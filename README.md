# Notetaker

An offline meeting notetaker for a hardware recorder. It turns raw audio into
speaker-diarized transcripts, meeting notes, action items, semantic search
across meetings, and a cross-meeting synthesis and graph view.

## Stack

Alibaba Cloud Qwen omni-flash for transcription and Qwen chat models for
notes and synthesis, with Superlinked SIE (hosted) as an alternate provider
for notes, extraction, embedding, and reranking. Provider routing is
per-primitive and configurable via env vars.

## Running it

```bash
cp .env.example .env   # fill in your API keys
cd backend
uv venv --python 3.12 .venv
uv pip install -e . --group dev
.venv/bin/uvicorn app.main:app --port 8000
```

See `backend/API.md` for the full HTTP and WebSocket contract.

## The device

An Axiometa Genesis Mini (ESP32-S3) with a PDM microphone, a button, a rotary
encoder and a small IPS display. Pressing the button opens a WebSocket to the
backend and streams 16 kHz mono PCM continuously until you press it again; the
display shows recording state, streaming stats and network status, and the
encoder switches between those views.

Firmware sources are in `firmware/`. Credentials are compiled in, so set them
first:

```bash
cp firmware/secrets.h.example firmware/secrets.h   # SSID, password, laptop IP
```

The board's radio is **2.4 GHz only** — a 5 GHz network will never connect. See
`CLAUDE.md` for the full hardware notes, pin map and build instructions.

## Watching a meeting transcribe live

The backend transcribes a meeting once it ends. To watch transcription happen
*during* recording — useful for checking the microphone and the network — run
the standalone rig instead, which speaks the same device protocol:

```bash
python live_server.py     # then open http://localhost:8000
```

It transcribes every 10 seconds while audio keeps streaming.

## Tests

```bash
cd backend
.venv/bin/pytest -v            # offline suite
.venv/bin/pytest -v -m live    # live suite, needs real API keys
```
