import asyncio
import io
import json
import wave

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel

from app.pipeline import process_meeting
from app.search import search_meetings
from app.synthesis import build_graph, synthesize

router = APIRouter()


class SynthesisRequest(BaseModel):
    question: str
    k: int = 5


def _kick(request_app, meeting_id: str, wav_bytes: bytes):
    asyncio.create_task(
        process_meeting(request_app.state.store, request_app.state.router, meeting_id, wav_bytes)
    )


@router.post("/meetings/upload", status_code=202)
async def upload_meeting(request: Request, file: UploadFile = File(...), title: str = Form("Untitled meeting")):
    wav_bytes = await file.read()
    meeting_id = request.app.state.store.create_meeting(title)
    _kick(request.app, meeting_id, wav_bytes)
    return {"id": meeting_id}


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
    frames = bytearray()
    meeting_id = None
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                frames.extend(msg["bytes"])
            elif msg.get("text") is not None:
                data = json.loads(msg["text"])
                if "title" in data and meeting_id is None:
                    title = data["title"]
                if data.get("event") == "stop":
                    break
            if meeting_id is None and msg.get("type") == "websocket.receive":
                meeting_id = ws.app.state.store.create_meeting(title)
                await ws.send_json({"type": "ack", "id": meeting_id})
    except WebSocketDisconnect:
        pass
    if meeting_id is not None:
        if frames:
            _kick(ws.app, meeting_id, pcm_to_wav(bytes(frames)))
            final_status = "processing"
        else:
            ws.app.state.store.update_meeting(meeting_id, status="error", error="no audio received")
            final_status = "error"
        try:
            await ws.send_json({"type": "status", "status": final_status})
        except Exception:
            pass
