"""Audio conditioning before speech recognition.

A PDM mic on a table picks up two people at very different levels: whoever is
nearer is loud, the other is close to the noise floor. Diarization then tends to
collapse - the quiet speaker is transcribed but not recognised as a separate
voice, or missed entirely.

Peak normalisation costs almost nothing and lifts the quieter speaker into a
range the model can work with.
"""

import io
import wave

import numpy as np

TARGET_PEAK = 0.89          # ~ -1 dBFS, leaves headroom against clipping
MIN_PEAK_TO_BOTHER = 0.95   # already loud enough
SILENCE_FLOOR = 1e-4        # below this it is silence, not a quiet speaker


def read_wav(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        frames = w.readframes(w.getnframes())
        rate = w.getframerate()
    return np.frombuffer(frames, dtype=np.int16), rate


def write_wav(samples: np.ndarray, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.astype(np.int16).tobytes())
    return buf.getvalue()


def measure(wav_bytes: bytes) -> dict:
    """Peak and RMS as fractions of full scale - useful for diagnosing a mic."""
    try:
        samples, rate = read_wav(wav_bytes)
    except Exception:
        return {}
    if samples.size == 0:
        return {"peak": 0.0, "rms": 0.0, "seconds": 0.0}

    scaled = samples.astype(np.float32) / 32768.0
    return {
        "peak": round(float(np.abs(scaled).max()), 4),
        "rms": round(float(np.sqrt(np.mean(scaled ** 2))), 4),
        "seconds": round(samples.size / rate, 1),
    }


def normalize(wav_bytes: bytes) -> bytes:
    """Peak-normalise a mono 16-bit WAV. Returns the input unchanged if there is
    nothing to gain or the audio cannot be read."""
    try:
        samples, rate = read_wav(wav_bytes)
    except Exception:
        return wav_bytes
    if samples.size == 0:
        return wav_bytes

    scaled = samples.astype(np.float32) / 32768.0
    peak = float(np.abs(scaled).max())
    if peak < SILENCE_FLOOR or peak >= MIN_PEAK_TO_BOTHER:
        return wav_bytes

    boosted = np.clip(scaled * (TARGET_PEAK / peak), -1.0, 1.0)
    return write_wav(boosted * 32767.0, rate)
