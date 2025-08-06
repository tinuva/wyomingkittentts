#!/usr/bin/env python3
"""
Simple Wyoming-like protocol client for testing the KittenTTS server.

Protocol (pragmatic subset):
- Each frame is 4-byte big-endian length followed by payload bytes.
- Request:
  1) JSON header frame: {"type":"TTS","voice":"expr-voice-5-m","speed":1.0,"sample_rate":24000}
  2) UTF-8 encoded text frame
- Response:
  1) JSON header frame: {"type":"AUDIO","format":"wav","sample_rate":24000,"voice":"expr-voice-5-m","ok":true}
     or {"type":"ERROR","message":"..."}
  2) If ok, a single frame of WAV bytes
"""

import argparse
import json
import socket
import struct
from typing import Tuple, Dict, Any


def send_frame(sock: socket.socket, data: bytes) -> None:
    """Send a single framed message."""
    sock.sendall(struct.pack(">I", len(data)))
    sock.sendall(data)


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes or raise RuntimeError if EOF occurs prematurely."""
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("Connection closed while reading frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_frame(sock: socket.socket) -> bytes:
    """Receive a single framed message."""
    hdr = recv_exact(sock, 4)
    (length,) = struct.unpack(">I", hdr)
    if length == 0:
        return b""
    return recv_exact(sock, length)


def tts_request(
    host: str,
    port: int,
    text: str,
    voice: str = "expr-voice-5-m",
    speed: float = 1.0,
    sample_rate: int = 24000,
    timeout: float = 30.0,
) -> Tuple[Dict[str, Any], bytes]:
    """
    Send a TTS request and return (response_header, wav_bytes).
    If the server returns an error, raises RuntimeError with the error message.
    """
    header = {
        "type": "TTS",
        "voice": voice,
        "speed": float(speed),
        "sample_rate": int(sample_rate),
    }

    with socket.create_connection((host, port), timeout=timeout) as sock:
        send_frame(sock, json.dumps(header).encode("utf-8"))
        send_frame(sock, text.encode("utf-8"))

        resp_hdr_bytes = recv_frame(sock)
        try:
            resp_hdr = json.loads(resp_hdr_bytes.decode("utf-8"))
        except Exception as e:
            raise RuntimeError(f"Invalid response header JSON: {e}") from e

        if resp_hdr.get("type") == "ERROR":
            raise RuntimeError(f"Server error: {resp_hdr.get('message')}")

        if resp_hdr.get("type") != "AUDIO" or resp_hdr.get("format") != "wav":
            raise RuntimeError(f"Unexpected response header: {resp_hdr}")

        wav_bytes = recv_frame(sock)
        return resp_hdr, wav_bytes


def main():
    parser = argparse.ArgumentParser(description="Wyoming KittenTTS client")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=10200, help="Server port (default: 10200)")
    parser.add_argument(
        "--voice",
        default="expr-voice-5-m",
        help="Voice id (default: expr-voice-5-m)",
    )
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed (default: 1.0)")
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=24000,
        help="Output sample rate (default: 24000)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Socket timeout seconds (default: 30)",
    )
    parser.add_argument(
        "text",
        nargs="?",
        default="This is a test of the Wyoming KittenTTS server.",
        help="Text to synthesize",
    )
    parser.add_argument("output", nargs="?", default="out.wav", help="Path to save WAV output")
    args = parser.parse_args()

    hdr, wav = tts_request(
        host=args.host,
        port=args.port,
        text=args.text,
        voice=args.voice,
        speed=args.speed,
        sample_rate=args.sample_rate,
        timeout=args.timeout,
    )

    with open(args.output, "wb") as f:
        f.write(wav)

    print(
        f"Saved WAV to {args.output} "
        f"(sr={hdr.get('sample_rate')}, voice={hdr.get('voice')}, bytes={len(wav)})"
    )


if __name__ == "__main__":
    main()
