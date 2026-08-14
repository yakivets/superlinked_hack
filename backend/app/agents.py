"""Agent profiles.

An agent decides how a meeting is understood: which SIE model writes the notes,
what the model is told it is listening to, and which entity labels matter. The
device picks one with its rotary encoder before recording starts.

Model ids are the ones verified live against SIE on 2026-08-14. `Qwen3.6-27B`
is the heavier reasoning model, `Qwen3.5-4B` the fast default; the
`:long-context` variants exist for long meetings.
"""

from dataclasses import dataclass, field

FAST_MODEL = "Qwen/Qwen3.5-4B"
DEEP_MODEL = "Qwen/Qwen3.6-27B"
FAST_LONG = "Qwen/Qwen3.5-4B:long-context"
DEEP_LONG = "Qwen/Qwen3.6-27B:long-context"

# Above this, a meeting is long enough that context window matters more than
# raw model size.
LONG_MEETING_S = 15 * 60


@dataclass(frozen=True)
class Agent:
    id: str
    name: str          # short enough for the 160x80 display
    context: str       # prepended to notes/extraction prompts
    notes_model: str
    long_model: str
    labels: list[str] = field(default_factory=list)

    def model_for(self, duration_s: float) -> str:
        return self.long_model if duration_s >= LONG_MEETING_S else self.notes_model


AGENTS: dict[str, Agent] = {
    "general": Agent(
        id="general",
        name="General",
        context="This is a general work meeting.",
        notes_model=FAST_MODEL,
        long_model=FAST_LONG,
        labels=["task", "person", "date", "topic"],
    ),
    "fintech": Agent(
        id="fintech",
        name="Fintech",
        context=(
            "This is a finance meeting. Pay close attention to figures, currencies, "
            "time periods and any regulatory or compliance obligation. Never round or "
            "invent a number: if a figure is unclear in the transcript, say so rather "
            "than guessing. Treat commitments about money or deadlines as decisions."
        ),
        notes_model=DEEP_MODEL,      # numbers and compliance need real reasoning
        long_model=DEEP_LONG,
        labels=["amount", "metric", "risk", "counterparty", "deadline", "person"],
    ),
    "engineering": Agent(
        id="engineering",
        name="Engineering",
        context=(
            "This is an engineering meeting. Track bugs, incidents, services, "
            "deployments, pull requests and technical decisions. Record who owns each "
            "piece of work and any blocking dependency between them."
        ),
        notes_model=FAST_MODEL,
        long_model=FAST_LONG,
        labels=["bug", "service", "owner", "deploy", "decision", "dependency"],
    ),
    "standup": Agent(
        id="standup",
        name="Standup",
        context=(
            "This is a short daily standup. Keep the summary to a few lines. What "
            "matters is what each person did, what they will do next, and what is "
            "blocking them. Ignore small talk."
        ),
        notes_model=FAST_MODEL,
        long_model=FAST_MODEL,       # standups are short by definition
        labels=["blocker", "owner", "status"],
    ),
    "sales": Agent(
        id="sales",
        name="Sales",
        context=(
            "This is a sales or client call. Track objections raised, pricing and "
            "scope discussion, competitors mentioned, and what happens next. Treat any "
            "commitment about price, timeline or scope as a decision. An objection "
            "nobody answered is an open question, not a decision."
        ),
        notes_model=FAST_MODEL,
        long_model=FAST_LONG,
        labels=["objection", "price", "competitor", "next_step", "decision_maker", "budget"],
    ),
    "interview": Agent(
        id="interview",
        name="Interview",
        context=(
            "This is a candidate interview. Summarise the evidence for and against the "
            "candidate: skills actually demonstrated, relevant experience, and concerns "
            "raised. Never credit a skill that was only claimed rather than shown, and "
            "do not state a hiring recommendation the interviewers did not make."
        ),
        notes_model=DEEP_MODEL,      # judgement about people needs real reasoning
        long_model=DEEP_LONG,
        labels=["skill", "experience", "concern", "strength", "recommendation"],
    ),
    "legal": Agent(
        id="legal",
        name="Legal",
        context=(
            "This is a legal or contract discussion. Record obligations exactly as "
            "stated, along with which party owes them and by when. Never invent or "
            "tighten an obligation, and if a term is left ambiguous say so rather than "
            "resolving it yourself."
        ),
        notes_model=DEEP_MODEL,      # precision matters more than latency here
        long_model=DEEP_LONG,
        labels=["obligation", "party", "clause", "deadline", "liability", "condition"],
    ),
}

DEFAULT_AGENT = "general"

# Stable order, so the device's encoder and the dashboard agree on the list.
# Mirrored in firmware/ui.cpp - the two MUST stay in sync.
AGENT_ORDER = ["general", "fintech", "engineering", "standup", "sales", "interview", "legal"]


def get_agent(agent_id: str | None) -> Agent:
    return AGENTS.get(agent_id or DEFAULT_AGENT, AGENTS[DEFAULT_AGENT])
