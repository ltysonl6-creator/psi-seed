from datetime import datetime, timezone, timedelta
import pytest

from psi_seed.persistence.sqlite.backend import SQLitePersistenceBackend
from psi_seed.cacc.service import CACCService
from contracts.cacc_joint_validation import CACCJointValidationError
from contracts.semantic_integrity import validate_semantic_integrity


def now(offset_seconds=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


def build_chain(svc, chain="A"):
    p = svc.create_possibility({"description": "p", "causation_chain_id": chain})
    e = svc.record_evaluation({
        "possibility_id": p["id"], "decision": "ADVANCE", "evaluated_at": now(),
        "causation_chain_id": chain,
    })
    c = svc.select_candidate({
        "evaluation_id": e["id"], "possibility_id": p["id"],
        "selection_status": "SELECTED", "selected_at": now(),
        "causation_chain_id": chain,
    })
    g = svc.record_governance({
        "candidate_id": c["id"], "result": "PERMITTED", "decided_at": now(),
        "checks": [], "causation_chain_id": chain,
    })
    ch = svc.create_choice({
        "possibility_id": p["id"], "candidate_id": c["id"],
        "governance_decision_id": g["id"], "decision_time": now(),
        "decision_basis": "x", "selected_action": "x",
        "decision_status": "COMMITTED", "causation_chain_id": chain,
    })
    t = svc.create_transition({
        "choice_id": ch["id"], "before_snapshot": {"x": 0},
        "proposed_state": {"x": 1}, "evidence_delta": {"x": 1},
        "post_state": {"x": 1}, "invariant_results": [],
        "commit_status": "COMMITTED", "timestamp": now(),
        "causation_chain_id": chain,
    })
    return p, e, c, g, ch, t


def test_si_001_chain_mismatch_is_rejected_at_creation(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    svc = CACCService(db)
    *_, transition = build_chain(svc, "CHAIN-A")
    with pytest.raises(CACCJointValidationError, match="causation_chain_id"):
        svc.record_outcome({
            "transition_id": transition["id"], "outcome_id": "outcome-b",
            "result": "SUCCESS", "success": True, "observed_state": {"x": 1},
            "expected_state": {"x": 1}, "timestamp": now(),
            "causation_chain_id": "CHAIN-B",
        })
    db.close()


def test_si_002_temporal_inversion_is_rejected_at_creation(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    svc = CACCService(db)
    *_, transition = build_chain(svc, "CHAIN-A")
    with pytest.raises(CACCJointValidationError, match="precede"):
        svc.record_outcome({
            "transition_id": transition["id"], "outcome_id": "outcome-time",
            "result": "SUCCESS", "success": True, "observed_state": {"x": 1},
            "expected_state": {"x": 1}, "timestamp": now(-3600),
            "causation_chain_id": "CHAIN-A",
        })
    db.close()


def test_si_003_rollback_is_lifecycle_boundary(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    svc = CACCService(db)
    *_, transition = build_chain(svc, "CHAIN-A")
    svc.record_outcome({
        "transition_id": transition["id"], "outcome_id": "outcome-before",
        "result": "SUCCESS", "success": True, "observed_state": {"x": 1},
        "expected_state": {"x": 1}, "timestamp": now(),
        "causation_chain_id": "CHAIN-A",
    })
    rollback = svc.rollback_transition(transition["id"], reason="invalidated")
    assert rollback["transition_id"] == transition["id"]
    assert db.get(transition["id"])["status"] == "ROLLED_BACK"
    with pytest.raises(CACCJointValidationError, match="rolled-back"):
        svc.record_outcome({
            "transition_id": transition["id"], "outcome_id": "outcome-after",
            "result": "SUCCESS", "success": True, "observed_state": {"x": 1},
            "expected_state": {"x": 1}, "timestamp": now(1),
            "causation_chain_id": "CHAIN-A",
        })
    # The first outcome remains historical evidence; rollback did not erase it.
    assert db.get("outcome-before") is not None
    db.close()


def test_si_004_developmental_evidence_rejects_rolled_back_outcome(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    svc = CACCService(db)
    *_, transition = build_chain(svc, "CHAIN-A")
    outcome = svc.record_outcome({
        "transition_id": transition["id"], "outcome_id": "outcome-dev",
        "result": "SUCCESS", "success": True, "observed_state": {"x": 1},
        "expected_state": {"x": 1}, "timestamp": now(),
        "causation_chain_id": "CHAIN-A",
    })
    svc.rollback_transition(transition["id"], reason="bad result")
    with pytest.raises(CACCJointValidationError, match="ineligible"):
        svc.link_developmental_evidence("evidence-dev", [outcome["id"]], "CHAIN-A")
    db.close()


def test_si_005_audit_detects_legacy_semantic_corruption(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    svc = CACCService(db)
    *_, transition = build_chain(svc, "CHAIN-A")
    # Create an individually valid outcome through the backend, bypassing the
    # service enforcement. This models imported/legacy/corrupted authoritative data.
    bad = {
        "id": "legacy-bad-outcome",
        "entity_type": "cacc_outcome",
        "status": "active",
        "created_at": now(-3600),
        "provenance": {},
        "transition_id": transition["id"],
        "outcome_id": "legacy-bad-outcome",
        "result": "SUCCESS",
        "success": True,
        "timestamp": now(-3600),
        "causation_chain_id": "CHAIN-B",
    }
    db.create_record(bad)
    db.create_relationship(
        source_id=transition["id"], target_id=bad["id"],
        relationship_type="TRANSITION_PRODUCES_OUTCOME",
        metadata={"causation_chain_id": "CHAIN-A", "contract": "CACC-JOINTS-001"},
        relationship_id="rel-legacy-bad",
    )
    report = svc.validate_semantic_integrity()
    codes = {x["code"] for x in report["issues"]}
    assert "SI-001" in codes
    assert "SI-002" in codes
    db.close()


def test_si_006_valid_history_passes_semantic_audit(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    svc = CACCService(db)
    *_, transition = build_chain(svc, "CHAIN-A")
    svc.record_outcome({
        "transition_id": transition["id"], "outcome_id": "good-outcome",
        "result": "SUCCESS", "success": True, "observed_state": {"x": 1},
        "expected_state": {"x": 1}, "timestamp": now(),
        "causation_chain_id": "CHAIN-A",
    })
    report = svc.validate_semantic_integrity()
    assert report["valid"] is True
    assert report["issue_count"] == 0
    db.close()
