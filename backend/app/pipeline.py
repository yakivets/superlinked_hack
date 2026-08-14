import asyncio
import io
import wave

from app import routing_log


def wav_duration_s(wav_bytes: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 0.0


async def process_meeting(store, router, meeting_id: str, wav_bytes: bytes,
                          agent_id: str | None = None) -> None:
    try:
        duration_s = wav_duration_s(wav_bytes)
        store.update_meeting(meeting_id, duration_s=duration_s)

        with routing_log.timed("transcribe", "cloud", "qwen3.5-omni-flash",
                               duration_s=round(duration_s, 1)):
            turns = await router.transcribe(wav_bytes)
        store.update_meeting(meeting_id, status="transcribed", transcript=turns)

        transcript_text = "\n".join(f"{t.speaker}: {t.text}" for t in turns)
        # The agent decides which model writes the notes; extraction stays on the
        # fast model regardless, so these two genuinely differ per meeting.
        notes, entities = await asyncio.gather(
            router.generate_notes(transcript_text, agent_id, duration_s),
            router.extract(transcript_text, agent_id),
        )
        store.update_meeting(meeting_id, notes=notes, entities=entities)

        meeting = store.get_meeting(meeting_id)
        embed_text = f"{meeting['title']}\n{notes.summary}\n{transcript_text}"
        vectors = await router.embed([embed_text])
        store.update_meeting(meeting_id, status="done", embedding=vectors[0])
    except Exception as exc:
        store.update_meeting(meeting_id, status="error", error=str(exc))
