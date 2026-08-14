"""Missing signals must not be scored as evidence against relatedness."""

from app import relatedness as rel


def m(topics=(), people=()):
    return {"entities": {"topics": list(topics), "people": list(people)}}


V = [1.0, 0.0]


def test_identical_meetings_reach_one_even_with_no_people():
    assert rel.score_pair(m(["billing"]), m(["billing"]), V, V, 0.5)["score"] == 1.0


def test_identical_meetings_reach_one_with_no_entities_at_all():
    assert rel.score_pair(m(), m(), V, V, 0.5)["score"] == 1.0


def test_people_still_count_when_both_meetings_have_them():
    same = rel.score_pair(m(["billing"], ["alice"]), m(["billing"], ["alice"]), V, V, 0.5)
    differing = rel.score_pair(m(["billing"], ["alice"]), m(["billing"], ["bob"]), V, V, 0.5)
    assert same["score"] > differing["score"]


def test_one_sided_entities_are_ignored_rather_than_penalised():
    # Only one meeting named anyone: that is missing evidence, not disagreement.
    one_sided = rel.score_pair(m(["billing"], ["alice"]), m(["billing"]), V, V, 0.5)
    neither = rel.score_pair(m(["billing"]), m(["billing"]), V, V, 0.5)
    assert one_sided["score"] == neither["score"]


def test_disagreeing_topics_do_pull_the_score_down():
    agree = rel.score_pair(m(["billing"]), m(["billing"]), V, V, 0.5)
    disagree = rel.score_pair(m(["billing"]), m(["logistics"]), V, V, 0.5)
    assert disagree["score"] < agree["score"]
