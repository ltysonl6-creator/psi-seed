from datetime import datetime, timezone, timedelta
import copy
import pytest

from psi_seed.persistence.sqlite.backend import SQLitePersistenceBackend
from psi_seed.cacc.service import CACCService
from contracts.semantic_integrity import validate_semantic_integrity
from contracts.semantic_replay import semantic_interpretation, semantic_replay


def ts(offset=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat()


def make_entity(db, eid="e1"):
    return db.create_record({
        "id": eid, "entity_type": "belief", "status": "active",
        "created_at": ts(), "provenance": {}, "payload": {"value": "A"},
    })


def test_revision_time_inversion_is_semantically_invalid(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    e = make_entity(db)
    db.revise_entity(e["id"], {"value": "B"})
    history = db.export_authoritative_history()
    revs = [r for r in history["revisions"] if r["entity_id"] == e["id"]]
    revs[0]["created_at"], revs[1]["created_at"] = revs[1]["created_at"], revs[0]["created_at"]
    report = validate_semantic_integrity(history)
    assert report["valid"] is False
    assert "SI-008" in {x["code"] for x in report["issues"]}
    db.close()


def test_revision_event_after_revision_is_semantically_invalid(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    e = make_entity(db)
    db.revise_entity(e["id"], {"value": "B"})
    history = db.export_authoritative_history()
    rev = [r for r in history["revisions"] if r["entity_id"] == e["id"]][-1]
    event_id = rev["revision_event_id"]
    # Existing v0.11 revisions may not carry events; create an explicit bad link.
    if not event_id:
        event = db.append_event({
            "event_type": "revision", "occurred_at": ts(100),
            "related_entity_refs": [e["id"]], "payload": {"version": rev["version"]},
        })
        rev["revision_event_id"] = event["id"]
        event_id = event["id"]
    else:
        for event in history["events"]:
            if event["id"] == event_id:
                event["occurred_at"] = ts(100)
    report = validate_semantic_integrity(history)
    assert report["valid"] is False
    assert "SI-009" in {x["code"] for x in report["issues"]}
    db.close()


def test_fresh_replay_matches_semantic_interpretation(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    e = make_entity(db)
    db.revise_entity(e["id"], {"value": "B"})
    history = db.export_authoritative_history()
    fresh = SQLitePersistenceBackend.from_authoritative_history(history, tmp_path / "fresh.sqlite3")
    result = semantic_replay(history, fresh.export_authoritative_history())
    assert result["equivalent"] is True
    assert result["issues"] == []
    fresh.close(); db.close()


def test_same_current_state_different_history_has_different_meaning(tmp_path):
    db1 = SQLitePersistenceBackend(tmp_path / "a.sqlite3")
    e1 = make_entity(db1, "e1")
    db1.revise_entity("e1", {"value": "B"})
    h1 = db1.export_authoritative_history()

    db2 = SQLitePersistenceBackend(tmp_path / "b.sqlite3")
    e2 = make_entity(db2, "e1")
    db2.revise_entity("e1", {"value": "X"})
    db2.revise_entity("e1", {"value": "B"})
    h2 = db2.export_authoritative_history()

    i1 = semantic_interpretation(h1)
    i2 = semantic_interpretation(h2)
    assert i1["revisions"] != i2["revisions"]
    assert i1["interpretation_digest"] != i2["interpretation_digest"]
    db1.close(); db2.close()


def test_replay_detects_semantic_difference_even_when_current_state_matches(tmp_path):
    db1 = SQLitePersistenceBackend(tmp_path / "a.sqlite3")
    make_entity(db1, "e1")
    db1.revise_entity("e1", {"value": "B"})
    h1 = db1.export_authoritative_history()

    db2 = SQLitePersistenceBackend(tmp_path / "b.sqlite3")
    make_entity(db2, "e1")
    db2.revise_entity("e1", {"value": "X"})
    db2.revise_entity("e1", {"value": "B"})
    h2 = db2.export_authoritative_history()

    result = semantic_replay(h1, h2)
    assert result["equivalent"] is False
    assert result["issues"][0]["code"] == "SI-010"
    db1.close(); db2.close()
