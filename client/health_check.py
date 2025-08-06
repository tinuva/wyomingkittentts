#!/usr/bin/env python3
"""
Tiny health-check client for the Wyoming KittenTTS server.

This performs a minimal end-to-end readiness check:
1) Connects to the server.
2) Sends a very short TTS request.
3) Verifies a valid AUDIO header and non-empty WAV payload is returned.

Exit codes:
- 0: Healthy (server ready)
- 1: Unhealthy (unexpected response / protocol error)
- 2: Connection error / timeout

Usage:
  python health_check.py --host 127.0.0.1 --port 10200
"""

import argparse
import json
import socket
import struct
import sys
from typing import Tuple, Dict, Any


def send_frame(sock: socket.socket, data: bytes) -> None:
    sock.sendall(struct.pack(">I", len(data)))
    sock.sendall(data)


def recv_exact(sock: socket.socket, n: int) -> bytes:
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
    hdr = recv_exact(sock, 4)
    (length,) = struct.unpack(">I", hdr)
    if length == 0:
        return b""
    return recv_exact(sock, length)


def check_server(host: str, port: int, timeout: float = 10.0) -> Tuple[Dict[str, Any], bytes]:
    """
    Sends a minimal TTS request and returns (response_header, wav_bytes).
    Raises RuntimeError on protocol/server error.
    """
    header = {
        "type": "TTS",
        "voice": "expr-voice-5-m",
        "speed": 1.0,
        "sample_rate": 24000,
    }
    text = "ok"

    with socket.create_connection((host, port), timeout=timeout) as sock:
        send_frame(sock, json.dumps(header).encode("utf-8"))
        send_frame(sock, text.encode("utf-8"))

        resp_hdr_bytes = recv_frame(sock)
        try:
            resp_hdr = json.loads(resp_hdr_bytes.decode("utf-8"))
        except Exception as e:
            raise RuntimeError(f"Invalid response header JSON: {e}")

        if resp_hdr.get("type") == "ERROR":
            raise RuntimeError(f"Server error: {resp_hdr.get('message')}")

        if resp_hdr.get("type") != "AUDIO" or resp_hdr.get("format") != "wav":
            raise RuntimeError(f"Unexpected response header: {resp_hdr}")

        wav_bytes = recv_frame(sock)
        if not wav_bytes:
            raise RuntimeError("Empty WAV payload")
        return resp_hdr, wav_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="Health-check client for Wyoming KittenTTS server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=10200, help="Server port (default: 10200)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Socket timeout seconds (default: 10)")
    args = parser.parse_args()

    try:
        hdr, wav = check_server(args.host, args.port, args.timeout)
        # Basic sanity checks on header fields
        if hdr.get("ok") is True and hdr.get("sample_rate") in (16000, 22050, 24000, 44100, 48000) and len(wav) > 44:
            print(f"healthy: sr={hdr.get('sample_rate')}, voice={hdr.get('voice')}, wav_bytes={len(wav)}")
            return 0
        else:
            print(f"unhealthy: unexpected header or payload (hdr={hdr}, bytes={len(wav)})", file=sys.stderr)
            return 1
    except (ConnectionRefusedError, TimeoutError, OSError) as e:
        print(f"unhealthy: connection error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"unhealthy: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
