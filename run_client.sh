#!/usr/bin/env bash
# Helper script to run the Wyoming KittenTTS client locally and save a WAV file.
#
# Usage:
#   ./run_client.sh "Your text to synthesize" output.wav
#   HOST=127.0.0.1 PORT=10200 VOICE=expr-voice-4-f SPEED=1.1 SAMPLE_RATE=24000 ./run_client.sh "Hello!" hello.wav
#
# Env vars (with defaults):
#   HOST=127.0.0.1
#   PORT=10200
#   VOICE=expr-voice-5-m
#   SPEED=1.0
#   SAMPLE_RATE=24000
#
# Notes:
# - Expects a Python venv in .venv (use ./run_local.sh to create it).
# - If not using the venv, ensure required Python packages are available on your PATH.
# - Creates the output directory if it does not exist.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Defaults
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-10200}"
VOICE="${VOICE:-expr-voice-4-f}"
SPEED="${SPEED:-1.0}"
SAMPLE_RATE="${SAMPLE_RATE:-24000}"

TEXT="${1:-This is a test of the Wyoming KittenTTS server.}"
OUT="${2:-out.wav}"

# Ensure output directory exists
OUT_DIR="$(dirname "$OUT")"
if [[ "$OUT_DIR" != "." ]]; then
  mkdir -p "$OUT_DIR"
fi

# Activate venv if present
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found on PATH."
  exit 1
fi

echo "==> Sending TTS request"
echo "    HOST=${HOST} PORT=${PORT}"
echo "    VOICE=${VOICE} SPEED=${SPEED} SAMPLE_RATE=${SAMPLE_RATE}"
echo "    TEXT='${TEXT}'"
echo "    OUT=${OUT}"

python3 "client/wy_client.py" \
  --host "${HOST}" \
  --port "${PORT}" \
  --voice "${VOICE}" \
  --speed "${SPEED}" \
  --sample-rate "${SAMPLE_RATE}" \
  "${TEXT}" \
  "${OUT}"

echo "==> Done. Wrote WAV to ${OUT}"
