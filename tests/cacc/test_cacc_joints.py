from datetime import datetime, timezone
import pytest
from psi_seed.cacc import CACCService
from contracts.cacc_joint_validation import CACCJointValidationError

def now():
    return datetime.now(timezone.utc).isoformat()

def make_prefix(svc, chain):
    p=svc.create_possibility({
        "description":"test","source":"test","candidate_type":"action",
        "status":"OPEN","relevance":1,"risk":0,"uncertainty":0.1,
        "causation_chain_id":chain})
    e=svc.record_evaluation({
        "possibility_id":p["id"],"evaluated_at":now(),
        "scores":{"relevance":1},"decision":"ADVANCE",
        "causation_chain_id":chain})
    c=svc.select_candidate({
        "evaluation_id":e["id"],"possibility_id":p["id"],
        "selected_at":now(),"selection_status":"SELECTED",
        "selection_basis":"test","causation_chain_id":chain})
    return p,e,c

def test_choice_requires_permitted_governance(backend):
    svc=CACCService(backend); p,e,c=make_prefix(svc,"chain-1")
    g=svc.record_governance({
        "candidate_id":c["id"],"decided_at":now(),"result":"BLOCKED",
        "checks":[{"name":"protected","passed":False}],
        "causation_chain_id":"chain-1"})
    with pytest.raises(CACCJointValidationError):
        svc.create_choice({
            "possibility_id":p["id"],"candidate_id":c["id"],
            "governance_decision_id":g["id"],"decision_time":now(),
            "decision_basis":"test","selected_action":"do_it",
            "decision_status":"COMMITTED","decision_provenance":{},
            "causation_chain_id":"chain-1"})

def test_full_choice_transition_outcome_chain(backend):
    svc=CACCService(backend); p,e,c=make_prefix(svc,"chain-2")
    g=svc.record_governance({
        "candidate_id":c["id"],"decided_at":now(),"result":"PERMITTED",
        "checks":[{"name":"protected","passed":True}],
        "causation_chain_id":"chain-2"})
    choice=svc.create_choice({
        "possibility_id":p["id"],"candidate_id":c["id"],
        "governance_decision_id":g["id"],"decision_time":now(),
        "decision_basis":"test","selected_action":"do_it",
        "decision_status":"COMMITTED","decision_provenance":{},
        "causation_chain_id":"chain-2"})
    transition=svc.create_transition({
        "choice_id":choice["id"],"before_snapshot":{"x":0},
        "proposed_state":{"x":1},"evidence_delta":{"x":1},
        "post_state":{"x":1},"invariant_results":[{"id":"I01","passed":True}],
        "commit_status":"COMMITTED","timestamp":now(),"provenance":{},
        "causation_chain_id":"chain-2"})
    outcome=svc.record_outcome({
        "transition_id":transition["id"],"result":"SUCCESS","success":True,
        "observed_state":{"x":1},"expected_state":{"x":1},
        "event_id":"evt-test-1","timestamp":now(),
        "causation_chain_id":"chain-2"})
    assert outcome["transition_id"]==transition["id"]
    kinds={r["relationship_type"] for r in backend._conn.execute(
        "SELECT relationship_type FROM relationships").fetchall()}
    assert {"governance_authorizes_choice","choice_executes_transition",
            "transition_produces_outcome"} <= kinds

def test_transition_requires_authoritative_choice(backend):
    svc=CACCService(backend)
    with pytest.raises(CACCJointValidationError):
        svc.create_transition({
            "choice_id":"missing","before_snapshot":{},"proposed_state":{},
            "evidence_delta":{},"post_state":{},"invariant_results":[],
            "commit_status":"COMMITTED","timestamp":now(),"provenance":{},
            "causation_chain_id":"chain-3"})
