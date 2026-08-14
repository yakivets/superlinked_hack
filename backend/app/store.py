import json
import sqlite3
import uuid
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    duration_s REAL,
    status TEXT NOT NULL,
    error TEXT,
    transcript_json TEXT,
    notes_json TEXT,
    entities_json TEXT,
    embedding_json TEXT,
    agent TEXT
);
"""

# Databases created before agents existed lack the column; add it in place
# rather than forcing anyone to delete their meetings.
MIGRATIONS = [
    ("agent", "ALTER TABLE meetings ADD COLUMN agent TEXT"),
]


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path
        with self._conn() as c:
            c.executescript(SCHEMA)
            existing = {r["name"] for r in c.execute("PRAGMA table_info(meetings)")}
            for column, ddl in MIGRATIONS:
                if column not in existing:
                    c.execute(ddl)

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_meeting(self, title: str, agent: str | None = None) -> str:
        mid = uuid.uuid4().hex
        with self._conn() as c:
            c.execute(
                "INSERT INTO meetings (id, title, created_at, status, agent) "
                "VALUES (?, ?, ?, ?, ?)",
                (mid, title, datetime.now(timezone.utc).isoformat(), "processing", agent),
            )
        return mid

    def update_meeting(self, mid, *, status=None, transcript=None, notes=None,
                       entities=None, embedding=None, duration_s=None, error=None,
                       agent=None):
        sets, vals = [], []
        if agent is not None:
            sets.append("agent = ?"); vals.append(agent)
        if status is not None:
            sets.append("status = ?"); vals.append(status)
        if transcript is not None:
            sets.append("transcript_json = ?")
            vals.append(json.dumps([t.to_dict() for t in transcript]))
        if notes is not None:
            sets.append("notes_json = ?"); vals.append(json.dumps(notes.to_dict()))
        if entities is not None:
            sets.append("entities_json = ?"); vals.append(json.dumps(entities.to_dict()))
        if embedding is not None:
            sets.append("embedding_json = ?"); vals.append(json.dumps(embedding))
        if duration_s is not None:
            sets.append("duration_s = ?"); vals.append(duration_s)
        if error is not None:
            sets.append("error = ?"); vals.append(error)
        if not sets:
            return
        vals.append(mid)
        with self._conn() as c:
            c.execute(f"UPDATE meetings SET {', '.join(sets)} WHERE id = ?", vals)

    def _row_to_dict(self, row, heavy: bool):
        d = {
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "duration_s": row["duration_s"],
            "status": row["status"],
            "error": row["error"],
            "agent": row["agent"] if "agent" in row.keys() else None,
            "notes": json.loads(row["notes_json"]) if row["notes_json"] else None,
            "entities": json.loads(row["entities_json"]) if row["entities_json"] else None,
        }
        if heavy:
            d["transcript"] = json.loads(row["transcript_json"]) if row["transcript_json"] else []
            d["embedding"] = json.loads(row["embedding_json"]) if row["embedding_json"] else None
        return d

    def get_meeting(self, mid):
        with self._conn() as c:
            row = c.execute("SELECT * FROM meetings WHERE id = ?", (mid,)).fetchone()
        return self._row_to_dict(row, heavy=True) if row else None

    def list_meetings(self):
        with self._conn() as c:
            rows = c.execute("SELECT * FROM meetings ORDER BY created_at DESC").fetchall()
        return [self._row_to_dict(r, heavy=False) for r in rows]

    def all_embeddings(self):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, embedding_json FROM meetings "
                "WHERE status = 'done' AND embedding_json IS NOT NULL"
            ).fetchall()
        return [(r["id"], json.loads(r["embedding_json"])) for r in rows]
