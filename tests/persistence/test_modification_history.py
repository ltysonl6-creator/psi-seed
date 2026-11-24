"""P-009 Modification Traceability."""


def test_p009_modification_lifecycle_is_traceable(backend):
    modification = backend.create_self_modification(
        target={"component": "retrieval", "identifier": "test-target"},
        proposed_change={"description": "change retrieval behavior"},
        rationale="test traceability",
        expected_effect="changed retrieval",
    )

    backend.evaluate_modification(modification["id"])
    backend.approve_modification(modification["id"])
    backend.execute_modification(modification["id"])
    backend.record_outcome(
        modification["id"],
        expected="changed retrieval",
        observed="changed retrieval",
        result="success",
    )

    record = backend.get(modification["id"])

    assert record["target"], "P-009 VIOLATION: target is not traceable."
    assert record["proposed_change"], (
        "P-009 VIOLATION: proposed change is not traceable."
    )
    assert record["rationale"], "P-009 VIOLATION: rationale is not traceable."
    assert record["expected_effect"], (
        "P-009 VIOLATION: expected effect is not traceable."
    )
    assert record["outcome_refs"], (
        "P-009 VIOLATION: outcome is not traceable."
    )
