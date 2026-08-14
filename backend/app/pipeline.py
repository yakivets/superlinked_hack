import asyncio
import io
import wave


def wav_duration_s(wav_bytes: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 0.0


async def process_meeting(store, router, meeting_id: str, wav_bytes: bytes) -> None:
    try:
        store.update_meeting(meeting_id, duration_s=wav_duration_s(wav_bytes))
        turns = await router.transcribe(wav_bytes)
        store.update_meeting(meeting_id, status="transcribed", transcript=turns)

        transcript_text = "\n".join(f"{t.speaker}: {t.text}" for t in turns)
        notes, entities = await asyncio.gather(
            router.generate_notes(transcript_text),
            router.extract(transcript_text),
        )
        store.update_meeting(meeting_id, notes=notes, entities=entities)

        meeting = store.get_meeting(meeting_id)
        embed_text = f"{meeting['title']}\n{notes.summary}\n{transcript_text}"
        vectors = await router.embed([embed_text])
        store.update_meeting(meeting_id, status="done", embedding=vectors[0])
    except Exception as exc:
        store.update_meeting(meeting_id, status="error", error=str(exc))
