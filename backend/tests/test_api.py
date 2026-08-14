import asyncio
import io
import wave

from fastapi.testclient import TestClient

from app import api
from app.main import app
from app.models import Notes, SpeakerTurn
from app.store import Store


class InstantRouter:
    async def transcribe(self, wav_bytes):
        return [SpeakerTurn("Speaker 1", "hello")]

    async def generate_notes(self, transcript_text):
        return Notes(summary="sum", decisions=[], open_questions=[])

    async def extract(self, transcript_text):
        from app.models import Entities

        return Entities(action_items=[], people=[], dates=[], topics=["t"])

    async def embed(self, texts):
        return [[1.0, 0.0]]


def tiny_wav():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 1600)
    return buf.getvalue()


def make_client(tmp_path):
    app.state.store = Store(str(tmp_path / "api.db"))
    app.state.router = InstantRouter()
    return TestClient(app)


def wait_done(client, mid, tries=50):
    for _ in range(tries):
        m = client.get(f"/meetings/{mid}").json()
        if m["status"] in ("done", "error"):
            return m
    raise AssertionError(f"pipeline never finished: {m}")


def test_upload_and_get(tmp_path):
    client = make_client(tmp_path)
    r = client.post(
        "/meetings/upload",
        files={"file": ("m.wav", tiny_wav(), "audio/wav")},
        data={"title": "standup"},
    )
    assert r.status_code == 202
    mid = r.json()["id"]
    m = wait_done(client, mid)
    assert m["status"] == "done"
    assert m["title"] == "standup"
    assert m["notes"]["summary"] == "sum"


def test_list_meetings(tmp_path):
    client = make_client(tmp_path)
    client.post("/meetings/upload", files={"file": ("a.wav", tiny_wav(), "audio/wav")})
    r = client.get("/meetings")
    assert r.status_code == 200
    assert len(r.json()["meetings"]) == 1


def test_get_missing_404(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/meetings/nope").status_code == 404


def test_device_websocket_stream(tmp_path):
    client = make_client(tmp_path)
    with client.websocket_connect("/ws/device") as ws:
        ws.send_text('{"title": "hardware demo"}')
        ack = ws.receive_json()
        assert ack["type"] == "ack"
        mid = ack["id"]
        ws.send_bytes(b"\x00\x00" * 1600)
        ws.send_bytes(b"\x00\x00" * 1600)
        ws.send_text('{"event": "stop"}')
        status = ws.receive_json()
        assert status == {"type": "status", "status": "processing"}
    m = wait_done(client, mid)
    assert m["status"] == "done"
    assert m["title"] == "hardware demo"


def test_device_websocket_stop_with_no_audio(tmp_path):
    client = make_client(tmp_path)
    with client.websocket_connect("/ws/device") as ws:
        ws.send_text('{"title": "empty"}')
        ack = ws.receive_json()
        assert ack["type"] == "ack"
        mid = ack["id"]
        ws.send_text('{"event": "stop"}')
        status = ws.receive_json()
        assert status == {"type": "status", "status": "error"}
    m = client.get(f"/meetings/{mid}").json()
    assert m["status"] == "error"
    assert "no audio" in m["error"]
