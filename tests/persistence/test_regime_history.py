"""P-011 Regime Traceability."""


def test_p011_regime_change_preserves_context_and_evidence(backend):
    previous = backend.create_regime(
        label="regime-A",
        description="prior test regime",
    )
    new = backend.create_regime(
        label="regime-B",
        description="new test regime",
    )
    event = backend.append_event({
        "event_type": "regime_detection",
        "payload": {"reason": "test"},
    })

    change = backend.create_regime_change(
        previous_regime=previous["id"],
        new_regime=new["id"],
        detection_event_ref=event["id"],
        evidence_refs=["p011-evidence"],
    )

    loaded = backend.get(change["id"])

    assert loaded["previous_regime"], (
        "P-011 VIOLATION: previous regime was lost."
    )
    assert loaded["new_regime"], (
        "P-011 VIOLATION: new regime was lost."
    )
    assert loaded["detection_event_ref"] == event["id"], (
        "P-011 VIOLATION: detection event reference was lost."
    )
    assert "p011-evidence" in loaded["evidence_refs"], (
        "P-011 VIOLATION: regime evidence reference was lost."
    )
