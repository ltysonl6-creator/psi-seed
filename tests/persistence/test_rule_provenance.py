"""P-013 Rule Traceability."""


def test_p013_rule_remains_linked_to_originating_episode_and_evidence(backend):
    episode = backend.create_episode(
        trigger_event_ref=backend.append_event({
            "event_type": "rule_test_trigger",
            "payload": {},
        })["id"]
    )

    rule = backend.create_developmental_rule(
        rule="Test failures should remain retrievable.",
        source_episode_refs=[episode["id"]],
        evidence_refs=["p013-evidence"],
    )

    loaded = backend.get(rule["id"])

    assert episode["id"] in loaded["source_episode_refs"], (
        "P-013 VIOLATION: developmental rule lost its source episode."
    )
    assert "p013-evidence" in loaded["evidence_refs"], (
        "P-013 VIOLATION: developmental rule lost its evidence provenance."
    )


def test_p013_superseded_rule_remains_retrievable(backend):
    episode = backend.create_episode(
        trigger_event_ref=backend.append_event({
            "event_type": "supersession_test",
            "payload": {},
        })["id"]
    )

    old_rule = backend.create_developmental_rule(
        rule="old rule",
        source_episode_refs=[episode["id"]],
        evidence_refs=["old-evidence"],
    )

    new_rule = backend.create_developmental_rule(
        rule="new rule",
        source_episode_refs=[episode["id"]],
        evidence_refs=["new-evidence"],
    )

    backend.supersede_rule(old_rule["id"], new_rule["id"])

    old_loaded = backend.get(old_rule["id"])
    assert old_loaded is not None, (
        "P-013 VIOLATION: superseding a rule erased the historical rule."
    )
    assert old_loaded["status"] == "superseded"
