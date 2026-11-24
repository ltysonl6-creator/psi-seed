from contracts.constitutional_contract import (
    CONSTITUTION,
    CONSTITUTIONAL_INVARIANTS,
    CONSTITUTIONAL_STATUS,
    CONSTITUTION_VERSION,
    INVARIANT_TEXT,
)


def test_v1_constitution_is_frozen():
    assert CONSTITUTION_VERSION == "1.0"
    assert CONSTITUTIONAL_STATUS == "FROZEN"
    CONSTITUTION.assert_frozen()


def test_frozen_registry_has_stable_permanent_ids():
    assert CONSTITUTIONAL_INVARIANTS == (
        "C-001", "C-002", "C-003", "C-004",
        "C-005", "C-006", "C-007", "C-008",
        "C-009", "C-010", "C-011", "C-012",
    )
    assert set(INVARIANT_TEXT) == set(CONSTITUTIONAL_INVARIANTS)
    assert all(INVARIANT_TEXT[i] for i in CONSTITUTIONAL_INVARIANTS)


def test_freeze_does_not_equate_implementation_with_constitution():
    # This is intentionally an architectural assertion: implementation changes
    # may occur without changing the constitutional contract version.
    assert CONSTITUTION.version == "1.0"
    assert CONSTITUTION.status == "FROZEN"
