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
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid JSON in fence: {e}") from e

    # Try to find a valid JSON object by scanning from each opening brace
    # and counting braces while respecting strings
    for i in range(len(text)):
        if text[i] == '{':
            brace_depth = 0
            in_string = False
            escape_next = False

            for j in range(i, len(text)):
                ch = text[j]

                if escape_next:
                    escape_next = False
                elif ch == '\\' and in_string:
                    escape_next = True
                elif ch == '"':
                    in_string = not in_string
                elif not in_string:
                    if ch == '{':
                        brace_depth += 1
                    elif ch == '}':
                        brace_depth -= 1
                        if brace_depth == 0:
                            # Found a complete JSON object
                            candidate = text[i:j+1]
                            try:
                                return json.loads(candidate)
                            except json.JSONDecodeError:
                                # This span didn't parse, continue searching
                                break

    # No valid JSON object found
    raise ValueError(f"no JSON object in: {text[:120]!r}")
