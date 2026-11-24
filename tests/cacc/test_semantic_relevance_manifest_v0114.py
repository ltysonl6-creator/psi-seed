from datetime import datetime, timezone

from psi_seed.persistence.sqlite.backend import SQLitePersistenceBackend
from contracts.semantic_relevance_manifest import (
    semantic_relevance_manifest,
    semantic_projection,
    validate_semantic_relevance_manifest,
)
from contracts.semantic_replay import semantic_interpretation


def ts():
    return datetime.now(timezone.utc).isoformat()


def make(db):
    e = db.create_record({
        "id": "e1", "entity_type": "belief", "status": "active",
        "created_at": ts(), "provenance": {}, "payload": {"value": "A"},
    })
    db.revise_entity(e["id"], {"value": "B"})
    return db.export_authoritative_history()


def test_manifest_is_machine_readable_and_fail_closed():
    m = semantic_relevance_manifest()
    assert m["manifest_id"] == "SRM-001"
    assert m["unknown_field_policy"] == "FAIL_CLOSED"
    assert m["sections"]["revisions"]["payload"] == "authoritative"


def test_known_history_has_valid_manifest(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    history = make(db)
    report = validate_semantic_relevance_manifest(history)
    assert report["valid"] is True
    assert report["issues"] == []
    db.close()


def test_unknown_authoritative_top_level_field_fails_closed(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    history = make(db)
    history["future_authoritative_section"] = [{"id": "x"}]
    report = validate_semantic_relevance_manifest(history)
    assert report["valid"] is False
    assert any(x["issue"] == "UNKNOWN_HISTORY_SECTION" for x in report["issues"])
    db.close()


def test_unknown_field_in_known_section_fails_closed(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    history = make(db)
    history["future_semantic_field"] = [{"id": "x"}]
    report = validate_semantic_relevance_manifest(history)
    assert report["valid"] is False
    assert any(x["issue"] == "UNKNOWN_HISTORY_SECTION" for x in report["issues"])
    db.close()


def test_nonsemantic_projection_fields_are_excluded(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    history = make(db)
    history["entities"][0]["updated_at"] = "2099-01-01T00:00:00+00:00"
    history["entities"][0]["payload"] = {"poison": True}
    projected = semantic_projection(history)
    assert projected["entities"] == [{}]
    assert projected["revisions"]
    db.close()


def test_manifest_is_part_of_semantic_interpretation(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    history = make(db)
    interpretation = semantic_interpretation(history)
    assert interpretation["manifest_id"] == "SRM-001"
    assert interpretation["manifest_version"] == "0.11.4"
    assert interpretation["semantic_integrity_valid"] is True
    db.close()


def test_new_flattened_revision_payload_field_is_explicitly_semantic(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    history = make(db)
    before = semantic_interpretation(history)
    history["revisions"][0]["future_payload_field"] = "new-meaning"
    report = validate_semantic_relevance_manifest(history)
    after = semantic_interpretation(history)
    assert report["valid"] is True
    assert before["interpretation_digest"] != after["interpretation_digest"]
    db.close()
