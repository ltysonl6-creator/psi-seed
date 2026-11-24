import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from psi_seed.persistence.sqlite.backend import SQLitePersistenceBackend
from psi_seed.persistence.sqlite.errors import ValidationError
from psi_seed.cacc.service import CACCService


def root_of(history):
    return SQLitePersistenceBackend.compute_history_integrity(history)["root"]


def make_belief(db):
    return db.create_belief(proposition="R1", confidence=0.1)


def test_state_rollback_restores_target_but_retains_r2_history(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    db.revise_belief(b["id"], {"proposition": "R2", "confidence": 0.9})
    result = db.rollback_entity_state(b["id"], 1, reason="bad modification")

    current = db.get(b["id"])
    history = db.get_history(b["id"])

    assert current["version"] == 3
    assert current["proposition"] == "R1"
    assert current["confidence"] == 0.1
    assert [h["version"] for h in history] == [1, 2, 3]
    assert history[1]["proposition"] == "R2"
    assert history[2]["proposition"] == "R1"
    assert result["history_rewrite"] is False


def test_rollback_is_new_fact_not_time_travel(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    db.revise_belief(b["id"], {"proposition": "R2"})
    result = db.rollback_entity_state(b["id"], 1)

    event = db.get_event(result["event_id"])
    assert event["event_type"] == "state_rollback"
    assert event["payload"]["from_version"] == 2
    assert event["payload"]["restore_target_version"] == 1
    assert event["payload"]["result_version"] == 3
    assert event["payload"]["history_rewrite"] is False
    assert db.get_history(b["id"])[1]["proposition"] == "R2"


def test_rollback_preserves_dependent_events(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    db.revise_belief(b["id"], {"proposition": "R2"})
    dependent = db.append_event({
        "event_type": "dependent_action",
        "related_entity_refs": [b["id"]],
        "payload": {"built_from_version": 2},
    })
    db.rollback_entity_state(b["id"], 1, reason="dependent change invalidated")

    replay = db.export_authoritative_history()
    events = [e for e in replay["events"] if e["id"] == dependent["id"]]
    assert len(events) == 1
    assert events[0]["payload"]["built_from_version"] == 2
    assert db.get(b["id"])["proposition"] == "R1"


def test_rollback_to_missing_target_is_rejected_without_mutation(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    before = copy.deepcopy(db.export_authoritative_history())
    with pytest.raises(ValidationError):
        db.rollback_entity_state(b["id"], 99)
    after = db.export_authoritative_history()
    assert after == before


def test_tampered_target_snapshot_requires_trusted_root(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    db.revise_belief(b["id"], {"proposition": "R2"})
    trusted = root_of(db.export_authoritative_history())

    with db.atomic():
        db._conn.execute(
            "UPDATE entity_revisions SET payload_json = ? WHERE entity_id = ? AND version = 1",
            (json.dumps({"proposition": "TAMPERED", "confidence": 0.1}, sort_keys=True, separators=(",", ":")), b["id"]),
        )

    before = copy.deepcopy(db.export_authoritative_history())
    with pytest.raises(ValidationError, match="trusted-root verification"):
        db.rollback_entity_state(b["id"], 1, expected_history_root=trusted)
    after = db.export_authoritative_history()
    assert after == before


def test_rollback_without_trusted_root_can_still_be_a_valid_local_operation(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    db.revise_belief(b["id"], {"proposition": "R2"})
    result = db.rollback_entity_state(b["id"], 1)
    assert result["result_version"] == 3
    assert db.get(b["id"])["proposition"] == "R1"


def test_rollback_of_rollback_is_preserved(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    db.revise_belief(b["id"], {"proposition": "R2"})
    first = db.rollback_entity_state(b["id"], 1, reason="first rollback")
    second = db.rollback_entity_state(b["id"], 2, reason="undo first rollback")

    history = db.get_history(b["id"])
    assert [h["version"] for h in history] == [1, 2, 3, 4]
    assert history[2]["proposition"] == "R1"
    assert history[3]["proposition"] == "R2"
    assert first["target_version"] == 1
    assert second["target_version"] == 2


def test_rollback_to_genesis_is_supported_and_retains_everything_afterward(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    for i in range(2, 6):
        db.revise_belief(b["id"], {"proposition": f"R{i}"})
    result = db.rollback_entity_state(b["id"], 1, reason="return to genesis state")
    history = db.get_history(b["id"])

    assert result["target_version"] == 1
    assert db.get(b["id"])["proposition"] == "R1"
    assert [h["version"] for h in history] == [1, 2, 3, 4, 5, 6]
    assert [h["proposition"] for h in history[1:5]] == ["R2", "R3", "R4", "R5"]


def test_rollback_followed_by_new_development_creates_new_branch_from_restored_state(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    db.revise_belief(b["id"], {"proposition": "R2"})
    db.rollback_entity_state(b["id"], 1)
    db.revise_belief(b["id"], {"proposition": "R3-from-R1"})

    history = db.get_history(b["id"])
    assert [h["proposition"] for h in history] == ["R1", "R2", "R1", "R3-from-R1"]
    assert db.get(b["id"])["proposition"] == "R3-from-R1"


def test_replay_reconstructs_post_rollback_current_state(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    db.revise_belief(b["id"], {"proposition": "R2"})
    db.rollback_entity_state(b["id"], 1)
    history = db.export_authoritative_history()
    fresh = SQLitePersistenceBackend.from_authoritative_history(history)

    assert fresh.get(b["id"])["proposition"] == "R1"
    assert fresh.get(b["id"])["version"] == 3
    assert fresh.get_history(b["id"])[1]["proposition"] == "R2"
    assert CACCService.semantic_projection(fresh) == CACCService.semantic_projection_from_history(history)


def test_replay_does_not_execute_rollback_side_effect_again(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    db.revise_belief(b["id"], {"proposition": "R2"})
    db.rollback_entity_state(b["id"], 1)
    history = db.export_authoritative_history()
    rebuilt = db.reconstruct_from_history(history)

    assert rebuilt["entities"][b["id"]]["payload"]["proposition"] == "R1"
    assert len([e for e in rebuilt["events"] if e["event_type"] == "state_rollback"]) == 1


def test_rollback_integrity_failure_happens_before_mutation(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = make_belief(db)
    db.revise_belief(b["id"], {"proposition": "R2"})
    trusted = root_of(db.export_authoritative_history())

    db._conn.execute(
        "UPDATE entity_revisions SET payload_json = ? WHERE entity_id = ? AND version = 2",
        (json.dumps({"proposition": "CORRUPTED"}, sort_keys=True, separators=(",", ":")), b["id"]),
    )
    before_version = db.get(b["id"])["version"]
    with pytest.raises(ValidationError):
        db.rollback_entity_state(b["id"], 1, expected_history_root=trusted)
    assert db.get(b["id"])["version"] == before_version


def test_concurrent_rollbacks_are_serialized_and_history_is_not_lost(tmp_path):
    path = tmp_path / "seed.sqlite3"
    db = SQLitePersistenceBackend(path)
    b = db.create_belief(proposition="R1")
    db.revise_belief(b["id"], {"proposition": "R2"})
    db.close()

    def worker(i):
        conn = SQLitePersistenceBackend(path)
        try:
            return conn.rollback_entity_state(b["id"], 1, reason=f"concurrent-{i}")
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))

    check = SQLitePersistenceBackend(path)
    history = check.get_history(b["id"])
    events = [e for e in check.export_authoritative_history()["events"] if e["event_type"] == "state_rollback"]
    assert len(results) == 2
    assert len(events) == 2
    assert [h["version"] for h in history] == [1, 2, 3, 4]
    assert check.get(b["id"])["proposition"] == "R1"
    check.close()


def test_cacc_service_exposes_state_rollback(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    service = CACCService(db)
    b = service.backend.create_belief(proposition="R1")
    db.revise_belief(b["id"], {"proposition": "R2"})
    result = service.rollback_state(b["id"], 1, reason="service rollback", chain_id="chain-1")
    assert result["target_version"] == 1
    assert db.get(b["id"])["proposition"] == "R1"
    event = db.get_event(result["event_id"])
    assert event["causation_ref"] == "chain-1"


def test_rollback_of_self_modification_preserves_failed_modification_history(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    mod = db.create_self_modification(name="bad rollback policy", policy="allow-dangerous-change")
    db.set_modification_status(mod["id"], "executed")
    db.revise_belief(mod["id"], {"policy": "allow-dangerous-change", "marker": "R2"})
    result = db.rollback_entity_state(mod["id"], 1, reason="self-modification failed")

    assert db.get(mod["id"])["policy"] == "allow-dangerous-change"
    assert db.get(mod["id"])["version"] == 4
    history = db.get_history(mod["id"])
    assert history[1]["status"] == "executed"
    assert history[2]["marker"] == "R2"
    assert history[3]["policy"] == "allow-dangerous-change"
    assert "marker" not in history[3]
    assert result["history_rewrite"] is False


def test_rollback_across_regime_change_preserves_regime_change_record(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = db.create_belief(proposition="R1", regime="stable")
    db.revise_belief(b["id"], {"proposition": "R2", "regime": "drifting"})
    change = db.create_regime_change(
        previous_regime="stable",
        new_regime="drifting",
        detection_event_ref="evt-regime",
        evidence_refs=[],
    )
    result = db.rollback_entity_state(b["id"], 1, reason="restore pre-regime state")

    assert result["target_version"] == 1
    assert db.get(b["id"])["regime"] == "stable"
    assert db.get(change["id"]) is not None
    history = db.export_authoritative_history()
    assert any(e["id"] == change["id"] for e in history["entities"])


def test_rollback_outcome_digest_matches_restored_state(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    b = db.create_belief(proposition="R1", confidence=0.1)
    db.revise_belief(b["id"], {"proposition": "R2", "confidence": 0.9})
    result = db.rollback_entity_state(b["id"], 1)
    event = db.get_event(result["event_id"])
    target = db.get_history(b["id"])[0]
    canonical = json.dumps(
        {"payload": target["payload"], "provenance": target["provenance"]},
        sort_keys=True,
        separators=(",", ":"),
    )
    assert event["payload"]["restored_state_digest"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
