"""How related two meetings are, on a scale where the number means something.

Raw cosine between meeting embeddings is not a usable "percent related": every
meeting is English, in a meeting register, often about the same product, so two
entirely unrelated meetings still score around 0.5. Thresholding raw cosine at
0.4 connected almost every pair - a hairball that tells the reader nothing.

Two corrections:

1. **Calibrate against the corpus.** Measure what an unrelated pair actually
   scores here, and rescale so that baseline becomes 0 and identical stays 1.
   0.7 then means "70% of the way from a typical pair to the same meeting".

2. **Use more than the vector.** Meetings that genuinely belong together tend to
   share extracted topics and people. Entity overlap is independent evidence,
   and it is also what lets the UI explain *why* two meetings are linked.
"""

from app.search import cosine

# What an unrelated pair scores with this embedder. Used until the corpus is
# large enough to measure its own baseline.
ASSUMED_BASELINE = 0.45
MIN_CORPUS_FOR_BASELINE = 5

# A baseline outside this range means something odd (near-duplicate corpus, or
# one meeting repeated); clamp rather than produce nonsense scores.
BASELINE_BOUNDS = (0.20, 0.90)

# Signals combine as independent evidence rather than a weighted average: an
# interview and a budget review that both concern the same named person are
# genuinely related even though their content is not similar at all, and an
# average lets the one strong signal be drowned by the weak ones. Each signal
# has a ceiling on how much it can carry alone.
CAP_SEMANTIC = 1.00      # near-identical content is sufficient on its own
CAP_PEOPLE = 0.85        # a shared full name is strong, if not quite conclusive
CAP_TOPICS = 0.70        # topics are generic enough to need corroboration

# A shared full name identifies a person; a shared first name might be two
# different Alexes.
FULL_NAME_EVIDENCE = 1.0
GIVEN_NAME_EVIDENCE = 0.5

# Measured on real meetings: a re-upload of the same recording scores ~0.97, two
# meetings in one thread ~0.68, an interview and a hiring decision about the same
# named person ~0.86, unrelated meetings ~0. Tunable per request via
# GET /graph?threshold=
DEFAULT_THRESHOLD = 0.50


import re

# "Speaker 1" is a diarization label, not a person. Every meeting has one, so
# treating them as shared people links every pair to every other pair.
SPEAKER_LABEL = re.compile(r"^speaker\s*\d+$", re.I)

STOPWORDS = {"the", "a", "an", "of", "and", "for", "to", "in", "on", "new"}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tokens(phrase: str) -> set[str]:
    """Content words of a topic, lightly singularised.

    Topics are free text from a model, so the same subject comes back as
    "payment bugs" in one meeting and "payment bug fixes" in the next. Matching
    whole strings scores those as completely unrelated; matching content words
    finds the overlap that is really there.
    """
    words = re.findall(r"[a-z0-9]+", phrase.lower())
    out = set()
    for w in words:
        # Keep two-character words: "AI", "UX" and "Q3" are real topics. Only
        # single characters are noise.
        if w in STOPWORDS or len(w) < 2:
            continue
        out.add(w[:-1] if w.endswith("s") and len(w) > 3 else w)
    return out


def people_evidence(a: set[str], b: set[str]) -> float:
    """How strongly a shared cast of people links two meetings.

    Deliberately not Jaccard. One meeting naming only the candidate and another
    naming the candidate plus three colleagues still points at the same person;
    dividing by the union would score that as weak.
    """
    shared = a & b
    if not shared:
        return 0.0
    if any(" " in name for name in shared):
        return FULL_NAME_EVIDENCE
    return GIVEN_NAME_EVIDENCE


def topic_similarity(a: set[str], b: set[str]) -> float:
    """Overlap between two topic sets, compared on content words."""
    if not a or not b:
        return 0.0
    tokens_a = set().union(*(_tokens(t) for t in a)) if a else set()
    tokens_b = set().union(*(_tokens(t) for t in b)) if b else set()
    return jaccard(tokens_a, tokens_b)


def _median(values: list[float]) -> float:
    if not values:
        return ASSUMED_BASELINE
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def corpus_baseline(vectors: list[list[float]]) -> float:
    """What a typical pair scores in this corpus - i.e. what "unrelated" means here.

    The median is deliberate: a mean would be dragged up by genuinely related
    clusters, which is exactly the signal we are trying to keep.
    """
    if len(vectors) < MIN_CORPUS_FOR_BASELINE:
        return ASSUMED_BASELINE

    sims = [
        cosine(vectors[i], vectors[j])
        for i in range(len(vectors))
        for j in range(i + 1, len(vectors))
    ]
    lo, hi = BASELINE_BOUNDS
    return min(max(_median(sims), lo), hi)


def calibrated_semantic(raw: float, baseline: float) -> float:
    """Rescale so a typical pair is 0 and an identical pair is 1."""
    if raw <= baseline:
        return 0.0
    span = 1.0 - baseline
    return min(max((raw - baseline) / span, 0.0), 1.0) if span > 0 else 0.0


def _tags(meeting: dict) -> tuple[set, set]:
    entities = meeting.get("entities") or {}
    topics = {t.lower().strip() for t in entities.get("topics", []) if t}
    people = {
        p.lower().strip() for p in entities.get("people", [])
        if p and not SPEAKER_LABEL.match(p.strip())
    }
    return topics, people


def _shared_labels(topics_a: set, topics_b: set,
                   people_a: set, people_b: set) -> list[str]:
    """What the two meetings visibly have in common, for the UI to show.

    Exact matches would miss "payment bugs" against "payment bug fixes", which
    is precisely the overlap a reader wants to see, so topics count as shared
    when their content words meet.
    """
    shared = set(people_a & people_b)
    for topic in topics_a:
        tokens = _tokens(topic)
        if any(tokens & _tokens(other) for other in topics_b):
            shared.add(topic)
    return sorted(shared)


def score_pair(meeting_a: dict, meeting_b: dict,
               vec_a: list[float], vec_b: list[float],
               baseline: float) -> dict:
    """Relatedness of two meetings, with the reasons that produced it."""
    semantic = calibrated_semantic(cosine(vec_a, vec_b), baseline)

    topics_a, people_a = _tags(meeting_a)
    topics_b, people_b = _tags(meeting_b)
    topic_overlap = topic_similarity(topics_a, topics_b)
    people_overlap = people_evidence(people_a, people_b)

    # Noisy-OR: any signal can carry the pair on its own, up to its ceiling, and
    # a signal that is simply absent contributes nothing rather than counting
    # against. Meetings that name nobody are not penalised for it.
    remaining = 1.0
    for cap, value in (
        (CAP_SEMANTIC, semantic),
        (CAP_PEOPLE, people_overlap),
        (CAP_TOPICS, topic_overlap),
    ):
        remaining *= 1.0 - cap * value
    score = 1.0 - remaining
    return {
        "score": round(score, 3),
        "semantic": round(semantic, 3),
        "topic_overlap": round(topic_overlap, 3),
        "shared": _shared_labels(topics_a, topics_b, people_a, people_b),
    }


def build_edges(meetings: dict[str, dict], embeddings: list[tuple[str, list]],
                threshold: float = DEFAULT_THRESHOLD) -> list[dict]:
    """Edges between meetings that clear the relatedness threshold."""
    baseline = corpus_baseline([v for _, v in embeddings])

    edges = []
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            id_a, vec_a = embeddings[i]
            id_b, vec_b = embeddings[j]
            if id_a not in meetings or id_b not in meetings:
                continue

            detail = score_pair(meetings[id_a], meetings[id_b], vec_a, vec_b, baseline)
            if detail["score"] < threshold:
                continue
            edges.append({
                "source": id_a,
                "target": id_b,
                "weight": detail["score"],
                "semantic": detail["semantic"],
                "shared": detail["shared"],
            })

    edges.sort(key=lambda e: e["weight"], reverse=True)
    return edges


def related_to(meetings: dict[str, dict], embeddings: list[tuple[str, list]],
               meeting_id: str, limit: int,
               threshold: float = DEFAULT_THRESHOLD) -> list[str]:
    """Meetings related to one meeting, strongest first."""
    by_id = dict(embeddings)
    target = by_id.get(meeting_id)
    if target is None or meeting_id not in meetings:
        return []

    baseline = corpus_baseline([v for _, v in embeddings])
    scored = []
    for mid, vec in embeddings:
        if mid == meeting_id or mid not in meetings:
            continue
        detail = score_pair(meetings[meeting_id], meetings[mid], target, vec, baseline)
        if detail["score"] >= threshold:
            scored.append((mid, detail["score"]))

    scored.sort(key=lambda t: t[1], reverse=True)
    return [mid for mid, _ in scored[:limit]]
