"""In-memory log of which model served which call.

The whole point of the routing story is that it is visible, so every inference
call records what it used. Bounded, in-process, lost on restart - that is fine,
it is a live view rather than a record.
"""

import time
from collections import deque
from datetime import datetime, timezone

MAX_ENTRIES = 200
_entries: deque = deque(maxlen=MAX_ENTRIES)


def record(task: str, provider: str, model: str, ms: float, **meta) -> None:
    _entries.appendleft({
        "at": datetime.now(timezone.utc).isoformat(),
        "task": task,
        "provider": provider,      # "sie" | "cloud"
        "model": model,
        "ms": round(ms, 1),
        **meta,
    })


class timed:
    """with timed("notes", "sie", model, agent="fintech"): ..."""

    def __init__(self, task: str, provider: str, model: str, **meta):
        self.task, self.provider, self.model, self.meta = task, provider, model, meta

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        record(self.task, self.provider, self.model,
               (time.perf_counter() - self.t0) * 1000, **self.meta)
        return False


def entries() -> list[dict]:
    return list(_entries)


def summary() -> dict:
    """Per-provider totals, so the dashboard can show the split at a glance."""
    out: dict[str, dict] = {}
    for e in _entries:
        row = out.setdefault(e["provider"], {"calls": 0, "ms": 0.0, "models": {}})
        row["calls"] += 1
        row["ms"] += e["ms"]
        row["models"][e["model"]] = row["models"].get(e["model"], 0) + 1
    for row in out.values():
        row["ms"] = round(row["ms"], 1)
    return out
