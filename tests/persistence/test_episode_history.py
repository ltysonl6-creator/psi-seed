"""P-012 Episode Traceability."""


def test_p012_episode_retains_developmental_graph(backend):
    trigger = backend.append_event({
        "event_type": "episode_trigger",
        "payload": {"reason": "test"},
    })

    episode = backend.create_episode(
        trigger_event_ref=trigger["id"],
    )

    belief = backend.create_belief(
        proposition="episode-linked belief",
        confidence=0.5,
    )

    backend.link_episode(
        episode["id"],
        belief_refs=[belief["id"]],
        event_refs=[trigger["id"]],
    )

    loaded = backend.get(episode["id"])

    assert loaded["trigger_event_ref"] == trigger["id"], (
        "P-012 VIOLATION: episode trigger event is not traceable."
    )
    assert belief["id"] in loaded["belief_refs"], (
        "P-012 VIOLATION: episode belief reference is not traceable."
    )
    assert trigger["id"] in loaded["event_refs"], (
        "P-012 VIOLATION: episode event reference is not traceable."
    )
