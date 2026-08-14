"""Prove the agent routing and the SIE/Alibaba split are real.

Runs the SAME audio through several agents and prints which model actually
served every call. Use it to check the system yourself, and to show a judge
that the routing is doing something rather than being a label.

    python verify_sie.py                    # against localhost:8000
    python verify_sie.py --port 8001
    python verify_sie.py --agents fintech standup
"""

import argparse
import sys
import time

import httpx

DEFAULT_WAV = "backend/fixtures/meeting_a.wav"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--wav", default=DEFAULT_WAV)
    ap.add_argument("--agents", nargs="*", default=["fintech", "engineering"])
    args = ap.parse_args()

    base = f"http://{args.host}:{args.port}"

    try:
        httpx.get(f"{base}/healthz", timeout=5)
    except Exception:
        print(f"No backend on {base}.")
        print("Start it with:  cd backend && python -m uvicorn app.main:app --port 8000")
        print("(live_server.py is a different program and has no agents.)")
        return 1

    print("=" * 68)
    print("AGENT ROSTER")
    print("=" * 68)
    for a in httpx.get(f"{base}/agents", timeout=30).json()["agents"]:
        print(f"  {a['id']:<12} notes -> {a['notes_model']}")

    for agent in args.agents:
        print()
        print("=" * 68)
        print(f"SAME AUDIO, AGENT = {agent.upper()}")
        print("=" * 68)
        with open(args.wav, "rb") as f:
            r = httpx.post(f"{base}/meetings/upload",
                           files={"file": ("m.wav", f, "audio/wav")},
                           data={"title": f"verify {agent}", "agent": agent},
                           timeout=60)
        mid = r.json()["id"]

        m = {}
        for _ in range(120):
            time.sleep(2)
            m = httpx.get(f"{base}/meetings/{mid}", timeout=30).json()
            if m["status"] in ("done", "error"):
                break

        if m.get("status") != "done":
            print(f"  FAILED: {m.get('status')} {m.get('error')}")
            continue

        print("  summary:", (m["notes"].get("summary") or "")[:180])
        items = (m["entities"] or {}).get("action_items", [])
        print(f"  action items ({len(items)}):")
        for it in items:
            print(f"    - {it.get('text')}   owner={it.get('owner')}")
        print("  topics:", (m["entities"] or {}).get("topics"))

    print()
    print("=" * 68)
    print("WHO SERVED WHAT")
    print("=" * 68)
    routing = httpx.get(f"{base}/routing", timeout=30).json()

    for provider, s in routing["summary"].items():
        models = ", ".join(f"{k} x{v}" for k, v in s["models"].items())
        print(f"  {provider:<6} {s['calls']:>3} calls  {s['ms']:>9.0f}ms   {models}")

    sie = routing["summary"].get("sie", {}).get("calls", 0)
    cloud = routing["summary"].get("cloud", {}).get("calls", 0)
    print(f"\n  SIE:Alibaba call ratio = {sie}:{cloud}")

    print("\n  recent calls:")
    for c in routing["calls"][:14]:
        print(f"    {c['task']:<11} {c['provider']:<6} {c['model']:<26} "
              f"{c['ms']:>8.0f}ms  agent={c.get('agent', '-')}")

    if sie == 0:
        print("\n  WARNING: nothing went through SIE. Check PROVIDER_* in .env.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
