# Wyoming KittenTTS Server

This project packages the KittenTTS model behind a minimal Wyoming-style protocol server and provides a simple Python client for testing.

Contents
- server/: Wyoming KittenTTS server (Dockerized)
- client/: Simple Python test client

Prerequisites
- Docker (for containerized server)
- Python 3.9+ (only needed for running the local client)

Model
- Default: KittenML/kitten-tts-nano-0.1
- The model is downloaded on the first run from Hugging Face and cached in the container.
- Available voices: expr-voice-2-m, expr-voice-2-f, expr-voice-3-m, expr-voice-3-f, expr-voice-4-m, expr-voice-4-f, expr-voice-5-m, expr-voice-5-f

Build the Docker image
From the repo root:
1) Build
   docker build -t wy-kittentts:latest -f server/Dockerfile server

2) Run
   docker run --rm -p 10200:10200 wy-kittentts:latest

3) Optional: persist Hugging Face cache between runs
   docker run --rm -p 10200:10200 \
     -v hf-cache:/root/.cache/huggingface \
     wy-kittentts:latest

Or use docker-compose
1) Up (builds if needed)
   docker compose up -d

2) View logs
   docker compose logs -f wy-kittentts

3) Recreate after changes
   docker compose up -d --build

4) Stop
   docker compose down

Environment variables (server)
- HOST: bind address (default: 0.0.0.0)
- PORT: TCP port (default: 10200)
- MODEL_ID: Hugging Face repo id (default: KittenML/kitten-tts-nano-0.1)
- VOICE: default voice (default: expr-voice-5-m)
- SPEED: default speed (default: 1.0)
- SAMPLE_RATE: default sample rate (default: 24000)
- LOG_LEVEL: logging level (default: INFO)

Examples:
- Change default voice:
  docker run --rm -p 10200:10200 -e VOICE=expr-voice-4-f wy-kittentts:latest
- Use a different model:
  docker run --rm -p 10200:10200 -e MODEL_ID=KittenML/kitten-tts-nano-0.1 wy-kittentts:latest

Protocol (pragmatic Wyoming subset)
- Each frame is 4-byte big-endian length followed by payload bytes.
- Client → Server:
  1) JSON header frame:
     {"type":"TTS","voice":"expr-voice-5-m","speed":1.0,"sample_rate":24000}
  2) UTF-8 encoded text frame.
- Server → Client:
  1) JSON header frame:
     {"type":"AUDIO","format":"wav","sample_rate":24000,"voice":"expr-voice-5-m","ok":true}
     or {"type":"ERROR","message":"..."}
  2) If ok, a single frame with WAV bytes (PCM 16-bit).

Run the client
Use Python on your host to send a TTS request and save WAV output.

1) Install Python 3.9+ (if not already available).
2) Run:
   python client/wy_client.py "Kitten TTS over Wyoming is working!" out.wav

Health check
Use a tiny end-to-end probe to verify the server is ready.

1) With docker-compose:
   docker compose up -d
   python client/health_check.py --host 127.0.0.1 --port 10200

2) With raw docker:
   docker run --rm -p 10200:10200 -v hf-cache:/root/.cache/huggingface wy-kittentts:latest
   python client/health_check.py --host 127.0.0.1 --port 10200

Exit codes:
- 0 healthy
- 1 protocol/server error
- 2 connection/timeout error

Client CLI options
- --host: server host (default: 127.0.0.1)
- --port: server port (default: 10200)
- --voice: voice id (default: expr-voice-5-m)
- --speed: speech speed (default: 1.0)
- --sample-rate: output sample rate (default: 24000)
- --timeout: socket timeout seconds (default: 30)
- Positional:
  - text: text to synthesize (default: demo sentence)
  - output: output wav path (default: out.wav)

Troubleshooting
- First request is slow
  The model downloads on first use. Use a volume to cache models:
  docker run --rm -p 10200:10200 -v hf-cache:/root/.cache/huggingface wy-kittentts:latest

- Missing phonemizer/espeak-ng or soundfile libs
  These are preinstalled in the Docker image (espeak-ng, libsndfile1). Use the container to avoid host dependency issues.

- Voice not available error
  Check the server logs for the list of available voices on startup.

- Connection refused
  Ensure the container is running and port 10200 is published: -p 10200:10200.

License
- KittenTTS and its model files are under their respective licenses. Review the upstream repository for details.
