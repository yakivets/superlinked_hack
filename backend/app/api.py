import asyncio
import io
import json
import wave

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.websockets import WebSocketDisconnect

from app.pipeline import process_meeting

router = APIRouter()


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
            if msg.get("bytes") is not None:
                frames.extend(msg["bytes"])
            elif msg.get("text") is not None:
                data = json.loads(msg["text"])
                if "title" in data and meeting_id is None:
                    title = data["title"]
                if data.get("event") == "stop":
                    break
            if meeting_id is None:
                meeting_id = ws.app.state.store.create_meeting(title)
                await ws.send_json({"type": "ack", "id": meeting_id})
            if msg.get("type") == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    if meeting_id is not None and frames:
        _kick(ws.app, meeting_id, pcm_to_wav(bytes(frames)))
        try:
            await ws.send_json({"type": "status", "status": "processing"})
        except Exception:
            pass
