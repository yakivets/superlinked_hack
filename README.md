# Notetaker

An offline meeting notetaker for a hardware recorder. It turns raw audio into
speaker-diarized transcripts, meeting notes, action items, semantic search
across meetings, and a cross-meeting synthesis and graph view.

## Stack

Superlinked SIE (hosted) is the primary inference engine: it writes the notes,
extracts entities, embeds every meeting and reranks search results. Alibaba
Cloud Model Studio handles the two things SIE cannot — speaker-diarized
transcription (`qwen3.5-omni-flash`) and cross-meeting synthesis
(`qwen3.8-max`). That works out at roughly six SIE calls per two Alibaba calls
for a meeting.

Routing is per-primitive and configurable via `PROVIDER_*` env vars, and each
provider falls back to the other on failure.

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
display shows recording state, streaming stats and network status.

The dial picks the **agent** that will handle the meeting: press it to open the
picker, turn to browse, press again to commit. The agent decides the domain
context the model is given, which entities are extracted, and which SIE model
writes the notes — a legal or fintech meeting routes to `Qwen3.6-27B`, a standup
to the faster `Qwen3.5-4B`. `GET /agents` returns the same roster for the
dashboard, and `GET /routing` shows which model actually served each call.

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
