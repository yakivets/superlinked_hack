# Meeting Notetaker API

Frontend contract for the backend. FastAPI app, CORS wide open (`allow_origins=["*"]`).
Base URL in dev: `http://localhost:8000`.

All examples below are copied verbatim from a live run against the real Alibaba
(`qwen3.5-omni-flash` transcription) and hosted Superlinked SIE endpoints
(`https://api.superlinked.com`, used for notes/extract/embed/rerank per
`PROVIDER_*` in `.env`). No API keys appear in any response body, so nothing
here is redacted.

## Meeting status lifecycle

```
processing -> transcribed -> done
           \-> error
```

- `processing`: row created, audio duration recorded, transcription in flight.
- `transcribed`: speaker-labeled transcript saved; notes/extract/embed running.
- `done`: notes, entities and embedding all saved. Terminal.
- `error`: something in the pipeline raised; `error` field holds the message. Terminal.

**The frontend should poll `GET /meetings/{id}` every ~2s while `status` is not
`done` or `error`.** There is no push/webhook for meeting completion (the
device WebSocket has its own status message, see below, but it does not
report the async pipeline's outcome).

---

## `GET /healthz`

Liveness check.

**Response `200`**
```json
{ "ok": true }
```

---

## `POST /meetings/upload`

Upload a full WAV recording for async processing. `multipart/form-data`.

**Request**
- `file`: WAV audio (required)
- `title`: string (optional, default `"Untitled meeting"`)

**Response `202`**
```json
{ "id": "acd91b43874e45d4a1867d0166776538" }
```

The meeting is created with `status: "processing"` and a background task
(`process_meeting`) starts immediately: transcribe -> notes+extract (in
parallel) -> embed -> `status: "done"`. Poll `GET /meetings/{id}` for progress.

---

## `WS /ws/device`

Streaming ingest for the hardware device. Binary frames carry raw 16kHz
mono 16-bit PCM; text frames carry small JSON control messages.

**Message sequence (client -> server), exactly as implemented in `app/api.py`:**

1. Client optionally sends a text frame first to set the title:
   ```json
   { "title": "hardware demo" }
   ```
   (Only honored if received before the meeting is created — i.e. it must be
   the first message.)
2. On the **first message of any kind** (text or bytes), the server creates
   the meeting row and replies with an ack text frame:
   ```json
   { "type": "ack", "id": "<meeting id>" }
   ```
3. Client streams zero or more binary frames of raw PCM:
   ```
   ws.send_bytes(<pcm16 bytes>)
   ```
   Bytes are appended to an in-memory buffer; there is no per-chunk ack.
4. Client sends a text frame to end the recording:
   ```json
   { "event": "stop" }
   ```
5. Server closes the loop and, in all cases, replies with one final status
   frame before the socket handler returns: `{"type": "status", "status": "processing"}`
   if audio was received, or `{"type": "status", "status": "error"}` if it
   wasn't (see zero-audio behavior below).
6. Client may then close the connection (or the server closes it after
   sending the status frame).

**Zero-audio behavior:** if `stop` arrives with no PCM bytes ever received,
the server does **not** kick off the processing pipeline. Instead it writes
`status: "error"`, `error: "no audio received"` directly to the store and
sends a matching `{"type": "status", "status": "error"}` frame over the
socket before closing. The frontend/device can still call
`GET /meetings/{id}` afterwards to fetch the full error detail.

If audio was received, the server behaves like `/meetings/upload`: it kicks
off `process_meeting` in the background (still WAV-wraps the raw PCM first)
and the meeting proceeds through the normal `processing -> transcribed ->
done|error` lifecycle.

---

## `GET /meetings`

List all meetings, newest first. Lightweight (no `transcript`/`embedding`).

**Response `200`**
```json
{
  "meetings": [
    {
      "id": "e98836df123c4049b1a2ba249dcab895",
      "title": "Payments update",
      "created_at": "2026-08-14T12:18:38.367847+00:00",
      "duration_s": 9.1961875,
      "status": "done",
      "error": null,
      "notes": {
        "summary": "Speaker 1 confirmed that both bugs are fixed and deployed, clearing the way to ship the onboarding flow. Speaker 2 agreed to proceed with the announcement as originally scheduled for Monday morning. The team is now ready to execute the final release steps.",
        "decisions": [
          "Ship the onboarding flow - Speaker 1",
          "Send announcement on Monday morning - Speaker 2"
        ],
        "open_questions": []
      },
      "entities": {
        "action_items": [
          { "text": "Announce payment bugs fixed and onboarding flow ready to ship", "owner": "Speaker 2" },
          { "text": "Ship onboarding flow", "owner": null }
        ],
        "people": [],
        "dates": ["Monday morning"],
        "topics": ["payments", "bugs", "onboarding", "deployment", "announcement", "shipping"]
      }
    }
  ]
}
```

---

## `GET /meetings/{id}`

Full meeting detail, including `transcript` and `embedding` (heavy fields
omitted from the list endpoint above).

**Response `200`** (same shape as a list entry, plus):
```json
{
  "id": "e98836df123c4049b1a2ba249dcab895",
  "title": "Payments update",
  "created_at": "2026-08-14T12:18:38.367847+00:00",
  "duration_s": 9.1961875,
  "status": "done",
  "error": null,
  "notes": { "...": "as above" },
  "entities": { "...": "as above" },
  "transcript": [
    { "speaker": "Speaker 1", "text": "Quick update on payments. Both bugs are fixed and deployed. We are clear to ship the onboarding flow." },
    { "speaker": "Speaker 2", "text": "Great, then the announcement goes out Monday morning as planned." }
  ],
  "embedding": [-0.00040201310184784234, 0.0018990333192050457, "... 2560 floats total (Qwen/Qwen3-Embedding-4B)"]
}
```

**Response `404`** (unknown id):
```json
{ "detail": "meeting not found" }
```

---

## `GET /search?q=&k=`

Semantic search over `done` meetings. `q` is required; `k` defaults to `5`
(top-k results returned, after fetching `2*k` semantic candidates and
re-ranking/fusing).

**Request**: `GET /search?q=payment%20bugs&k=5`

**Response `200`**
```json
{
  "results": [
    {
      "id": "acd91b43874e45d4a1867d0166776538",
      "title": "Sprint planning",
      "created_at": "2026-08-14T12:18:38.364557+00:00",
      "score": 0.9953,
      "summary": "The team initially planned to ship the new onboarding flow next week due to strong beta metrics, but Speaker 2 delayed the launch to address two open bugs in the payment step. After agreeing to postpone, Speaker 1 confirmed Monday as the new ship date and accepted responsibility for the announcement. The payment bugs remain the immediate focus before the release."
    },
    {
      "id": "e98836df123c4049b1a2ba249dcab895",
      "title": "Payments update",
      "created_at": "2026-08-14T12:18:38.367847+00:00",
      "score": 0.9883,
      "summary": "Speaker 1 confirmed that both bugs are fixed and deployed, clearing the way to ship the onboarding flow. Speaker 2 agreed to proceed with the announcement as originally scheduled for Monday morning. The team is now ready to execute the final release steps."
    }
  ]
}
```

`score` is a fusion of semantic similarity/rerank (60%), recency (25%,
exponential decay over days since `created_at`), and query/topic word
overlap (15%).

**Response `400`** (missing/blank `q`):
```json
{ "detail": "q is required" }
```

---

## `POST /synthesis`

Cross-meeting Q&A. Runs `/search` internally to gather context, then asks
`qwen3.8-max` (Alibaba) to answer using only the retrieved meeting records.

**Request**
```json
{ "question": "What was decided about shipping the onboarding flow?", "k": 5 }
```
(`k` optional, defaults to `5`.)

**Response `200`**
```json
{
  "answer": "In **Sprint planning**, the team decided to delay shipping the onboarding flow until Monday to fix two payment-step bugs, with Speaker 1 owning the announcement.\n\nIn **Payments update**, after the bugs were fixed and deployed, they decided to proceed with shipping the onboarding flow and send the announcement Monday morning.",
  "sources": [
    { "id": "acd91b43874e45d4a1867d0166776538", "title": "Sprint planning" },
    { "id": "e98836df123c4049b1a2ba249dcab895", "title": "Payments update" }
  ]
}
```

If there are no meetings yet, `search_meetings` returns no hits and the
response is:
```json
{ "answer": "No meetings recorded yet.", "sources": [] }
```

---

## `GET /graph`

Similarity graph across all `done` meetings (nodes = meetings, edges = pairs
with cosine similarity >= 0.4 between their embeddings).

**Response `200`**
```json
{
  "nodes": [
    { "id": "acd91b43874e45d4a1867d0166776538", "title": "Sprint planning" },
    { "id": "e98836df123c4049b1a2ba249dcab895", "title": "Payments update" }
  ],
  "edges": [
    {
      "source": "acd91b43874e45d4a1867d0166776538",
      "target": "e98836df123c4049b1a2ba249dcab895",
      "weight": 0.736,
      "shared": ["announcement", "shipping"]
    }
  ]
}
```

`shared` is the sorted intersection of each meeting's `topics` and `people`
entity lists.
