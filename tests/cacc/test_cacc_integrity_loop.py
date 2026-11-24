from datetime import datetime, timezone
import hashlib
import json
import pytest
from psi_seed.cacc import CACCService


def now(): return datetime.now(timezone.utc).isoformat()


def full_chain(svc, chain="loop"):
    p=svc.create_possibility({"description":"p","causation_chain_id":chain})
    e=svc.record_evaluation({"possibility_id":p["id"],"decision":"ADVANCE","evaluated_at":now(),"causation_chain_id":chain})
    c=svc.select_candidate({"evaluation_id":e["id"],"possibility_id":p["id"],"selection_status":"SELECTED","selected_at":now(),"causation_chain_id":chain})
    g=svc.record_governance({"candidate_id":c["id"],"result":"PERMITTED","decided_at":now(),"checks":[],"causation_chain_id":chain})
    ch=svc.create_choice({"possibility_id":p["id"],"candidate_id":c["id"],"governance_decision_id":g["id"],"decision_time":now(),"decision_basis":"x","selected_action":"x","decision_status":"COMMITTED","causation_chain_id":chain})
    t=svc.create_transition({"choice_id":ch["id"],"before_snapshot":{"x":0},"proposed_state":{"x":1},"evidence_delta":{"x":1},"post_state":{"x":1},"invariant_results":[],"commit_status":"COMMITTED","timestamp":now(),"causation_chain_id":chain})
    o=svc.record_outcome({"transition_id":t["id"],"result":"SUCCESS","success":True,"observed_state":{"x":1},"expected_state":{"x":1},"timestamp":now(),"causation_chain_id":chain})
    ev=svc.link_developmental_evidence("evidence_1", [o["id"]], chain)
    ep=svc.create_developmental_episode({"episode_id":"episode_1","evidence_id":ev["id"],"trigger":"transition_outcome","causation_chain_id":chain})
    rule=svc.create_developmental_rule({"rule_id":"rule_1","episode_id":ep["id"],"rule":"retain successful transition pattern","causation_chain_id":chain})
    future=svc.create_possibility({"id":"future_possibility","description":"future action","causation_chain_id":chain})
    dev=svc.create_developmental_change({"change_id":"development_1","rule_id":rule["id"],"possibility_id":future["id"],"change_type":"capability_expansion","causation_chain_id":chain})
    return p,e,c,g,ch,t,o,ev,ep,rule,future,dev


def test_replay_is_deterministic_and_non_mutating(backend):
    svc=CACCService(backend); full_chain(svc)
    before=backend.export_authoritative_history()
    a=svc.replay_cacc_chain("loop")
    b=svc.replay_cacc_chain("loop")
    assert a["digest"] == b["digest"]
    assert backend.export_authoritative_history() == before


def test_corrupted_current_payload_is_detected_against_revision(backend):
    svc=CACCService(backend); p,e,c,g,ch,t,o,*_=full_chain(svc)
    backend._conn.execute("UPDATE entities SET payload_json=? WHERE id=?", (json.dumps({"corrupted": True}), ch["id"]))
    result=svc.reconstruct_cacc_chain("loop")
    assert not result["valid"]
    assert any(i["code"] == "CACC-V-007" for i in result["issues"])


def test_payload_rewire_is_detected_even_when_joint_survives(backend):
    svc=CACCService(backend); p,e,c,g,ch,t,o,*_=full_chain(svc)
    backend._conn.execute("UPDATE entities SET payload_json=? WHERE id=?", (json.dumps({"choice_id":"wrong"}), t["id"]))
    result=svc.reconstruct_cacc_chain("loop")
    assert not result["valid"]
    assert any(i["code"] == "CACC-V-006" for i in result["issues"])


def test_rollback_preserves_original_transition_and_records_restored_state(backend):
    svc=CACCService(backend); *_,t,o,ev,ep,rule,future,dev=full_chain(svc)
    rb=svc.rollback_transition(t["id"], reason="test rollback")
    assert rb["restored_state"] == {"x":0}
    assert backend.get(t["id"])["post_state"] == {"x":1}
    assert backend.get(o["id"]) is not None
    assert backend.get(rb["id"]) is not None
    edges=backend.get_relationships(source_id=t["id"], target_id=rb["id"], relationship_type="rollback_of_transition")
    assert len(edges)==1
    assert svc.reconstruct_cacc_chain("loop")["valid"]


def test_fresh_instance_rebuild_uses_authoritative_history_not_mutable_current_state(backend):
    svc=CACCService(backend)
    full_chain(svc)
    authoritative=backend.export_authoritative_history()
    fresh=svc.rebuild_fresh_from_authoritative_history(authoritative)
    try:
        assert svc.semantic_projection_from_history(authoritative) == svc.semantic_projection(fresh)
        assert svc.reconstruct_cacc_chain_from_backend(fresh, "loop")["valid"]
    finally:
        fresh.close()


def test_fresh_rebuild_survives_source_current_payload_corruption(backend):
    svc=CACCService(backend)
    _,_,_,_,ch,_,_,_,_,_,_,_=full_chain(svc)
    authoritative=backend.export_authoritative_history()
    backend._conn.execute("UPDATE entities SET payload_json=? WHERE id=?", (json.dumps({"poisoned": True}), ch["id"]))
    fresh=svc.rebuild_fresh_from_authoritative_history(authoritative)
    try:
        assert svc.semantic_projection_from_history(authoritative) == svc.semantic_projection(fresh)
        assert fresh.get(ch["id"])["payload"] != {"poisoned": True}
        assert svc.reconstruct_cacc_chain_from_backend(fresh, "loop")["valid"]
    finally:
        fresh.close()

def test_authoritative_history_has_stable_integrity_root(backend):
    svc=CACCService(backend); full_chain(svc)
    history=backend.export_authoritative_history()
    root=history["integrity"]["root"]
    assert svc.verify_authoritative_history(history, expected_root=root)["valid"]


def test_tampered_authoritative_revision_fails_against_anchored_root(backend):
    svc=CACCService(backend); full_chain(svc)
    history=backend.export_authoritative_history()
    root=history["integrity"]["root"]
    history["revisions"][0]["payload"]["tampered"]=True
    result=svc.verify_authoritative_history(history, expected_root=root)
    assert not result["valid"]
    assert any(i["code"] == "HIST-I-002" for i in result["issues"])


def test_tampered_relationship_fails_against_anchored_root(backend):
    svc=CACCService(backend); full_chain(svc)
    history=backend.export_authoritative_history()
    root=history["integrity"]["root"]
    history["relationships"][0]["target_id"]="forged-target"
    result=svc.verify_authoritative_history(history, expected_root=root)
    assert not result["valid"]
    assert any(i["code"] == "HIST-I-002" for i in result["issues"])


def test_embedded_manifest_detects_internal_inconsistency(backend):
    svc=CACCService(backend); full_chain(svc)
    history=backend.export_authoritative_history()
    history["revisions"][0]["payload"]["tampered"]=True
    result=svc.verify_authoritative_history(history)
    assert not result["valid"]
    assert any(i["code"] == "HIST-I-003" for i in result["issues"])
