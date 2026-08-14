"""Topic matching and speaker-label filtering.

Both come from real failures: every pair shared "Speaker 1", and meetings about
the same subject scored 0.000 topic overlap because one said "payment bugs" and
the other "payment bug fixes".
"""

from app import relatedness as rel


def m(topics=(), people=()):
    return {"entities": {"topics": list(topics), "people": list(people)}}


V = [1.0, 0.0]


def test_speaker_labels_are_not_treated_as_people():
    topics, people = rel._tags(m(people=["Speaker 1", "Speaker 2", "Alice"]))
    assert people == {"alice"}


def test_speaker_labels_do_not_appear_as_shared():
    d = rel.score_pair(m(["x"], ["Speaker 1"]), m(["y"], ["Speaker 1"]), V, V, 0.5)
    assert d["shared"] == []


def test_real_names_still_count_as_shared():
    d = rel.score_pair(m(["x"], ["Alice"]), m(["x"], ["Alice"]), V, V, 0.5)
    assert "alice" in d["shared"]


def test_topics_match_on_content_words_not_exact_strings():
    # The real pair that scored 0.000 before.
    assert rel.topic_similarity({"payment bugs"}, {"payment bug fixes"}) > 0


def test_plurals_do_not_break_matching():
    assert rel.topic_similarity({"payment bug"}, {"payment bugs"}) == 1.0


def test_unrelated_topics_still_score_zero():
    assert rel.topic_similarity({"office coffee"}, {"payment bugs"}) == 0.0


def test_stopwords_do_not_manufacture_overlap():
    # "the new X" vs "the new Y" share only stopwords.
    assert rel.topic_similarity({"the new onboarding"}, {"the new billing"}) == 0.0


def test_shared_labels_report_near_matches():
    d = rel.score_pair(m(["payment bugs"]), m(["payment bug fixes"]), V, V, 0.5)
    assert d["shared"] == ["payment bugs"]


def test_short_real_topics_are_not_discarded():
    # "AI", "UX" and "Q3" are genuine topics, not noise.
    assert rel.topic_similarity({"AI roadmap"}, {"AI hiring"}) > 0
    assert rel.topic_similarity({"Q3 budget"}, {"Q3 planning"}) > 0
    assert rel.topic_similarity({"UX review"}, {"UX debt"}) > 0


def test_single_characters_are_still_noise():
    assert rel.topic_similarity({"a b c"}, {"a b d"}) == 0.0


def test_empty_topics_are_safe():
    assert rel.topic_similarity(set(), {"x"}) == 0.0
    assert rel.topic_similarity({"x"}, set()) == 0.0
