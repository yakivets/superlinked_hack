import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.inference import get_router
from app.main import app
from app.store import Store

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.live
def test_full_flow_live(tmp_path):
    app.state.store = Store(str(tmp_path / "e2e.db"))
    app.state.router = get_router()

    # Must use TestClient as a context manager: it keeps one persistent
    # portal/event loop alive for the whole "with" block (matching a real
    # uvicorn process). Without "with", Starlette opens and tears down a
    # fresh event loop per request, which cancels the asyncio.create_task
    # background pipeline kicked off by /meetings/upload before it can
    # finish a real (multi-second) network call.
    with TestClient(app) as client:
        ids = []
        for name, title in [("meeting_a.wav", "Sprint planning"), ("meeting_b.wav", "Payments update")]:
            wav = (FIXTURES / name).read_bytes()
            r = client.post("/meetings/upload", files={"file": (name, wav, "audio/wav")}, data={"title": title})
            assert r.status_code == 202
            ids.append(r.json()["id"])

        deadline = time.time() + 300
        for mid in ids:
            while time.time() < deadline:
                m = client.get(f"/meetings/{mid}").json()
                if m["status"] in ("done", "error"):
                    break
                time.sleep(3)
            assert m["status"] == "done", m.get("error")
            assert len(m["transcript"]) >= 2, "diarization should find multiple turns"
            assert m["notes"]["summary"]

        r = client.get("/search", params={"q": "payment bugs"})
        assert r.json()["results"], "search should return results"

        r = client.post("/synthesis", json={"question": "What was decided about shipping the onboarding flow?"})
        body = r.json()
        assert "onday" in body["answer"] or "ship" in body["answer"].lower()
        assert body["sources"]

        g = client.get("/graph").json()
        assert len(g["nodes"]) == 2
