#!/usr/bin/env python3
import asyncio
import io
import json
import logging
import os
import struct
from typing import Optional

import soundfile as sf

# Shim misaki.espeak to avoid AttributeError on EspeakWrapper.set_data_path
# Safe because KittenTTS uses phonemizer's EspeakBackend internally, not misaki.espeak.
import sys
import types

if "misaki.espeak" not in sys.modules:
    shim_mod = types.ModuleType("misaki.espeak")

    class EspeakWrapper:
        data_path = None

        @staticmethod
        def set_data_path(path):
            EspeakWrapper.data_path = path

    setattr(shim_mod, "EspeakWrapper", EspeakWrapper)
    sys.modules["misaki.espeak"] = shim_mod

from kittentts import KittenTTS

# Basic, pragmatic Wyoming-like protocol:
# - Each message is framed with a 4-byte big-endian length, followed by payload bytes.
# - Client sends one header frame (JSON) with type "TTS" and optional fields:
#     { "type": "TTS", "voice": "expr-voice-5-m", "speed": 1.0, "sample_rate": 24000 }
# - Then client sends a text frame (UTF-8).
# - Server responds with a header frame (JSON) and a single audio frame (WAV bytes):
#     {
#         "type": "AUDIO",
#         "format": "wav",
#         "sample_rate": 24000,
#         "voice": "expr-voice-5-m",
#         "ok": true
#     }
# - On error, server responds with:
#     { "type": "ERROR", "message": "<details>" }
#
# This is intentionally minimal and self-contained. It’s compatible with
# simple Wyoming-style clients.

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
LOG = logging.getLogger("wy-kittentts")

# Server configuration via environment
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "10200"))

MODEL_ID = os.environ.get("MODEL_ID", "KittenML/kitten-tts-nano-0.1")
DEFAULT_VOICE = os.environ.get("VOICE", "expr-voice-4-f")
DEFAULT_SPEED = float(os.environ.get("SPEED", "1.0"))
DEFAULT_SAMPLE_RATE = int(os.environ.get("SAMPLE_RATE", "24000"))


class WyomingKittenTTSServer:
    def __init__(self) -> None:
        LOG.info("Loading KittenTTS model: %s", MODEL_ID)
        self.tts = KittenTTS(MODEL_ID)
        LOG.info("Available voices: %s", self.tts.available_voices)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        LOG.info("Client connected: %s", peer)

        try:
            header_bytes = await self._read_frame(reader)
            if header_bytes is None:
                await self._send_error(writer, "missing_header")
                return

            try:
                header = json.loads(header_bytes.decode("utf-8"))
            except Exception as e:
                LOG.error("Failed to parse header JSON: %s", e)
                await self._send_error(writer, "invalid_header_json")
                return

            # Support simple INFO queries over the same framing.
            # Header examples:
            #   {"type":"INFO","what":"voices"}   -> returns {"type":"INFO","voices":[...]}
            #   {"type":"INFO","what":"version"}  -> returns {"type":"INFO","version":"<str>"}
            msg_type = header.get("type")
            if msg_type == "INFO":
                what = str(header.get("what", "")).lower()
                if what in ("voices", "voice", "list_voices"):
                    resp = {
                        "type": "INFO",
                        "voices": list(self.tts.available_voices),
                    }
                    await self._write_frame(writer, json.dumps(resp).encode("utf-8"))
                    return
                elif what in ("version", "ver"):
                    # Try to report kittentts package version if available
                    try:
                        import importlib.metadata as im
                        ver = im.version("kittentts")
                    except Exception:
                        ver = "unknown"
                    resp = {"type": "INFO", "version": ver}
                    await self._write_frame(writer, json.dumps(resp).encode("utf-8"))
                    return
                else:
                    await self._send_error(writer, "unsupported_info_query")
                    return
            elif msg_type != "TTS":
                await self._send_error(writer, "unsupported_type")
                return

            text_bytes = await self._read_frame(reader)
            if text_bytes is None:
                await self._send_error(writer, "missing_text_body")
                return

            try:
                text = text_bytes.decode("utf-8")
            except Exception:
                await self._send_error(writer, "text_not_utf8")
                return

            voice = header.get("voice", DEFAULT_VOICE)
            speed = self._safe_float(header.get("speed", DEFAULT_SPEED), DEFAULT_SPEED)
            sample_rate = self._safe_int(
                header.get("sample_rate", DEFAULT_SAMPLE_RATE),
                DEFAULT_SAMPLE_RATE,
            )

            LOG.info("Synthesize request: voice=%s speed=%.2f sr=%d text='%s...'",
                     voice, speed, sample_rate, text[:80].replace("\n", " "))

            try:
                audio = self.tts.generate(text, voice=voice, speed=speed)
            except Exception as e:
                LOG.exception("TTS generation failed")
                await self._send_error(writer, f"tts_failed: {e}")
                return

            # Encode response as WAV PCM 16-bit
            wav_buf = io.BytesIO()
            sf.write(wav_buf, audio, sample_rate, format="WAV", subtype="PCM_16")
            wav_bytes = wav_buf.getvalue()

            resp_header = {
                "type": "AUDIO",
                "format": "wav",
                "sample_rate": sample_rate,
                "voice": voice,
                "ok": True,
            }
            await self._write_frame(writer, json.dumps(resp_header).encode("utf-8"))
            await self._write_frame(writer, wav_bytes)
            LOG.info("Sent audio response: %d bytes", len(wav_bytes))

        except asyncio.IncompleteReadError:
            LOG.warning("Connection closed abruptly by client: %s", peer)
        except Exception as e:
            LOG.exception("Unexpected server error: %s", e)
            # Try to inform client if possible
            try:
                await self._send_error(writer, "server_exception")
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            LOG.info("Client disconnected: %s", peer)

    async def _read_frame(self, reader: asyncio.StreamReader) -> Optional[bytes]:
        # Expect 4-byte big-endian length followed by that many bytes
        length_bytes = await reader.readexactly(4)
        (length,) = struct.unpack(">I", length_bytes)
        if length == 0:
            return b""
        data = await reader.readexactly(length)
        return data

    async def _write_frame(self, writer: asyncio.StreamWriter, data: bytes) -> None:
        writer.write(struct.pack(">I", len(data)))
        writer.write(data)
        await writer.drain()

    async def _send_error(self, writer: asyncio.StreamWriter, message: str) -> None:
        err = {"type": "ERROR", "message": message}
        await self._write_frame(writer, json.dumps(err).encode("utf-8"))

    @staticmethod
    def _safe_int(value, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _safe_float(value, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return default


async def main():
    server = WyomingKittenTTSServer()
    srv = await asyncio.start_server(server.handle_client, HOST, PORT)
    sockets = srv.sockets or []
    bind_info = ", ".join(str(s.getsockname()) for s in sockets)
    LOG.info("Wyoming KittenTTS server listening on %s", bind_info)
    async with srv:
        await srv.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
