"""P-001 Stable Identity and P-002 Unique Identity."""

import pytest
from .conftest import require_method


def test_p001_identity_survives_update_and_reload(backend):
    create = require_method(backend, "create_belief")
    load = require_method(backend, "get")
    update = require_method(backend, "update_belief")

    record = create(
        proposition="test proposition",
        confidence=0.5,
    )
    original_id = record["id"]

    update(original_id, {"confidence": 0.7})
    reloaded = load(original_id)

    assert reloaded["id"] == original_id, (
        "P-001 VIOLATION: updating a belief changed its stable identity."
    )


def test_p002_duplicate_identity_cannot_create_two_authoritative_records(backend):
    create = require_method(backend, "create_record")
    get = require_method(backend, "get")

    record = create({
        "id": "p002-duplicate-test",
        "entity_type": "belief",
        "proposition": "duplicate identity test",
        "confidence": 0.5,
    })

    with pytest.raises(Exception):
        create({
            "id": record["id"],
            "entity_type": "belief",
            "proposition": "second authoritative record",
            "confidence": 0.9,
        })

    loaded = get(record["id"])
    assert loaded["id"] == record["id"]
