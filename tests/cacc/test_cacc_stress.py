from datetime import datetime, timezone
import pytest
from psi_seed.cacc import CACCService
from contracts.cacc_joint_validation import CACCJointValidationError


def now():
    return datetime.now(timezone.utc).isoformat()


def prefix(svc, chain="stress"):
    p = svc.create_possibility({"description":"p","entity_type":"possibility","causation_chain_id":chain})
    e = svc.record_evaluation({"possibility_id":p["id"],"decision":"ADVANCE","evaluated_at":now(),"causation_chain_id":chain})
    c = svc.select_candidate({"evaluation_id":e["id"],"possibility_id":p["id"],"selection_status":"SELECTED","selected_at":now(),"causation_chain_id":chain})
    g = svc.record_governance({"candidate_id":c["id"],"result":"PERMITTED","decided_at":now(),"checks":[],"causation_chain_id":chain})
    return p,e,c,g


def test_j03_candidate_governed_by_edge_is_persisted(backend):
    svc=CACCService(backend); p,e,c,g=prefix(svc)
    edges=backend.get_relationships(source_id=c["id"], target_id=g["id"], relationship_type="candidate_governed_by")
    assert len(edges)==1


def test_choice_cannot_cross_wire_candidate_and_possibility(backend):
    svc=CACCService(backend); p,e,c,g=prefix(svc)
    p2=svc.create_possibility({"description":"other","causation_chain_id":"other"})
    with pytest.raises(CACCJointValidationError):
        svc.create_choice({"possibility_id":p2["id"],"candidate_id":c["id"],"governance_decision_id":g["id"],"decision_time":now(),"decision_basis":"x","selected_action":"x","decision_status":"COMMITTED","causation_chain_id":"stress"})


def test_governance_cannot_authorize_wrong_candidate(backend):
    svc=CACCService(backend); p,e,c,g=prefix(svc)
    p2=svc.create_possibility({"description":"other","causation_chain_id":"other"})
    e2=svc.record_evaluation({"possibility_id":p2["id"],"decision":"ADVANCE","evaluated_at":now(),"causation_chain_id":"other"})
    c2=svc.select_candidate({"evaluation_id":e2["id"],"possibility_id":p2["id"],"selection_status":"SELECTED","selected_at":now(),"causation_chain_id":"other"})
    with pytest.raises(CACCJointValidationError):
        svc.create_choice({"possibility_id":p["id"],"candidate_id":c2["id"],"governance_decision_id":g["id"],"decision_time":now(),"decision_basis":"x","selected_action":"x","decision_status":"COMMITTED","causation_chain_id":"stress"})


def test_failure_and_rollback_cannot_point_to_missing_records(backend):
    svc=CACCService(backend); p,e,c,g=prefix(svc)
    choice=svc.create_choice({"possibility_id":p["id"],"candidate_id":c["id"],"governance_decision_id":g["id"],"decision_time":now(),"decision_basis":"x","selected_action":"x","decision_status":"COMMITTED","causation_chain_id":"stress"})
    t=svc.create_transition({"choice_id":choice["id"],"before_snapshot":{},"proposed_state":{},"evidence_delta":{},"post_state":{},"invariant_results":[],"commit_status":"COMMITTED","timestamp":now(),"causation_chain_id":"stress"})
    with pytest.raises(CACCJointValidationError):
        svc.link_failure("missing",t["id"],"stress")
    with pytest.raises(CACCJointValidationError):
        svc.link_rollback("missing",t["id"],"stress")


def test_chain_survives_export_reconstruction(backend):
    svc=CACCService(backend); p,e,c,g=prefix(svc)
    choice=svc.create_choice({"possibility_id":p["id"],"candidate_id":c["id"],"governance_decision_id":g["id"],"decision_time":now(),"decision_basis":"x","selected_action":"x","decision_status":"COMMITTED","causation_chain_id":"stress"})
    t=svc.create_transition({"choice_id":choice["id"],"before_snapshot":{"x":0},"proposed_state":{"x":1},"evidence_delta":{"x":1},"post_state":{"x":1},"invariant_results":[],"commit_status":"COMMITTED","timestamp":now(),"causation_chain_id":"stress"})
    o=svc.record_outcome({"transition_id":t["id"],"result":"SUCCESS","success":True,"observed_state":{"x":1},"expected_state":{"x":1},"timestamp":now(),"causation_chain_id":"stress"})
    history=backend.export_authoritative_history()
    rebuilt=backend.reconstruct_from_history(history)
    rels=[r for r in rebuilt["relationships"] if r["metadata"].get("causation_chain_id")=="stress"]
    types={r["relationship_type"] for r in rels}
    assert {"possibility_evaluated_by","evaluation_selected_as_candidate","candidate_governed_by","governance_authorizes_choice","choice_executes_transition","transition_produces_outcome"} <= types
    assert o["id"] in rebuilt["entities"]


def test_choice_and_joint_commit_atomically(backend, monkeypatch):
    svc=CACCService(backend); p,e,c,g=prefix(svc)
    original=svc._relate
    calls=0
    def fail_after_entity(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("simulated relationship write failure")
    monkeypatch.setattr(svc, "_relate", fail_after_entity)
    with pytest.raises(RuntimeError):
        svc.create_choice({
            "possibility_id":p["id"],"candidate_id":c["id"],
            "governance_decision_id":g["id"],"decision_time":now(),
            "decision_basis":"x","selected_action":"x",
            "decision_status":"COMMITTED","causation_chain_id":"stress"})
    choices=backend._conn.execute("SELECT COUNT(*) AS n FROM entities WHERE entity_type='choice'").fetchone()["n"]
    assert choices == 0


def test_chain_integrity_detects_deleted_joint(backend):
    svc=CACCService(backend); p,e,c,g=prefix(svc)
    choice=svc.create_choice({"possibility_id":p["id"],"candidate_id":c["id"],"governance_decision_id":g["id"],"decision_time":now(),"decision_basis":"x","selected_action":"x","decision_status":"COMMITTED","causation_chain_id":"stress"})
    t=svc.create_transition({"choice_id":choice["id"],"before_snapshot":{},"proposed_state":{},"evidence_delta":{},"post_state":{},"invariant_results":[],"commit_status":"COMMITTED","timestamp":now(),"causation_chain_id":"stress"})
    svc.record_outcome({"transition_id":t["id"],"result":"SUCCESS","success":True,"observed_state":{},"expected_state":{},"timestamp":now(),"causation_chain_id":"stress"})
    edge=backend.get_relationships(source_id=choice["id"], relationship_type="choice_executes_transition")[0]
    backend._conn.execute("DELETE FROM relationships WHERE id = ?", (edge["id"],))
    result=svc.reconstruct_cacc_chain("stress")
    assert not result["valid"]
    assert any(i["relationship_type"] == "choice_executes_transition" for i in result["issues"])


def test_full_developmental_tail_closes_all_remaining_joints(backend):
    svc=CACCService(backend); p,e,c,g=prefix(svc)
    choice=svc.create_choice({
        "possibility_id":p["id"],"candidate_id":c["id"],"governance_decision_id":g["id"],
        "decision_time":now(),"decision_basis":"x","selected_action":"x",
        "decision_status":"COMMITTED","causation_chain_id":"stress"})
    t=svc.create_transition({
        "choice_id":choice["id"],"before_snapshot":{"x":0},"proposed_state":{"x":1},
        "evidence_delta":{"x":1},"post_state":{"x":1},"invariant_results":[],
        "commit_status":"COMMITTED","timestamp":now(),"causation_chain_id":"stress"})
    o=svc.record_outcome({
        "transition_id":t["id"],"result":"SUCCESS","success":True,
        "observed_state":{"x":1},"expected_state":{"x":1},"timestamp":now(),
        "causation_chain_id":"stress"})
    evidence=svc.link_developmental_evidence("evidence_1", [o["id"]], "stress")
    episode=svc.create_developmental_episode({
        "episode_id":"episode_1","evidence_id":evidence["id"],
        "trigger":"transition_outcome","causation_chain_id":"stress"})
    rule=svc.create_developmental_rule({
        "rule_id":"rule_1","episode_id":episode["id"],
        "rule":"retain successful transition pattern","causation_chain_id":"stress"})
    future=svc.create_possibility({
        "id":"future_possibility","description":"future action enabled by development",
        "causation_chain_id":"stress"})
    svc.create_developmental_change({
        "change_id":"development_1","rule_id":rule["id"],
        "possibility_id":future["id"],"change_type":"capability_expansion",
        "causation_chain_id":"stress"})

    result=svc.reconstruct_cacc_chain("stress")
    assert result["valid"]
    types={r["relationship_type"] for r in result["relationships"]}
    assert {
        "possibility_evaluated_by","evaluation_selected_as_candidate","candidate_governed_by",
        "governance_authorizes_choice","choice_executes_transition","transition_produces_outcome",
        "outcome_persisted_as_evidence","evidence_forms_episode","episode_supports_rule",
        "development_changes_possibility_space",
    } <= types


def test_developmental_tail_rejects_wrong_endpoint_types(backend):
    svc=CACCService(backend); p,e,c,g=prefix(svc)
    wrong=svc.create_possibility({"description":"wrong endpoint","causation_chain_id":"stress"})
    # Inject an invalid developmental joint directly to test reconstruction rather than service validation.
    backend.create_relationship(
        source_id=wrong["id"], target_id=p["id"],
        relationship_type="development_changes_possibility_space",
        metadata={"causation_chain_id":"stress"}, relationship_id="bad-dev-rel")
    result=svc.reconstruct_cacc_chain("stress")
    assert not result["valid"]
    assert any(i["code"] == "CACC-V-005" for i in result["issues"])
