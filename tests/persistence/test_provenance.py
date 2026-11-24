"""P-007 Provenance Preservation."""


def test_p007_provenance_survives_persistence_and_reload(backend):
    record = backend.create_belief(
        proposition="provenance test",
        confidence=0.5,
        provenance={
            "source_type": "observation",
            "source_ref": "p007-test-source",
        },
    )

    backend.reload()
    loaded = backend.get(record["id"])

    provenance = loaded["provenance"]
    assert provenance["source_type"] == "observation", (
        "P-007 VIOLATION: source_type was not preserved."
    )
    assert provenance["source_ref"] == "p007-test-source", (
        "P-007 VIOLATION: source_ref was not preserved."
    )
