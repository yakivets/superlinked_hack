import pytest

from app.models import (
    ActionItem,
    Entities,
    Notes,
    SpeakerTurn,
    parse_json_block,
    parse_speaker_turns,
)


def test_parse_speaker_turns_basic():
    raw = "Speaker 1: Hello team.\nSpeaker 2: Hi there.\nSpeaker 1: Let's start."
    turns = parse_speaker_turns(raw)
    assert turns == [
        SpeakerTurn("Speaker 1", "Hello team."),
        SpeakerTurn("Speaker 2", "Hi there."),
        SpeakerTurn("Speaker 1", "Let's start."),
    ]


def test_parse_speaker_turns_folds_continuations():
    raw = "Speaker 1: First line\nstill first speaker\nSpeaker 2: Reply"
    turns = parse_speaker_turns(raw)
    assert turns[0].text == "First line still first speaker"
    assert turns[1] == SpeakerTurn("Speaker 2", "Reply")


def test_parse_speaker_turns_no_labels():
    # Undiarized output used to be attributed to "Speaker 1", which made a
    # failed diarization look identical to a genuine one-person meeting - the
    # reason a two-person recording appeared as one speaker.
    turns = parse_speaker_turns("just a plain transcript")
    assert turns == [SpeakerTurn("Unlabelled", "just a plain transcript")]


def test_parse_json_block_with_fences():
    raw = 'Here you go:\n```json\n{"summary": "s", "decisions": [], "open_questions": []}\n```'
    assert parse_json_block(raw)["summary"] == "s"


def test_parse_json_block_bare():
    assert parse_json_block('{"a": 1}') == {"a": 1}


def test_notes_roundtrip():
    n = Notes(summary="s", decisions=["d"], open_questions=["q"])
    assert Notes.from_dict(n.to_dict()) == n


def test_entities_roundtrip():
    e = Entities(
        action_items=[ActionItem(text="fix bug", owner="Speaker 2")],
        people=["Sarah"],
        dates=["Monday"],
        topics=["payments"],
    )
    assert Entities.from_dict(e.to_dict()) == e


def test_parse_json_block_no_json_raises_valueerror():
    with pytest.raises(ValueError, match="no JSON object"):
        parse_json_block("just plain text with no braces")


def test_parse_json_block_with_stray_braces_extracts_valid_json():
    raw = 'The schema is {like this} but the real answer is {"a": 1}'
    result = parse_json_block(raw)
    assert result == {"a": 1}
