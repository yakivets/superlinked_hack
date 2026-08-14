"""Per-meeting RAG chat.

Answers a question about one meeting, using that meeting plus the meetings it is
connected to in the similarity graph. Every step runs on SIE: `encode` for the
question and the passages, `score` to rerank, `generate` for the answer.

Retrieval is passage-level rather than whole-meeting, so answers can cite the
specific turn they came from and long meetings do not blow the context window.
"""

from app import relatedness, routing_log
from app.agents import get_agent
from app.search import cosine

# Roughly a few speaker turns; small enough to cite, big enough to carry context.
CHUNK_CHARS = 700
MAX_RELATED = 4
CANDIDATES = 24             # embedded candidates handed to the reranker
TOP_PASSAGES = 8            # passages that actually reach the model

CHAT_PROMPT = """{context_intro}

Answer the question using ONLY the meeting excerpts below. Cite the meeting title in brackets when you use it, like [Weekly sync]. If the excerpts do not contain the answer, say so plainly rather than guessing.

{history}Question: {question}

Excerpts:
{passages}"""

# Passage embeddings are stable for a finished meeting, so they are computed
# once and reused across questions. Cleared implicitly on restart.
_cache: dict[str, list[tuple[dict, list[float]]]] = {}


def chunk_meeting(meeting: dict) -> list[dict]:
    """Split a meeting into citable passages."""
    passages: list[dict] = []
    title = meeting["title"]

    notes = meeting.get("notes") or {}
    if notes.get("summary"):
        passages.append({"meeting_id": meeting["id"], "title": title,
                         "kind": "summary", "text": notes["summary"]})

    buf: list[str] = []
    size = 0
    for turn in meeting.get("transcript") or []:
        line = f"{turn['speaker']}: {turn['text']}"
        if size + len(line) > CHUNK_CHARS and buf:
            passages.append({"meeting_id": meeting["id"], "title": title,
                             "kind": "transcript", "text": "\n".join(buf)})
            buf, size = [], 0
        buf.append(line)
        size += len(line)
    if buf:
        passages.append({"meeting_id": meeting["id"], "title": title,
                         "kind": "transcript", "text": "\n".join(buf)})

    return passages


def related_meeting_ids(store, meeting_id: str, limit: int = MAX_RELATED) -> list[str]:
    """Meetings linked to this one, strongest first.

    Deliberately the same scoring the graph uses: what the chat reads from and
    what the graph draws must never disagree.
    """
    embeddings = store.all_embeddings()
    meetings = {mid: store.get_meeting(mid) for mid, _ in embeddings}
    return relatedness.related_to(meetings, embeddings, meeting_id, limit)


async def _passages_with_vectors(store, router, meeting_id: str):
    if meeting_id in _cache:
        return _cache[meeting_id]

    meeting = store.get_meeting(meeting_id)
    if not meeting:
        return []
    passages = chunk_meeting(meeting)
    if not passages:
        return []

    vectors = await router.embed([p["text"] for p in passages])
    _cache[meeting_id] = list(zip(passages, vectors))
    return _cache[meeting_id]


async def answer(store, router, meeting_id: str, question: str,
                 history: list[dict] | None = None) -> dict:
    meeting = store.get_meeting(meeting_id)
    if not meeting:
        return {"answer": "That meeting does not exist.", "sources": [], "related": []}

    related = related_meeting_ids(store, meeting_id)

    pool: list[tuple[dict, list[float]]] = []
    for mid in [meeting_id, *related]:
        pool.extend(await _passages_with_vectors(store, router, mid))

    if not pool:
        return {"answer": "This meeting has no transcript yet.", "sources": [],
                "related": related}

    qvec = (await router.embed([question]))[0]
    ranked = sorted(pool, key=lambda pv: cosine(qvec, pv[1]), reverse=True)
    candidates = [p for p, _ in ranked[:CANDIDATES]]

    # Rerank the shortlist: embedding similarity is a coarse filter, the
    # cross-encoder decides what actually answers the question.
    scores = await router.rerank(question, [c["text"] for c in candidates])
    if scores:
        order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
        candidates = [candidates[i] for i in order]
    top = candidates[:TOP_PASSAGES]

    passages_text = "\n\n".join(
        f"[{p['title']}] ({p['kind']})\n{p['text']}" for p in top
    )
    turns = "".join(
        f"{h['role']}: {h['content']}\n" for h in (history or [])[-6:]
    )
    agent = get_agent(meeting.get("agent"))
    prompt = CHAT_PROMPT.format(
        context_intro=f"{agent.context} You are answering questions about the "
                      f"meeting \"{meeting['title']}\" and meetings related to it.",
        history=f"Earlier in this conversation:\n{turns}\n" if turns else "",
        question=question,
        passages=passages_text,
    )

    model = agent.model_for(meeting.get("duration_s") or 0.0)
    with routing_log.timed("chat", "sie", model, agent=agent.id,
                           passages=len(top), related=len(related)):
        text = await router.chat_sie(model, prompt)

    used = []
    for p in top:
        entry = {"id": p["meeting_id"], "title": p["title"]}
        if entry not in used:
            used.append(entry)

    return {
        "answer": text,
        "sources": used,
        "related": [{"id": m, "title": store.get_meeting(m)["title"]} for m in related],
    }


def invalidate(meeting_id: str) -> None:
    _cache.pop(meeting_id, None)
