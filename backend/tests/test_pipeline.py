import io
import wave

from app.models import ActionItem, Entities, Notes, SpeakerTurn
from app.pipeline import process_meeting
from app.store import Store


class FakeRouter:
    def __init__(self, fail_transcribe=False):
        self.fail_transcribe = fail_transcribe
        self.seen_agent = None

    async def transcribe(self, wav_bytes):
        if self.fail_transcribe:
            raise RuntimeError("asr down")
        return [SpeakerTurn("Speaker 1", "we ship Monday")]

    async def generate_notes(self, transcript_text, agent_id=None, duration_s: float = 0.0):
        self.seen_agent = agent_id
        return Notes(summary="ship Monday", decisions=["ship Monday"], open_questions=[])

    async def extract(self, transcript_text, agent_id=None):
        return Entities(
            action_items=[ActionItem("ship", "Speaker 1")], people=[], dates=["Monday"], topics=["release"]
        )

    async def embed(self, texts):
        return [[0.5, 0.5] for _ in texts]


def tiny_wav(seconds=1.0):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


async def test_process_meeting_happy_path(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    mid = store.create_meeting("demo")
    await process_meeting(store, FakeRouter(), mid, tiny_wav(2.0))
    m = store.get_meeting(mid)
    assert m["status"] == "done"
    assert m["transcript"][0]["text"] == "we ship Monday"
    assert m["notes"]["summary"] == "ship Monday"
    assert m["entities"]["dates"] == ["Monday"]
    assert m["embedding"] == [0.5, 0.5]
    assert abs(m["duration_s"] - 2.0) < 0.01


async def test_process_meeting_error_path(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    mid = store.create_meeting("demo")
    await process_meeting(store, FakeRouter(fail_transcribe=True), mid, tiny_wav())
    m = store.get_meeting(mid)
    assert m["status"] == "error"
    assert "asr down" in m["error"]
