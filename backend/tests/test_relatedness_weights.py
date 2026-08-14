"""How signals combine.

From a real failure: an interview with Alex Smith and a hiring decision about
Alex Smith scored 0.078 and did not link. Their content is genuinely
dissimilar - the relationship is the shared person - and a weighted average let
that one strong signal be drowned by the weak ones.
"""

from app import relatedness as rel


def m(topics=(), people=()):
    return {"entities": {"topics": list(topics), "people": list(people)}}


SAME = [1.0, 0.0]
DIFFERENT = [0.0, 1.0]


# --- people evidence -------------------------------------------------------

def test_no_shared_people_is_no_evidence():
    assert rel.people_evidence({"alice smith"}, {"bob jones"}) == 0.0


def test_a_shared_full_name_is_strong_evidence():
    assert rel.people_evidence({"alex smith"}, {"alex smith", "mikito"}) == rel.FULL_NAME_EVIDENCE


def test_evidence_does_not_weaken_when_one_meeting_names_more_people():
    """The real case: one meeting named only the candidate, the other named the
    candidate plus colleagues. Jaccard scored that 1/3."""
    few = rel.people_evidence({"alex smith"}, {"alex smith"})
    many = rel.people_evidence({"alex smith"}, {"alex smith", "mikito", "oriol"})
    assert few == many


def test_a_shared_first_name_alone_is_weaker():
    assert rel.people_evidence({"alex"}, {"alex"}) < rel.people_evidence(
        {"alex smith"}, {"alex smith"})


# --- combination -----------------------------------------------------------

def test_a_shared_person_links_meetings_with_unrelated_content():
    d = rel.score_pair(m(["hiring"], ["alex smith"]), m(["finance"], ["alex smith"]),
                       SAME, DIFFERENT, 0.5)
    assert d["score"] >= rel.DEFAULT_THRESHOLD


def test_near_identical_content_links_without_any_shared_people():
    d = rel.score_pair(m(), m(), SAME, SAME, 0.5)
    assert d["score"] >= rel.DEFAULT_THRESHOLD


def test_nothing_in_common_scores_zero():
    d = rel.score_pair(m(["hiring"]), m(["catering"]), SAME, DIFFERENT, 0.5)
    assert d["score"] == 0.0


def test_a_shared_first_name_alone_does_not_link_unrelated_meetings():
    # Two different Alexes must not pull unrelated meetings together.
    d = rel.score_pair(m(["hiring"], ["alex"]), m(["catering"], ["alex"]),
                       SAME, DIFFERENT, 0.5)
    assert d["score"] < rel.DEFAULT_THRESHOLD


def test_missing_entities_are_not_counted_against_a_pair():
    with_people = rel.score_pair(m(["billing"], ["alice smith"]), m(["billing"]), SAME, SAME, 0.5)
    without = rel.score_pair(m(["billing"]), m(["billing"]), SAME, SAME, 0.5)
    assert with_people["score"] == without["score"]


def test_signals_reinforce_rather_than_average_out():
    only_topics = rel.score_pair(m(["billing"]), m(["billing"]), DIFFERENT, SAME, 0.5)
    topics_and_people = rel.score_pair(m(["billing"], ["alice smith"]),
                                       m(["billing"], ["alice smith"]),
                                       DIFFERENT, SAME, 0.5)
    assert topics_and_people["score"] > only_topics["score"]
