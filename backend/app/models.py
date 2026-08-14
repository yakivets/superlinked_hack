import json
import re
from dataclasses import asdict, dataclass


@dataclass
class SpeakerTurn:
    speaker: str
    text: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class Notes:
    summary: str
    decisions: list
    open_questions: list

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(
            summary=d.get("summary", ""),
            decisions=list(d.get("decisions", [])),
            open_questions=list(d.get("open_questions", [])),
        )


@dataclass
class ActionItem:
    text: str
    owner: str | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(text=d.get("text", ""), owner=d.get("owner"))


@dataclass
class Entities:
    action_items: list
    people: list
    dates: list
    topics: list

    def to_dict(self):
        return {
            "action_items": [a.to_dict() for a in self.action_items],
            "people": self.people,
            "dates": self.dates,
            "topics": self.topics,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            action_items=[ActionItem.from_dict(a) for a in d.get("action_items", [])],
            people=list(d.get("people", [])),
            dates=list(d.get("dates", [])),
            topics=list(d.get("topics", [])),
        )


_SPEAKER_RE = re.compile(r"^\s*(Speaker \d+)\s*:\s*(.*)$")


def parse_speaker_turns(raw: str) -> list[SpeakerTurn]:
    turns: list[SpeakerTurn] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        m = _SPEAKER_RE.match(line)
        if m:
            turns.append(SpeakerTurn(m.group(1), m.group(2).strip()))
        elif turns:
            turns[-1].text = (turns[-1].text + " " + line.strip()).strip()
        else:
            turns.append(SpeakerTurn("Speaker 1", line.strip()))
    return turns


def parse_json_block(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object in: {text[:120]!r}")
    return json.loads(text[start : end + 1])
