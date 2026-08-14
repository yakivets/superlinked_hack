from app.models import ActionItem, Entities, Notes, SpeakerTurn
from app.store import Store


def make_store(tmp_path):
    return Store(str(tmp_path / "test.db"))


def test_create_and_get(tmp_path):
    s = make_store(tmp_path)
    mid = s.create_meeting("standup")
    m = s.get_meeting(mid)
    assert m["title"] == "standup"
    assert m["status"] == "processing"
    assert m["transcript"] == []
    assert m["notes"] is None


def test_update_full_lifecycle(tmp_path):
    s = make_store(tmp_path)
    mid = s.create_meeting("planning")
    s.update_meeting(
        mid,
        status="done",
        transcript=[SpeakerTurn("Speaker 1", "hi")],
        notes=Notes(summary="s", decisions=[], open_questions=[]),
        entities=Entities(action_items=[ActionItem("t", "Speaker 1")], people=[], dates=[], topics=["x"]),
        embedding=[0.1, 0.2],
        duration_s=12.5,
    )
    m = s.get_meeting(mid)
    assert m["status"] == "done"
    assert m["transcript"] == [{"speaker": "Speaker 1", "text": "hi"}]
    assert m["notes"]["summary"] == "s"
    assert m["entities"]["topics"] == ["x"]
    assert m["embedding"] == [0.1, 0.2]


def test_list_meetings_newest_first_no_heavy_fields(tmp_path):
    s = make_store(tmp_path)
    a = s.create_meeting("first")
    b = s.create_meeting("second")
    lst = s.list_meetings()
    assert [m["title"] for m in lst] == ["second", "first"]
    assert "embedding" not in lst[0] and "transcript" not in lst[0]


def test_all_embeddings_only_done(tmp_path):
    s = make_store(tmp_path)
    a = s.create_meeting("a")
    b = s.create_meeting("b")
    s.update_meeting(a, status="done", embedding=[1.0])
    out = s.all_embeddings()
    assert out == [(a, [1.0])]


def test_get_missing_returns_none(tmp_path):
    assert make_store(tmp_path).get_meeting("nope") is None
