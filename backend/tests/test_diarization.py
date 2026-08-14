"""Speaker parsing and audio conditioning.

From a real failure: a two-person recording came back as a single "Speaker 1"
turn containing the whole conversation.
"""

import numpy as np

from app import audio
from app.models import parse_speaker_turns


# --- parsing ---------------------------------------------------------------

def test_plain_labels_parse():
    turns = parse_speaker_turns("Speaker 1: hello\nSpeaker 2: hi there")
    assert [(t.speaker, t.text) for t in turns] == [
        ("Speaker 1", "hello"), ("Speaker 2", "hi there")
    ]


def test_underscored_and_uppercase_labels_are_accepted():
    turns = parse_speaker_turns("SPEAKER_1: hello\nSPEAKER_2: hi")
    assert [t.speaker for t in turns] == ["Speaker 1", "Speaker 2"]


def test_markdown_bold_labels_are_accepted():
    turns = parse_speaker_turns("**Speaker 1:** hello\n**Speaker 2:** hi")
    assert [t.speaker for t in turns] == ["Speaker 1", "Speaker 2"]


def test_letter_labels_become_numbered_speakers():
    turns = parse_speaker_turns("Speaker A: hello\nSpeaker B: hi")
    assert [t.speaker for t in turns] == ["Speaker 1", "Speaker 2"]


def test_the_same_voice_keeps_one_label_however_it_is_written():
    turns = parse_speaker_turns("Speaker 1: a\nSPEAKER_1: b\n**Speaker 1**: c")
    assert {t.speaker for t in turns} == {"Speaker 1"}


def test_unlabelled_output_is_not_asserted_to_be_speaker_one():
    # The bug: undiarized text was silently attributed to Speaker 1, which made
    # a failed diarization indistinguishable from a one-person meeting.
    turns = parse_speaker_turns("we talked about the payment bug and shipped it")
    assert turns[0].speaker == "Unlabelled"


def test_continuation_lines_join_the_previous_turn():
    turns = parse_speaker_turns("Speaker 1: hello\nand also this\nSpeaker 2: hi")
    assert turns[0].text == "hello and also this"
    assert len(turns) == 2


def test_blank_lines_are_ignored():
    assert len(parse_speaker_turns("Speaker 1: a\n\n\nSpeaker 2: b")) == 2


# --- audio conditioning ----------------------------------------------------

def quiet_wav(peak=0.05, seconds=1.0, rate=16000):
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    tone = np.sin(2 * np.pi * 220 * t) * peak
    return audio.write_wav(tone * 32767.0, rate)


def test_measure_reports_level_and_length():
    m = audio.measure(quiet_wav(peak=0.05, seconds=2.0))
    assert 0.04 < m["peak"] < 0.06
    assert m["seconds"] == 2.0


def test_a_quiet_recording_is_lifted():
    before = audio.measure(quiet_wav(peak=0.05))
    after = audio.measure(audio.normalize(quiet_wav(peak=0.05)))
    assert after["peak"] > before["peak"] * 10


def test_normalising_does_not_clip():
    assert audio.measure(audio.normalize(quiet_wav(peak=0.05)))["peak"] <= 1.0


def test_an_already_loud_recording_is_left_alone():
    loud = quiet_wav(peak=0.99)
    assert audio.normalize(loud) == loud


def test_silence_is_not_amplified_into_noise():
    silence = audio.write_wav(np.zeros(16000), 16000)
    assert audio.normalize(silence) == silence


def test_unreadable_audio_is_returned_unchanged():
    assert audio.normalize(b"not a wav") == b"not a wav"
    assert audio.measure(b"not a wav") == {}
