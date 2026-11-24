"""Concurrency support for persistence invariants.

These tests intentionally require the backend to expose atomic operations.
They are not timing-based 'hope it races' tests; the backend must provide
deterministic concurrency probes.
"""


def test_concurrent_revision_does_not_create_duplicate_versions(backend):
    result = backend.concurrent_revision_probe(
        entity_type="belief",
        worker_count=8,
        revisions_per_worker=1,
    )

    assert result["duplicate_versions"] == [], (
        "P-003 VIOLATION: concurrent revisions produced duplicate versions."
    )
    assert result["lost_updates"] == [], (
        "P-003/P-004 VIOLATION: concurrent revisions lost historical updates."
    )


def test_concurrent_event_append_does_not_overwrite_events(backend):
    result = backend.concurrent_event_append_probe(
        worker_count=8,
        events_per_worker=10,
    )

    assert result["overwritten_events"] == [], (
        "P-005 VIOLATION: concurrent event writes overwrote historical events."
    )
    assert result["missing_events"] == [], (
        "P-005 VIOLATION: concurrent event writes lost committed events."
    )
