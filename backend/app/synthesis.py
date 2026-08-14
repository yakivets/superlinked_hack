from app import routing_log
from app import relatedness
from app.search import search_meetings

SYNTHESIS_PROMPT = """You are an assistant answering a question by reasoning across several past meetings. Use ONLY the meeting records below. Cite meetings by title when relevant. Answer concisely.

Question: {question}

{meetings}"""


def _meeting_block(m: dict) -> str:
    notes = m["notes"] or {}
    entities = m["entities"] or {}
    transcript = "\n".join(
        f"{t['speaker']}: {t['text']}" for t in m.get("transcript", [])
    )[:4000]
    actions = "; ".join(
        f"{a.get('text')} (owner: {a.get('owner')})" for a in entities.get("action_items", [])
    )
    return (
        f"## {m['title']} ({m['created_at'][:10]})\n"
        f"Summary: {notes.get('summary', '')}\n"
        f"Decisions: {'; '.join(notes.get('decisions', []))}\n"
        f"Action items: {actions}\n"
        f"Transcript:\n{transcript}\n"
    )


async def synthesize(store, router, question: str, k: int = 5) -> dict:
    hits = await search_meetings(store, router, question, k)
    if not hits:
        return {"answer": "No meetings recorded yet.", "sources": []}
    meetings = [store.get_meeting(h["id"]) for h in hits]
    prompt = SYNTHESIS_PROMPT.format(
        question=question, meetings="\n".join(_meeting_block(m) for m in meetings)
    )
    with routing_log.timed("synthesis", "cloud", "qwen3.8-max", meetings=len(meetings)):
        answer = await router.chat("qwen3.8-max", prompt)
    return {
        "answer": answer,
        "sources": [{"id": m["id"], "title": m["title"]} for m in meetings],
    }


def build_graph(store, threshold: float = relatedness.DEFAULT_THRESHOLD) -> dict:
    embeddings = store.all_embeddings()
    meetings = {mid: store.get_meeting(mid) for mid, _ in embeddings}
    nodes = [
        {
            "id": mid,
            "title": meetings[mid]["title"],
            "agent": meetings[mid].get("agent"),
            "topics": (meetings[mid].get("entities") or {}).get("topics", []),
        }
        for mid, _ in embeddings
    ]
    return {
        "nodes": nodes,
        "edges": relatedness.build_edges(meetings, embeddings, threshold),
        "threshold": threshold,
    }
