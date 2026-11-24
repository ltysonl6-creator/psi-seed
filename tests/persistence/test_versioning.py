"""P-003 Monotonic Version and P-006 Explicit Revision."""


def test_p003_versions_increase_monotonically(backend):
    create = backend.create_belief
    revise = backend.revise_belief
    history = backend.get_history

    record = create(
        proposition="version test",
        confidence=0.5,
    )
    v1 = record["version"]

    revise(record["id"], {"confidence": 0.6})
    revise(record["id"], {"confidence": 0.7})

    versions = [r["version"] for r in history(record["id"])]
    assert versions == sorted(set(versions)), (
        "P-003 VIOLATION: versions are not strictly increasing and unique."
    )
    assert versions[0] == v1
    assert versions[-1] > v1


def test_p006_state_change_has_explicit_revision(backend):
    record = backend.create_belief(
        proposition="revision test",
        confidence=0.5,
    )

    backend.revise_belief(record["id"], {"confidence": 0.8})
    history = backend.get_history(record["id"])

    assert len(history) >= 2, (
        "P-006 VIOLATION: a state change did not produce an explicit "
        "historical revision."
    )
    assert history[-1]["version"] > history[-2]["version"]
