"""P-014 No Orphaned Critical References and P-015 Deterministic Reconstruction."""


def test_p014_critical_references_resolve(backend):
    report = backend.validate_references()

    assert report["orphaned"] == [], (
        "P-014 VIOLATION: authoritative persistence references are orphaned: "
        f"{report['orphaned']!r}"
    )


def test_p015_identical_history_reconstructs_equivalent_state(backend):
    backend.create_belief(
        proposition="deterministic reconstruction test",
        confidence=0.6,
    )

    history = backend.export_authoritative_history()

    state_a = backend.reconstruct_from_history(history)
    state_b = backend.reconstruct_from_history(history)

    assert state_a == state_b, (
        "P-015 VIOLATION: identical persisted history produced different "
        "authoritative reconstructed state."
    )
