# Makefile for Wyoming KittenTTS project
# Common tasks for building, running, testing, and publishing.

# Variables (can be overridden: `make VAR=value target`)
IMAGE_NAME ?= wy-kittentts
PORT       ?= 10200
HOST       ?= 0.0.0.0
MODEL_ID   ?= KittenML/kitten-tts-nano-0.1
VOICE      ?= expr-voice-5-m
SPEED      ?= 1.0
SAMPLE_RATE?= 24000
LOG_LEVEL  ?= INFO
HF_HOME    ?= /root/.cache/huggingface
CACHE_VOL  ?= hf-cache

# Derived
DOCKERFILE := server/Dockerfile
BUILD_CTX  := server

.PHONY: help
help:
	@echo "Makefile targets:"
	@echo "  build            Build Docker image ($(IMAGE_NAME))"
	@echo "  run              Run container (ephemeral) with port $(PORT) and cache volume"
	@echo "  run-no-cache     Run container without HF cache volume (slower first run)"
	@echo "  stop             Stop running container (if started via 'up')"
	@echo "  logs             Tail logs from docker-compose service"
	@echo "  up               docker-compose up -d (build if necessary)"
	@echo "  down             docker-compose down"
	@echo "  client           Run client to synthesize text -> WAV (vars: TEXT, OUT)"
	@echo "  health           Run health check client"
	@echo "  clean            Remove dangling images and prune build cache"
	@echo "  push             Push image to ghcr.io (requires GH login and GHCR permissions)"
	@echo "Variables:"
	@echo "  IMAGE_NAME, PORT, HOST, MODEL_ID, VOICE, SPEED, SAMPLE_RATE, LOG_LEVEL, HF_HOME, CACHE_VOL"

# -------- Docker build/run --------

.PHONY: build
build:
	docker build -t $(IMAGE_NAME):latest -f $(DOCKERFILE) $(BUILD_CTX)

.PHONY: run
run: build
	docker run --rm \
		-p $(PORT):$(PORT) \
		-e HOST=$(HOST) \
		-e PORT=$(PORT) \
		-e MODEL_ID="$(MODEL_ID)" \
		-e VOICE="$(VOICE)" \
		-e SPEED="$(SPEED)" \
		-e SAMPLE_RATE="$(SAMPLE_RATE)" \
		-e LOG_LEVEL="$(LOG_LEVEL)" \
		-e HF_HOME="$(HF_HOME)" \
		-v $(CACHE_VOL):$(HF_HOME) \
		$(IMAGE_NAME):latest

.PHONY: run-no-cache
run-no-cache: build
	docker run --rm \
		-p $(PORT):$(PORT) \
		-e HOST=$(HOST) \
		-e PORT=$(PORT) \
		-e MODEL_ID="$(MODEL_ID)" \
		-e VOICE="$(VOICE)" \
		-e SPEED="$(SPEED)" \
		-e SAMPLE_RATE="$(SAMPLE_RATE)" \
		-e LOG_LEVEL="$(LOG_LEVEL)" \
		$(IMAGE_NAME):latest

# -------- docker-compose helpers --------

.PHONY: up
up:
	docker compose up -d --build

.PHONY: down
down:
	docker compose down

.PHONY: logs
logs:
	docker compose logs -f wy-kittentts

.PHONY: stop
stop:
	docker compose stop wy-kittentts || true

# -------- Client utilities --------

# Usage:
#   make client TEXT="Hello Wyoming!" OUT=kitten.wav
TEXT ?= "Kitten TTS over Wyoming is working!"
OUT  ?= out.wav

.PHONY: client
client:
	python3 client/wy_client.py --host 127.0.0.1 --port $(PORT) --voice $(VOICE) --speed $(SPEED) --sample-rate $(SAMPLE_RATE) $(TEXT) $(OUT)

.PHONY: health
health:
	python3 client/health_check.py --host 127.0.0.1 --port $(PORT)

# -------- CI/Registry --------

# Push to GitHub Container Registry:
# 1) docker login ghcr.io
# 2) make push OWNER=<gh-username-or-org> TAG=<tag>
OWNER ?= $(shell git config --get user.name | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
TAG   ?= $(shell git rev-parse --short HEAD)
REG   ?= ghcr.io

.PHONY: push
push: build
	@if [ -z "$(OWNER)" ]; then echo "OWNER is required (e.g., make push OWNER=myorg)"; exit 1; fi
	docker tag $(IMAGE_NAME):latest $(REG)/$(OWNER)/$(IMAGE_NAME):$(TAG)
	docker push $(REG)/$(OWNER)/$(IMAGE_NAME):$(TAG)
	@echo "Pushed: $(REG)/$(OWNER)/$(IMAGE_NAME):$(TAG)"

# -------- Cleanup --------

.PHONY: clean
clean:
	@echo "Pruning dangling images and build cache..."
	docker image prune -f
	docker builder prune -f
