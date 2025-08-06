#!/usr/bin/env bash
# Helper script to run the Wyoming KittenTTS server locally using a Python venv.
# - Ensures macOS system dependencies (brew: espeak, libsndfile)
# - Creates/updates a local venv at .venv
# - Installs Python deps from server/requirements.txt
# - Exposes environment variables to configure the server
# - Starts the server in the foreground
#
# Usage:
#   ./run_local.sh
#   LOG_LEVEL=DEBUG VOICE=expr-voice-4-f ./run_local.sh
#
# Configurable env vars (with defaults):
#   HOST=0.0.0.0
#   PORT=10200
#   MODEL_ID=KittenML/kitten-tts-nano-0.1
#   VOICE=expr-voice-5-m
#   SPEED=1.0
#   SAMPLE_RATE=24000
#   LOG_LEVEL=INFO
#
# Notes:
# - First TTS request downloads the model; expect a short delay.
# - On macOS Apple Silicon, ensure Homebrew is installed under /opt/homebrew.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Default envs if not provided
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-10200}"
export MODEL_ID="${MODEL_ID:-KittenML/kitten-tts-nano-0.1}"
export VOICE="${VOICE:-expr-voice-5-m}"
export SPEED="${SPEED:-1.0}"
export SAMPLE_RATE="${SAMPLE_RATE:-24000}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

echo "==> Wyoming KittenTTS local runner"
echo "    HOST=${HOST} PORT=${PORT}"
echo "    MODEL_ID=${MODEL_ID}"
echo "    VOICE=${VOICE} SPEED=${SPEED} SAMPLE_RATE=${SAMPLE_RATE}"
echo "    LOG_LEVEL=${LOG_LEVEL}"

# Detect macOS + Homebrew paths
UNAME_S="$(uname -s || true)"
if [[ "$UNAME_S" == "Darwin" ]]; then
  # Prefer Homebrew under /opt/homebrew (Apple Silicon)
  if [[ -x "/opt/homebrew/bin/brew" ]]; then
    BREW="/opt/homebrew/bin/brew"
  elif command -v brew >/dev/null 2>&1; then
    BREW="$(command -v brew)"
  else
    echo "Warning: Homebrew not found. On macOS, you may need 'brew install espeak libsndfile' if runtime errors occur."
    BREW=""
  fi

  if [[ -n "${BREW}" ]]; then
    echo "==> Checking macOS system dependencies via Homebrew"
    if ! command -v espeak >/dev/null 2>&1; then
      echo "   - Installing espeak (espeak-ng compatible)..."
      "$BREW" install espeak
    else
      echo "   - espeak found: $(command -v espeak)"
    fi

    if ! pkg-config --exists sndfile 2>/dev/null; then
      echo "   - Installing libsndfile..."
      "$BREW" install libsndfile
    else
      echo "   - libsndfile is available"
    fi
  fi

  # Hint for phonemizer if needed
  if [[ -z "${PHONEMIZER_ESPEAK_LIBRARY:-}" ]]; then
    if [[ -f "/opt/homebrew/lib/libespeak-ng.dylib" ]]; then
      export PHONEMIZER_ESPEAK_LIBRARY="/opt/homebrew/lib/libespeak-ng.dylib"
      echo "   - Set PHONEMIZER_ESPEAK_LIBRARY=${PHONEMIZER_ESPEAK_LIBRARY}"
    fi
  fi
fi

# Python venv setup
if [[ ! -d ".venv" ]]; then
  echo "==> Creating Python venv at .venv"
  python3 -m venv .venv
fi

# Activate venv
# shellcheck disable=SC1091
source ".venv/bin/activate"

echo "==> Python: $(python -V)"
echo "==> Upgrading pip..."
python -m pip install --upgrade pip

# Install Python requirements
if [[ -f "server/requirements.txt" ]]; then
  echo "==> Installing Python requirements from server/requirements.txt"
  pip install -r server/requirements.txt
else
  echo "Error: server/requirements.txt not found. Are you in the project root?"
  exit 1
fi

# Sanity: ensure script is run from repo root
if [[ ! -f "server/app.py" ]]; then
  echo "Error: server/app.py not found. Run this script from 'tts' directory."
  exit 1
fi

echo "==> Starting Wyoming KittenTTS server (Ctrl+C to stop)"
echo "    Listening on ${HOST}:${PORT}"
exec python "server/app.py"
