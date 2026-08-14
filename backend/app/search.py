import math
from datetime import datetime, timezone

import numpy as np


def cosine(a, b) -> float:
    """Cosine similarity, 0.0 for anything incomparable.

    Vectors of different lengths come from different embedding models - switching
    providers leaves older rows behind at the old dimension. Those are not
    comparable at all, so they score 0 rather than raising: one stale row used to
    take down search, the graph and synthesis together. Use reembed.py to bring
    old rows onto the current model.
    """
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if va.shape != vb.shape or va.size == 0:
        return 0.0
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(va @ vb / denom) if denom else 0.0


def fusion_score(semantic: float, created_at_iso: str, query: str, topics, now=None) -> float:
    now = now or datetime.now(timezone.utc)
    created = datetime.fromisoformat(created_at_iso)
    age_days = max((now - created).total_seconds() / 86400, 0.0)
    recency = math.exp(-age_days / 7)
    words = [w for w in query.lower().split() if len(w) > 2]
    topic_blob = " ".join(t.lower() for t in topics)
    overlap = sum(1 for w in words if w in topic_blob) / len(words) if words else 0.0
    return 0.6 * semantic + 0.25 * recency + 0.15 * overlap


async def search_meetings(store, router, query: str, k: int = 5) -> list[dict]:
    embeddings = store.all_embeddings()
    if not embeddings:
        return []
    qvec = (await router.embed([query]))[0]
    scored = sorted(
        ((mid, cosine(qvec, vec)) for mid, vec in embeddings),
        key=lambda t: t[1],
        reverse=True,
    )[: 2 * k]

    meetings = [store.get_meeting(mid) for mid, _ in scored]
    semantics = [s for _, s in scored]
    docs = [f"{m['title']}. {(m['notes'] or {}).get('summary', '')}" for m in meetings]
    reranked = await router.rerank(query, docs)
    if reranked is not None:
        semantics = reranked

    results = []
    for m, sem in zip(meetings, semantics):
        topics = (m["entities"] or {}).get("topics", [])
        results.append(
            {
                "id": m["id"],
                "title": m["title"],
                "created_at": m["created_at"],
                "score": round(fusion_score(sem, m["created_at"], query, topics), 4),
                "summary": (m["notes"] or {}).get("summary", ""),
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:k]
