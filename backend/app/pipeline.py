import asyncio
import io
import wave

from app import agents, chat, routing_log

# Progress goes to stdout as well as the store: a meeting takes tens of seconds
# to process and an empty terminal is indistinguishable from a hung one.
def _log(msg: str) -> None:
    print(msg, flush=True)


# Titles the device and the upload form produce when nobody named the meeting.
# Anything else is a title a person chose, and is left alone.
PLACEHOLDER_TITLES = {"device meeting", "untitled meeting", "untitled", ""}

TITLE_PROMPT = """Give this meeting a short title: 3 to 6 words naming what it was actually about.

Rules: no quotation marks, no trailing full stop, no words like "meeting", "discussion" or "sync" unless the meeting was genuinely about scheduling one. Name the subject, not the format. Reply with the title alone.

{summary}

{transcript}"""

MAX_TITLE_CHARS = 80


def _clean_title(raw: str) -> str:
    title = (raw or "").strip().splitlines()[0] if raw and raw.strip() else ""
    title = title.strip().strip('"').strip("'").rstrip(".").strip()
    return title[:MAX_TITLE_CHARS]


async def generate_title(router, summary: str, transcript_text: str) -> str | None:
    """A title from what the meeting was about. None if it cannot be produced."""
    prompt = TITLE_PROMPT.format(summary=summary or "", transcript=transcript_text[:3000])
    try:
        with routing_log.timed("title", "sie", agents.FAST_MODEL):
            raw = await router.chat_sie(agents.FAST_MODEL, prompt, max_tokens=40)
    except Exception:
        return None      # a missing title must never fail the meeting
    title = _clean_title(raw)
    return title or None


def wav_duration_s(wav_bytes: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 0.0


async def process_meeting(store, router, meeting_id: str, wav_bytes: bytes,
                          agent_id: str | None = None) -> None:
    short_id = meeting_id[:8]
    try:
        duration_s = wav_duration_s(wav_bytes)
        store.update_meeting(meeting_id, duration_s=duration_s)
        _log(f"\n[{short_id}] agent={agent_id or 'general'} audio={duration_s:.1f}s "
             f"-> transcribing (this takes a while for long meetings)")

        with routing_log.timed("transcribe", "cloud", "qwen3.5-omni-flash",
                               duration_s=round(duration_s, 1)):
            turns = await router.transcribe(wav_bytes)
        store.update_meeting(meeting_id, status="transcribed", transcript=turns)

        _log(f"[{short_id}] transcript ({len(turns)} turns):")
        for t in turns:
            text = t.text if len(t.text) <= 300 else t.text[:300] + "..."
            _log(f"    {t.speaker}: {text}")

        transcript_text = "\n".join(f"{t.speaker}: {t.text}" for t in turns)
        # The agent decides which model writes the notes; extraction stays on the
        # fast model regardless, so these two genuinely differ per meeting.
        notes, entities = await asyncio.gather(
            router.generate_notes(transcript_text, agent_id, duration_s),
            router.extract(transcript_text, agent_id),
        )
        store.update_meeting(meeting_id, notes=notes, entities=entities)

        _log(f"[{short_id}] summary: {notes.summary[:200]}")
        for item in entities.action_items:
            _log(f"[{short_id}]   action: {item.text}  (owner: {item.owner or '-'})")

        meeting = store.get_meeting(meeting_id)

        # Title last: only now is there anything to name the meeting after. A
        # title someone typed is theirs, so only placeholders get replaced.
        if (meeting["title"] or "").strip().lower() in PLACEHOLDER_TITLES:
            title = await generate_title(router, notes.summary, transcript_text)
            if title:
                store.update_meeting(meeting_id, title=title)
                meeting = store.get_meeting(meeting_id)
                _log(f"[{short_id}] titled: {title}")

        embed_text = f"{meeting['title']}\n{notes.summary}\n{transcript_text}"
        vectors = await router.embed([embed_text])
        store.update_meeting(meeting_id, status="done", embedding=vectors[0])
        # The live pass cached passages from a partial transcript; drop them so
        # chat re-chunks the final one.
        chat.invalidate(meeting_id)
        _log(f"[{short_id}] done\n")
    except Exception as exc:
        store.update_meeting(meeting_id, status="error", error=str(exc))
        _log(f"[{short_id}] FAILED: {exc}\n")
