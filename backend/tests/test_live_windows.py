"""Live windowed transcription during a device stream."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import api
from app.main import app
from app.models import Entities, Notes, SpeakerTurn
from app.store import Store


class WindowRouter:
    """Numbers each transcribe call, and makes the FIRST window slowest so the
    ordering logic is exercised with results arriving out of order."""

    def __init__(self):
        self.calls = 0

    async def transcribe(self, wav_bytes):
        self.calls += 1
        n = self.calls
        await asyncio.sleep(0.05 if n == 1 else 0.01)
        return [SpeakerTurn("Speaker 1", f"window{n}")]

    async def generate_notes(self, transcript_text, agent_id=None, duration_s: float = 0.0):
        return Notes(summary="sum", decisions=[], open_questions=[])

    async def extract(self, transcript_text, agent_id=None):
        return Entities(action_items=[], people=[], dates=[], topics=["t"])

    async def embed(self, texts):
        return [[1.0, 0.0]]


def make_client(tmp_path):
    app.state.store = Store(str(tmp_path / "live.db"))
    app.state.router = WindowRouter()
    return TestClient(app)


def test_transcript_appears_before_the_meeting_is_stopped(tmp_path):
    client = make_client(tmp_path)
    silence = b"\x00\x00" * (api.SAMPLE_RATE * 10)   # exactly one window

    with client.websocket_connect("/ws/device") as ws:
        ws.send_text('{"agent": "standup"}')
        mid = ws.receive_json()["id"]

        ws.send_bytes(silence)
        ws.send_bytes(silence)
        # Nudge the event loop so the window tasks get to run while the socket
        # is still open - this is the whole point of live transcription.
        for _ in range(40):
            client.get("/healthz")

        mid_stream = client.get(f"/meetings/{mid}").json()
        ws.send_text('{"event": "stop"}')

    assert mid_stream["transcript"], "transcript should exist before stop"


def test_windows_are_stored_in_order_even_when_they_finish_out_of_order(tmp_path):
    client = make_client(tmp_path)
    silence = b"\x00\x00" * (api.SAMPLE_RATE * 10)

    with client.websocket_connect("/ws/device") as ws:
        ws.send_text('{"agent": "standup"}')
        mid = ws.receive_json()["id"]
        for _ in range(3):
            ws.send_bytes(silence)
        for _ in range(60):
            client.get("/healthz")
        ws.send_text('{"event": "stop"}')

    m = client.get(f"/meetings/{mid}").json()
    texts = [t["text"] for t in m["transcript"]]
    # Window 1 is deliberately the slowest, so a naive append would put it last.
    assert texts == sorted(texts), f"windows out of order: {texts}"


def test_partial_window_is_not_transcribed_live(tmp_path):
    client = make_client(tmp_path)
    half = b"\x00\x00" * (api.SAMPLE_RATE * 4)   # under the 10s window

    with client.websocket_connect("/ws/device") as ws:
        ws.send_text('{"agent": "standup"}')
        mid = ws.receive_json()["id"]
        ws.send_bytes(half)
        for _ in range(20):
            client.get("/healthz")
        m = client.get(f"/meetings/{mid}").json()
        ws.send_text('{"event": "stop"}')

    assert not m["transcript"], "should wait for a full window"
