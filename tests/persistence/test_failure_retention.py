"""P-008 Failure Retention and P-010 Rollback Preservation."""


def test_p008_failure_survives_state_transition_and_reload(backend):
    modification = backend.create_self_modification(
        target={"component": "test", "identifier": "p008"},
        proposed_change={"description": "intentional test failure"},
        rationale="contract test",
        expected_effect="failure retention",
    )

    backend.record_outcome(
        modification["id"],
        expected="success",
        observed="failure",
        result="failure",
        failure_class="implementation",
    )

    backend.set_modification_status(modification["id"], "failed")
    backend.reload()

    failures = backend.get_failures_for(modification["id"])

    assert failures, (
        "P-008 VIOLATION: recorded failure disappeared after persistence/reload."
    )


def test_p010_rollback_preserves_modification_and_failure_history(backend):
    modification = backend.create_self_modification(
        target={"component": "test", "identifier": "p010"},
        proposed_change={"description": "rollback test"},
        rationale="contract test",
        expected_effect="temporary change",
    )

    backend.execute_modification(modification["id"])
    backend.record_outcome(
        modification["id"],
        expected="success",
        observed="failure",
        result="failure",
        failure_class="implementation",
    )
    backend.rollback_modification(modification["id"])

    stored = backend.get(modification["id"])
    failures = backend.get_failures_for(modification["id"])

    assert stored is not None, (
        "P-010 VIOLATION: rollback erased the modification record."
    )
    assert failures, (
        "P-010 VIOLATION: rollback erased the modification's failure history."
    )
