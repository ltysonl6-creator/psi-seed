"""P-004 Historical Preservation and P-005 Event Immutability."""


def test_p004_prior_state_remains_reconstructable(backend):
    record = backend.create_belief(
        proposition="historical preservation test",
        confidence=0.2,
    )
    original = dict(record)

    backend.revise_belief(record["id"], {"confidence": 0.9})

    history = backend.get_history(record["id"])
    first = next(r for r in history if r["version"] == original["version"])

    assert first["confidence"] == original["confidence"], (
        "P-004 VIOLATION: prior state was overwritten instead of preserved."
    )


def test_p005_committed_event_is_immutable(backend):
    event = backend.append_event({
        "event_type": "p005_test",
        "payload": {"value": "original"},
    })
    event_id = event["id"]

    backend.attempt_event_update(
        event_id,
        {"payload": {"value": "mutated"}},
    )

    stored = backend.get_event(event_id)
    assert stored["payload"]["value"] == "original", (
        "P-005 VIOLATION: committed historical event was mutated."
    )
