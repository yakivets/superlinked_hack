# Notetaker — project context

Offline meeting notetaker: a hardware capture device streams room audio to a
laptop backend that transcribes, takes notes, extracts entities, and answers
questions across meetings.

Two halves, developed in parallel:

- `backend/` — FastAPI: ingest, pipeline, search, synthesis. See `backend/API.md`.
- `firmware/` — ESP32-S3 capture node (Axiometa Genesis Mini).
- `live_server.py` — standalone live-transcription rig for testing the device.

## Hardware

Axiometa **Genesis Mini** (ESP32-S3), flashed via the `axiometa` MCP server.

| Port | Module | Id | Pins |
|---|---|---|---|
| P1 | Rotary Encoder | `AX22-0003` | BTN=IO0, CLK=IO1, DT=IO2 |
| P2 | ST7735 IPS TFT | `AX22-0034` | CS=IO0, RST=IO1, DC=IO2 |
| P3 | PDM Microphone | `AX22-0044` | SEL=IO0, DATA=IO1, CLK=IO2 |
| P4 | Push Button | `AX22-0007` | signal=IO1 |

Audio: 16 kHz mono 16-bit signed PCM (the only stable PDM config on this chip).

### Hard-won gotchas

These each cost real time — do not rediscover them.

- **The radio is 2.4 GHz only.** A 5 GHz-only SSID fails with no useful error;
  the board just reports a failed connect. iPhone hotspots default to 5 GHz —
  "Maximize Compatibility" forces 2.4 GHz *and* drops WPA3 to WPA2, which the
  ESP32 also prefers. Check the band before debugging firmware:
  `netsh wlan show networks mode=bssid`.
- **Guest/corporate networks usually isolate clients**, so the board connects
  fine and every request to the laptop still fails. Use a phone hotspot.
- **Windows firewall blocks the inbound port** by default. Needs an admin rule:
  `New-NetFirewallRule -DisplayName "notetaker" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Any`
- **The ST7735 panel is BGR**: call `tft.color565(B, G, R)`, and never use the
  `ST77XX_*` constants — they render as the wrong colour.
- **Never draw directly to the display in a loop.** Draw into `GFXcanvas16` and
  push once per frame with `drawRGBBitmap`, or it flickers badly.
- **Serial can look dead when it is not.** ESP32-S3 native USB re-enumerates on
  reset, so early boot prints are frequently lost. The firmware emits a periodic
  `[beat]` line specifically so a silent board is distinguishable from a hung one.
- **arduino-cli requires the sketch folder name to match the `.ino`.** Sources
  live in `firmware/`; copy them into `sketch/` (gitignored) before compiling.

### Building and flashing

Uses the `axiometa` MCP tools (`compile`, `upload`, `read_serial`), not a local
arduino-cli. Parts must be passed explicitly — that is what decides which
libraries get installed:

```
parts:     ["AX22-0044", "AX22-0007", "AX22-0034", "AX22-0003", "wifi"]
libraries: ["WebSockets"]
source:    sketch/          (copy of firmware/)
board_id:  genesis-mini
```

Credentials are compiled in, so they must exist before the build:
`cp firmware/secrets.h.example firmware/secrets.h` and fill in SSID, password,
and the laptop's IP. `secrets.h` is gitignored. Changing Wi-Fi or the laptop's
IP requires a recompile and reflash — there is no runtime configuration.

## Agents and model routing

An **agent** decides how a meeting is understood — the domain context given to
the model, which entity labels matter, and **which SIE model writes the notes**.
The dial on the device picks one while idle; it locks for the duration of a
meeting so it cannot change underneath a recording.

| Agent | Notes model | Rationale |
|---|---|---|
| General | `Qwen/Qwen3.5-4B` | balanced default |
| Fintech | `Qwen/Qwen3.6-27B` | figures and compliance need real reasoning |
| Engineering | `Qwen/Qwen3.5-4B` | fast, well-structured domain |
| Standup | `Qwen/Qwen3.5-4B` | short meetings, speed over depth |

Extraction stays on the fast model even when notes use the heavy one — it is a
narrow structured task. Meetings over 15 minutes escalate to `:long-context`.

`GET /agents` is the roster (same order as the device's dial), `GET /routing`
is the live feed of which model served which call, with latency.

**The agent list is duplicated in `firmware/ui.cpp` and `backend/app/agents.py`
and the order must match** — the device sends an id string, so a mismatch means
the wrong agent silently handles the meeting.

### What SIE actually offers (verified live 2026-08-14)

Probed via `GET /v1/models` — 61 models. What works and what does not:

- **Works:** `Qwen3.5-4B` and `Qwen3.6-27B` chat (plus `:thinking`,
  `:long-context` variants), `Qwen3-Embedding-4B` (2560d), `BGE-m3` (1024d),
  `Qwen3-Reranker-0.6B` / `-4B`.
- **Does not work:** `/v1/audio/transcriptions` with
  `openai/whisper-large-v3-turbo` returns 500 on real audio, so **ASR stays on
  Alibaba** — which also gives speaker diarization, the honest justification for
  that offload.
- **Not provisioned:** domain-tuned embedding variants such as
  `BAAI/bge-m3:banking` return 503 `QUEUE_UNAVAILABLE`. Agent specialisation is
  therefore prompt + model + labels, not per-domain embeddings.

## Device → backend contract

One WebSocket per meeting, `/ws/device`:

```
button press  -> connect
device        -> {"agent":"fintech","title":"Device meeting"}   FIRST message
server        -> {"type":"ack","id":"<meeting_id>","agent":"fintech"}
device        -> binary PCM frames, continuously
button press  -> {"event":"stop"}, then disconnect
server        -> {"type":"status","status":"processing"}
```

The hello must arrive before any audio: the backend creates the meeting from the
first message it receives, and reads the agent from that message. The firmware
holds audio back until the hello has gone out for exactly this reason.

Capture runs on core 0 writing into a PSRAM ring buffer; the main loop drains it
to the socket. That split is deliberate — a slow or stalled network must never
interrupt audio capture. If uploads fall behind, the firmware logs dropped bytes
rather than silently corrupting the stream.

## Live transcription rig

`live_server.py` implements the same `/ws/device` contract, so **the firmware
needs no change to use it**. Unlike the real backend (which transcribes once, at
stop), it transcribes every 10 s *during* recording and serves a live page:

```bash
python live_server.py     # then open http://localhost:8000
```

Windows are transcribed concurrently, so ASR latency never blocks capture. Each
window is transcribed independently with no cross-window context, so sentences
spanning a boundary can read oddly at the seam.

## Status

Verified end to end on real hardware: button press produces a transcribed
meeting with notes, entities, and an embedding. Live per-10s transcription
during recording also verified.
