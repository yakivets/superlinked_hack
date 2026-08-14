import asyncio
import io
import json
import wave

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel

from app import routing_log
from app.agents import AGENT_ORDER, AGENTS, DEFAULT_AGENT, get_agent
from app.pipeline import process_meeting
from app.search import search_meetings
from app.synthesis import build_graph, synthesize

router = APIRouter()


class SynthesisRequest(BaseModel):
    question: str
    k: int = 5


def _kick(request_app, meeting_id: str, wav_bytes: bytes, agent_id: str | None = None):
    asyncio.create_task(
        process_meeting(request_app.state.store, request_app.state.router,
                        meeting_id, wav_bytes, agent_id)
    )


@router.get("/agents")
def list_agents():
    """The agent roster, in the order the device's encoder cycles through them."""
    return {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "notes_model": a.notes_model,
                "long_model": a.long_model,
                "labels": a.labels,
            }
            for a in (AGENTS[k] for k in AGENT_ORDER)
        ],
        "default": DEFAULT_AGENT,
    }


@router.get("/routing")
def get_routing():
    """Which model served which call - the routing dashboard feed."""
    return {"summary": routing_log.summary(), "calls": routing_log.entries()}


@router.post("/meetings/upload", status_code=202)
async def upload_meeting(request: Request, file: UploadFile = File(...),
                         title: str = Form("Untitled meeting"),
                         agent: str = Form(DEFAULT_AGENT)):
    wav_bytes = await file.read()
    meeting_id = request.app.state.store.create_meeting(title)
    _kick(request.app, meeting_id, wav_bytes, agent)
    return {"id": meeting_id, "agent": get_agent(agent).id}


@router.get("/meetings")
def list_meetings(request: Request):
    return {"meetings": request.app.state.store.list_meetings()}


@router.get("/meetings/{meeting_id}")
def get_meeting(request: Request, meeting_id: str):
    m = request.app.state.store.get_meeting(meeting_id)
    if m is None:
        raise HTTPException(404, "meeting not found")
    return m


@router.get("/search")
async def search(request: Request, q: str = "", k: int = 5):
    if not q.strip():
        raise HTTPException(400, "q is required")
    results = await search_meetings(request.app.state.store, request.app.state.router, q, k)
    return {"results": results}


@router.post("/synthesis")
async def synthesis(request: Request, body: SynthesisRequest):
    return await synthesize(request.app.state.store, request.app.state.router, body.question, body.k)


@router.get("/graph")
def graph(request: Request):
    return build_graph(request.app.state.store)


SAMPLE_RATE = 16000
LIVE_WINDOW_S = 10
LIVE_WINDOW_BYTES = SAMPLE_RATE * 2 * LIVE_WINDOW_S


async def _transcribe_window(app, meeting_id: str, pcm: bytes, index: int, live: dict) -> None:
    """Transcribe one window while recording continues.

    Windows finish out of order, so results are keyed by index and the stored
    transcript is rebuilt in order each time one lands. This is a live preview:
    process_meeting re-transcribes the whole recording at stop, which is what
    the notes are built from - per-window speaker labels are independent of each
    other, so only the full pass gives consistent diarization.
    """
    try:
        turns = await app.state.router.transcribe(pcm_to_wav(pcm))
    except Exception as exc:
        print(f"[live] window {index} failed: {exc}", flush=True)
        return

    live[index] = turns
    text = " ".join(t.text for t in turns).strip()
    print(f"[live] +{index * LIVE_WINDOW_S}s: {text[:160]}", flush=True)

    ordered = [t for i in sorted(live) for t in live[i]]
    app.state.store.update_meeting(meeting_id, transcript=ordered)


def pcm_to_wav(pcm: bytes, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


@router.websocket("/ws/device")
async def device_stream(ws: WebSocket):
    await ws.accept()
    title = "Device meeting"
    agent_id = DEFAULT_AGENT
    frames = bytearray()
    meeting_id = None
    pending = bytearray()          # not yet sent to a live window
    live: dict[int, list] = {}     # window index -> turns
    live_tasks: list = []
    window_index = 0
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                frames.extend(msg["bytes"])
                pending.extend(msg["bytes"])

                # Fire each full window off concurrently so a slow ASR call
                # never stalls the audio stream.
                while len(pending) >= LIVE_WINDOW_BYTES and meeting_id is not None:
                    window = bytes(pending[:LIVE_WINDOW_BYTES])
                    del pending[:LIVE_WINDOW_BYTES]
                    live_tasks.append(asyncio.create_task(
                        _transcribe_window(ws.app, meeting_id, window, window_index, live)))
                    window_index += 1
            elif msg.get("text") is not None:
                data = json.loads(msg["text"])
                if meeting_id is None:
                    # Only honoured before the meeting exists: the device sends
                    # its encoder selection as the first frame.
                    if "title" in data:
                        title = data["title"]
                    if "agent" in data:
                        agent_id = get_agent(data["agent"]).id
                if data.get("event") == "stop":
                    break
            if meeting_id is None and msg.get("type") == "websocket.receive":
                agent = get_agent(agent_id)
                meeting_id = ws.app.state.store.create_meeting(title)
                print(f"\n[device] connected, agent={agent.id}, meeting={meeting_id[:8]}",
                      flush=True)
                await ws.send_json({"type": "ack", "id": meeting_id, "agent": agent.id})
    except WebSocketDisconnect:
        pass
    # Let any in-flight live windows settle before the full pass overwrites
    # their partial transcript.
    if live_tasks:
        await asyncio.gather(*live_tasks, return_exceptions=True)

    if meeting_id is not None:
        if frames:
            print(f"[device] stream ended, {len(frames)} bytes "
                  f"({len(frames) / 32000:.1f}s) -> processing", flush=True)
            _kick(ws.app, meeting_id, pcm_to_wav(bytes(frames)), agent_id)
            final_status = "processing"
        else:
            print("[device] stream ended with NO AUDIO", flush=True)
            ws.app.state.store.update_meeting(meeting_id, status="error", error="no audio received")
            final_status = "error"
        try:
            await ws.send_json({"type": "status", "status": final_status})
        except Exception:
            pass
