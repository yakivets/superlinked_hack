"""Re-embed meetings that are stuck on an old embedding model.

Switching PROVIDER_EMBED leaves older meetings at the previous model's
dimension. Those vectors are not comparable with the new ones, so the affected
meetings silently drop out of search, the similarity graph and synthesis.

    python reembed.py            # report only
    python reembed.py --apply    # re-embed the stale ones
"""

import argparse
import asyncio
from collections import Counter

from app.config import settings
from app.inference import get_router
from app.store import Store


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually re-embed")
    args = ap.parse_args()

    store = Store(settings.db_path)
    router = get_router()

    embs = store.all_embeddings()
    if not embs:
        print("no meetings with embeddings")
        return

    dims = Counter(len(v) for _, v in embs)
    print("dimensions in store:", dict(dims))

    # The current model decides what "correct" is, not the majority.
    probe = await router.embed(["dimension probe"])
    current = len(probe[0])
    print(f"current embedding model produces {current}d")

    stale = [mid for mid, v in embs if len(v) != current]
    if not stale:
        print("nothing to do - every meeting is on the current model")
        return

    print(f"{len(stale)} meeting(s) on an old model:")
    for mid in stale:
        m = store.get_meeting(mid)
        print(f"  {mid[:8]}  {m['created_at'][:19]}  {m['title']}")

    if not args.apply:
        print("\nre-run with --apply to fix")
        return

    for mid in stale:
        m = store.get_meeting(mid)
        transcript = "\n".join(
            f"{t['speaker']}: {t['text']}" for t in (m.get("transcript") or [])
        )
        summary = (m.get("notes") or {}).get("summary", "")
        text = f"{m['title']}\n{summary}\n{transcript}".strip()
        if not text:
            print(f"  {mid[:8]} has no text to embed, skipping")
            continue
        vec = (await router.embed([text]))[0]
        store.update_meeting(mid, embedding=vec)
        print(f"  {mid[:8]} re-embedded -> {len(vec)}d")

    print("done")


if __name__ == "__main__":
    asyncio.run(main())
