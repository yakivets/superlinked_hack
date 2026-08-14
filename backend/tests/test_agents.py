from app.agents import AGENT_ORDER, AGENTS, DEFAULT_AGENT, LONG_MEETING_S, get_agent


def test_unknown_agent_falls_back_to_default():
    assert get_agent("nonsense").id == DEFAULT_AGENT
    assert get_agent(None).id == DEFAULT_AGENT


def test_agent_order_covers_every_agent():
    assert set(AGENT_ORDER) == set(AGENTS)


def test_fintech_uses_the_heavier_model_than_engineering():
    # The routing story depends on these genuinely differing.
    assert get_agent("fintech").notes_model != get_agent("engineering").notes_model


def test_long_meetings_escalate_to_long_context_model():
    a = get_agent("fintech")
    assert a.model_for(60) == a.notes_model
    assert a.model_for(LONG_MEETING_S + 1) == a.long_model


def test_standup_stays_on_one_model_because_standups_are_short():
    a = get_agent("standup")
    assert a.model_for(LONG_MEETING_S + 1) == a.notes_model


def test_every_agent_has_labels_and_context():
    for agent in AGENTS.values():
        assert agent.labels, agent.id
        assert agent.context.strip(), agent.id
        assert len(agent.name) <= 12, "must fit the 160x80 display"
