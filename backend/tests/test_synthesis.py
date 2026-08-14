from app.models import ActionItem, Entities, Notes, SpeakerTurn
from app.store import Store
from app.synthesis import build_graph, synthesize


class ChatRouter:
    def __init__(self):
        self.last_prompt = None

    async def embed(self, texts):
        return [[1.0, 0.0]]

    async def rerank(self, query, docs):
        return None

    async def chat(self, model, prompt, max_tokens=2000):
        assert model == "qwen3.8-max"
        self.last_prompt = prompt
        return "They decided to ship Monday."


def seed(store, title, embedding, topics, people, action_items=None, transcript=None):
    mid = store.create_meeting(title)
    kwargs = dict(
        status="done",
        embedding=embedding,
        notes=Notes(summary=f"{title} summary", decisions=["ship"], open_questions=[]),
        entities=Entities(action_items=action_items or [], people=people, dates=[], topics=topics),
    )
    if transcript is not None:
        kwargs["transcript"] = transcript
    store.update_meeting(mid, **kwargs)
    return mid


async def test_synthesize_includes_sources(tmp_path):
    store = Store(str(tmp_path / "x.db"))
    router = ChatRouter()
    a = seed(store, "sprint planning", [1.0, 0.0], ["release"], ["Sarah"])
    out = await synthesize(store, router, "what did we decide about shipping?")
    assert out["answer"] == "They decided to ship Monday."
    assert out["sources"][0]["id"] == a
    assert "sprint planning" in router.last_prompt


async def test_synthesize_prompt_includes_transcript_actions_and_truncation(tmp_path):
    store = Store(str(tmp_path / "w.db"))
    router = ChatRouter()
    head = "START-MARKER " + "x" * 4100
    tail_marker = "TAIL-MARKER-SHOULD-BE-TRUNCATED"
    transcript = [SpeakerTurn("Speaker 1", head + tail_marker)]
    action_items = [ActionItem(text="fix payments", owner="Speaker 2")]
    seed(
        store,
        "payments sync",
        [1.0, 0.0],
        ["payments"],
        ["Sarah"],
        action_items=action_items,
        transcript=transcript,
    )
    await synthesize(store, router, "what's the plan for payments?")
    prompt = router.last_prompt
    assert "START-MARKER" in prompt
    assert tail_marker not in prompt
    assert "fix payments" in prompt
    assert "Speaker 2" in prompt
    assert "ship" in prompt
    assert "payments sync summary" in prompt


async def test_synthesize_empty_store(tmp_path):
    store = Store(str(tmp_path / "y.db"))
    out = await synthesize(store, ChatRouter(), "anything?")
    assert out["sources"] == []


def test_build_graph_edges_above_threshold(tmp_path):
    store = Store(str(tmp_path / "z.db"))
    a = seed(store, "a", [1.0, 0.0], ["payments"], ["Sarah"])
    b = seed(store, "b", [0.9, 0.1], ["payments"], ["John"])
    c = seed(store, "c", [0.0, 1.0], ["lunch"], [])
    g = build_graph(store)
    assert {n["id"] for n in g["nodes"]} == {a, b, c}
    pairs = {(e["source"], e["target"]) for e in g["edges"]}
    assert (a, b) in pairs or (b, a) in pairs
    ab = next(e for e in g["edges"] if {e["source"], e["target"]} == {a, b})
    assert "payments" in ab["shared"]
    assert not any({e["source"], e["target"]} == {a, c} for e in g["edges"])
