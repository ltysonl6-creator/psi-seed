import copy
import hashlib
import json
import pytest

from psi_seed.persistence.sqlite.backend import SQLitePersistenceBackend
from psi_seed.persistence.sqlite.errors import ValidationError
from psi_seed.cacc.service import CACCService


def canonical_state(state):
    return json.dumps(
        {"payload": state["payload"], "provenance": state["provenance"], "status": state["status"]},
        sort_keys=True, separators=(",", ":"),
    )


def test_v010_reconstruction_ignores_mutable_entity_projection(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = db.create_belief(proposition="R1", confidence=0.1)
    db.revise_belief(b["id"], {"proposition": "R2", "confidence": 0.9})
    db.set_modification_status if False else None
    history = db.export_authoritative_history()
    poisoned = copy.deepcopy(history)
    for entity in poisoned["entities"]:
        if entity["id"] == b["id"]:
            entity["payload"]["proposition"] = "POISON"
            entity["version"] = 999
            entity["status"] = "poisoned"
    rebuilt = db.reconstruct_from_history(poisoned)
    assert rebuilt["entities"][b["id"]]["payload"]["proposition"] == "R2"
    assert rebuilt["entities"][b["id"]]["version"] == 2
    assert rebuilt["entities"][b["id"]]["status"] == "active"


def test_v010_status_is_authoritative_revision_state(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    m = db.create_self_modification(name="bad", policy="x")
    db.execute_modification(m["id"])
    history = db.get_history(m["id"])
    assert [r["status"] for r in history] == ["proposed", "executed"]
    assert db.get(m["id"])["status"] == "executed"


def test_v010_rollback_restores_status_and_payload_as_one_snapshot(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    m = db.create_self_modification(name="bad", policy="safe")
    db.execute_modification(m["id"])
    db.revise_entity(m["id"], {"policy": "dangerous", "marker": "R2"})
    result = db.rollback_entity_state(m["id"], 1)
    current = db.get(m["id"])
    assert current["status"] == "proposed"
    assert current["policy"] == "safe"
    assert current["version"] == 4
    assert result["target_version"] == 1


def test_v010_rollback_digest_describes_resulting_state(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = db.create_belief(proposition="R1")
    db.revise_belief(b["id"], {"proposition": "R2"})
    result = db.rollback_entity_state(b["id"], 1)
    event = db.get_event(result["event_id"])
    current = db.get(b["id"])
    expected = hashlib.sha256(canonical_state(current).encode()).hexdigest()
    assert event["payload"]["result_state_digest"] == expected
    target = db.get_history(b["id"])[0]
    target_digest = hashlib.sha256(canonical_state(target).encode()).hexdigest()
    assert event["payload"]["target_state_digest"] == target_digest


def test_v010_unversioned_belief_update_is_impossible(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = db.create_belief(proposition="R1")
    db.update_belief(b["id"], {"proposition": "R2"})
    history = db.get_history(b["id"])
    assert [r["version"] for r in history] == [1, 2]
    assert history[-1]["proposition"] == "R2"


def test_v010_reconstruct_requires_complete_authoritative_revision_state(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = db.create_belief(proposition="R1")
    history = db.export_authoritative_history()
    broken = copy.deepcopy(history)
    del broken["revisions"][0]["status"]
    with pytest.raises(ValidationError):
        db.reconstruct_from_history(broken)


def test_v010_reconstruction_derives_latest_revision_only(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = db.create_belief(proposition="R1")
    db.revise_belief(b["id"], {"proposition": "R2"})
    db.rollback_entity_state(b["id"], 1)
    history = db.export_authoritative_history()
    rebuilt = db.reconstruct_from_history(history)
    assert rebuilt["entities"][b["id"]]["version"] == 3
    assert rebuilt["entities"][b["id"]]["proposition"] == "R1"


def test_v010_cacc_state_rollback_can_be_attached_to_transition(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    service = CACCService(db)
    b = service.backend.create_belief(proposition="R1")
    transition = service._create("transition_transaction", {
        "id": "transition-v010",
        "causation_chain_id": "chain-v010",
        "before_snapshot": {"proposition": "R1"},
        "proposed_state": {"proposition": "R2"},
    })
    db.revise_belief(b["id"], {"proposition": "R2"})
    result = service.rollback_state(
        b["id"], 1, reason="failed change", chain_id="chain-v010", transition_id=transition["id"]
    )
    assert result["rollback_entity_id"] == result["rollback_id"]
    rels = db.get_relationships(relationship_type="rollback_of_transition")
    assert any(r["source_id"] == transition["id"] and r["target_id"] == result["rollback_entity_id"] for r in rels)


def test_v010_replay_preserves_rollback_as_history_not_action(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = db.create_belief(proposition="R1")
    db.revise_belief(b["id"], {"proposition": "R2"})
    db.rollback_entity_state(b["id"], 1)
    history = db.export_authoritative_history()
    fresh = SQLitePersistenceBackend.from_authoritative_history(history)
    assert fresh.get(b["id"])["proposition"] == "R1"
    assert fresh.get(b["id"])["version"] == 3
    assert len([e for e in fresh.export_authoritative_history()["events"] if e["event_type"] == "state_rollback"]) == 1


def test_v010_rollback_target_is_immutable_after_newer_state_exists(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = db.create_belief(proposition="R1")
    db.revise_belief(b["id"], {"proposition": "R2"})
    before = copy.deepcopy(db.get_history(b["id"])[0])
    db.rollback_entity_state(b["id"], 1)
    after = db.get_history(b["id"])[0]
    assert before == after


def test_v010_failed_rollback_is_atomic(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = db.create_belief(proposition="R1")
    db.revise_belief(b["id"], {"proposition": "R2"})
    with pytest.raises(ValidationError):
        db.rollback_entity_state(b["id"], 99)
    assert db.get(b["id"])["version"] == 2
    assert len(db.get_history(b["id"])) == 2
    assert not [e for e in db.export_authoritative_history()["events"] if e["event_type"] == "state_rollback"]
