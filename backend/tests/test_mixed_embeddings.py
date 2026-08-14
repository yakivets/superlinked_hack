"""A meeting embedded by an older model must not break search or the graph.

This happened for real: switching PROVIDER_EMBED from cloud to SIE left two
1024d rows behind among 2560d ones, and `va @ vb` raised - taking down /search,
/graph and /synthesis together until the stale rows were re-embedded.
"""

from app.search import cosine
from app.synthesis import build_graph


class FakeStore:
    def __init__(self, embeddings):
        self._e = embeddings

    def all_embeddings(self):
        return self._e

    def get_meeting(self, mid):
        return {"id": mid, "title": f"m-{mid}", "entities": {"topics": ["t"]}}


def test_cosine_returns_zero_for_mismatched_dimensions():
    assert cosine([1.0] * 4, [1.0] * 8) == 0.0


def test_cosine_still_works_for_matching_dimensions():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert abs(cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_cosine_handles_empty_vectors():
    assert cosine([], []) == 0.0


def test_graph_survives_a_stale_embedding():
    graph = build_graph(FakeStore([
        ("a", [1.0] * 2560),
        ("b", [1.0] * 2560),
        ("legacy", [1.0] * 1024),   # left behind by the old model
    ]))
    ids = {n["id"] for n in graph["nodes"]}
    assert ids == {"a", "b", "legacy"}
    # a-b are identical so they must still link; nothing links to the stale row.
    assert any({e["source"], e["target"]} == {"a", "b"} for e in graph["edges"])
    assert all("legacy" not in (e["source"], e["target"]) for e in graph["edges"])
