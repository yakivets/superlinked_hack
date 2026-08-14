"""Relatedness scoring: calibration, entity overlap, and hairball prevention."""

import math

from app import relatedness as rel


def vec(*xs):
    return list(xs)


def meeting(topics=(), people=()):
    return {"entities": {"topics": list(topics), "people": list(people)}}


# --- jaccard ---------------------------------------------------------------

def test_jaccard_basics():
    assert rel.jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert rel.jaccard({"a"}, {"b"}) == 0.0
    assert rel.jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert rel.jaccard(set(), {"a"}) == 0.0      # empty must not divide by zero


# --- calibration -----------------------------------------------------------

def test_a_typical_pair_scores_zero_not_the_baseline():
    # The whole point: 0.5 raw cosine is what unrelated meetings look like.
    assert rel.calibrated_semantic(0.5, 0.5) == 0.0


def test_below_baseline_is_clamped_not_negative():
    assert rel.calibrated_semantic(0.1, 0.5) == 0.0


def test_identical_stays_one():
    assert rel.calibrated_semantic(1.0, 0.5) == 1.0


def test_calibration_is_linear_between_baseline_and_one():
    # Halfway from baseline to identical should read as 0.5.
    assert math.isclose(rel.calibrated_semantic(0.75, 0.5), 0.5, abs_tol=1e-9)


def test_raw_cosine_that_used_to_pass_the_old_threshold_now_scores_low():
    # 0.45 raw cleared the old `>= 0.4` cut-off and produced the hairball.
    assert rel.calibrated_semantic(0.45, 0.5) == 0.0


# --- corpus baseline -------------------------------------------------------

def test_small_corpus_uses_the_assumed_baseline():
    # With two meetings there is no distribution to measure.
    assert rel.corpus_baseline([vec(1, 0), vec(0, 1)]) == rel.ASSUMED_BASELINE


def test_baseline_is_measured_once_the_corpus_is_big_enough():
    # Six mutually orthogonal-ish vectors: a typical pair is dissimilar, so the
    # measured baseline is clamped to the floor rather than the assumed value.
    vectors = [
        vec(1, 0, 0, 0, 0, 0), vec(0, 1, 0, 0, 0, 0), vec(0, 0, 1, 0, 0, 0),
        vec(0, 0, 0, 1, 0, 0), vec(0, 0, 0, 0, 1, 0), vec(0, 0, 0, 0, 0, 1),
    ]
    assert rel.corpus_baseline(vectors) == rel.BASELINE_BOUNDS[0]


def test_baseline_is_clamped_when_every_meeting_is_near_identical():
    vectors = [vec(1, 0)] * 6
    assert rel.corpus_baseline(vectors) <= rel.BASELINE_BOUNDS[1]


# --- pair scoring ----------------------------------------------------------

def test_identical_meetings_score_one():
    d = rel.score_pair(meeting(["billing"]), meeting(["billing"]), vec(1, 0), vec(1, 0), 0.5)
    assert d["score"] == 1.0


def test_unrelated_meetings_score_zero():
    d = rel.score_pair(meeting(["hiring"]), meeting(["catering"]), vec(1, 0), vec(0, 1), 0.5)
    assert d["score"] == 0.0


def test_shared_topics_lift_a_borderline_pair():
    without = rel.score_pair(meeting(["hiring"]), meeting(["catering"]), vec(1, 0.5), vec(1, 0), 0.5)
    with_shared = rel.score_pair(meeting(["billing", "runway"]), meeting(["billing", "runway"]),
                                 vec(1, 0.5), vec(1, 0), 0.5)
    assert with_shared["score"] > without["score"]


def test_shared_tags_are_reported_for_the_ui():
    d = rel.score_pair(meeting(["Payment Bugs", "x"]), meeting(["payment bugs", "y"]),
                       vec(1, 0), vec(1, 0), 0.5)
    # Case-insensitive, so the UI does not show near-duplicate tags.
    assert d["shared"] == ["payment bugs"]


def test_scoring_survives_meetings_with_no_entities():
    d = rel.score_pair({}, {}, vec(1, 0), vec(1, 0), 0.5)
    assert d["score"] > 0


# --- edges -----------------------------------------------------------------

def test_threshold_excludes_weak_pairs():
    meetings = {"a": meeting(["hiring"]), "b": meeting(["catering"])}
    embeddings = [("a", vec(1, 0)), ("b", vec(0.55, 0.45))]
    assert rel.build_edges(meetings, embeddings, threshold=0.7) == []


def test_strong_pairs_are_kept_and_sorted_strongest_first():
    meetings = {"a": meeting(["hiring"]), "b": meeting(["hiring"]), "c": meeting(["hiring"])}
    embeddings = [("a", vec(1, 0)), ("b", vec(1, 0)), ("c", vec(0.98, 0.02))]
    edges = rel.build_edges(meetings, embeddings, threshold=0.5)
    assert edges
    assert edges == sorted(edges, key=lambda e: e["weight"], reverse=True)


def test_the_old_algorithm_would_hairball_where_this_one_does_not():
    # Six meetings that are all vaguely similar - the shape that produced 77
    # edges across 14 nodes with a raw 0.4 cut-off.
    meetings = {str(i): meeting([f"subject{i}"]) for i in range(6)}
    embeddings = [(str(i), vec(1.0, 0.1 * i)) for i in range(6)]

    edges = rel.build_edges(meetings, embeddings, threshold=0.7)
    complete = len(embeddings) * (len(embeddings) - 1) / 2
    assert len(edges) < complete, "still connecting everything to everything"


def test_related_to_returns_strongest_first_and_excludes_self():
    meetings = {k: meeting(["hiring"]) for k in ("a", "b", "c")}
    embeddings = [("a", vec(1, 0)), ("b", vec(1, 0)), ("c", vec(0, 1))]
    out = rel.related_to(meetings, embeddings, "a", limit=5, threshold=0.5)
    assert "a" not in out
    assert out and out[0] == "b"


def test_related_to_handles_an_unknown_meeting():
    assert rel.related_to({}, [], "nope", limit=5) == []
