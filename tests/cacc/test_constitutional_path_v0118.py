import copy

from contracts.constitutional_path import (
    full_path_digest,
    path_digest,
    validate_history,
)


def state(active, generations, evaluator_version=1, approval_threshold="ELEVATED"):
    return {
        "active_generation": active,
        "generations": generations,
        "evaluator_version": evaluator_version,
        "approval_threshold": approval_threshold,
    }


def transition(source, target, **extra):
    value = {"from": source, "to": target}
    value.update(extra)
    return value


def test_c001_every_intermediate_state_can_be_valid_while_path_is_invalid():
    states = [
        state("G1", {"G1": "ACTIVE"}),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}),
        state("G3", {"G1": "RETIRED", "G2": "RETIRED", "G3": "ACTIVE"}),
        state("G1", {"G1": "ACTIVE", "G2": "RETIRED", "G3": "RETIRED"}),
    ]
    transitions = [transition("G1", "G2"), transition("G2", "G3"), transition("G3", "G1")]
    report = validate_history(states, transitions)
    assert report.state_valid
    assert report.transitions_valid
    assert report.composition_valid
    assert not report.path_valid
    assert not report.constitutional_valid


def test_c002_same_final_configuration_does_not_imply_same_legitimacy():
    valid_states = [
        state("G1", {"G1": "ACTIVE"}),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}),
        state("G3", {"G1": "RETIRED", "G2": "RETIRED", "G3": "ACTIVE"}),
    ]
    valid_transitions = [transition("G1", "G2"), transition("G2", "G3")]

    invalid_states = [
        copy.deepcopy(valid_states[0]),
        copy.deepcopy(valid_states[1]),
        copy.deepcopy(valid_states[2]),
        state("G1", {"G1": "ACTIVE", "G2": "RETIRED", "G3": "RETIRED"}),
        copy.deepcopy(valid_states[2]),
    ]
    invalid_transitions = [
        transition("G1", "G2"),
        transition("G2", "G3"),
        transition("G3", "G1"),
        transition("G1", "G3"),
    ]

    valid = validate_history(valid_states, valid_transitions)
    invalid = validate_history(invalid_states, invalid_transitions)
    assert valid.constitutional_valid
    assert not invalid.constitutional_valid
    assert valid_states[-1]["active_generation"] == invalid_states[-1]["active_generation"]
    assert valid_states[-1]["generations"] == invalid_states[-1]["generations"]
    assert valid.path_digest != invalid.path_digest


def test_c003_rollback_is_a_transition_and_cannot_erase_path_history():
    states = [
        state("G1", {"G1": "ACTIVE"}),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}),
        state("G1", {"G1": "ACTIVE", "G2": "RETIRED"}),
    ]
    transitions = [
        transition("G1", "G2", event_type="rotation"),
        transition("G2", "G1", event_type="rollback"),
    ]
    report = validate_history(states, transitions)
    assert not report.path_valid
    assert any("reactivates retired generation G1" in f.message for f in report.findings)


def test_c004_composition_can_fail_even_when_latest_delta_is_locally_valid():
    states = [
        state("G1", {"G1": "ACTIVE"}, evaluator_version=1, approval_threshold="ELEVATED"),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}, evaluator_version=2, approval_threshold="ELEVATED"),
        state("G3", {"G1": "RETIRED", "G2": "RETIRED", "G3": "ACTIVE"}, evaluator_version=2, approval_threshold="STANDARD"),
    ]
    transitions = [transition("G1", "G2"), transition("G2", "G3")]
    report = validate_history(states, transitions)
    assert report.state_valid
    assert report.transitions_valid
    assert not report.composition_valid
    assert not report.constitutional_valid


def test_c005_path_digest_is_order_sensitive():
    a = [transition("G1", "G2"), transition("G2", "G3")]
    b = [transition("G2", "G3"), transition("G1", "G2")]
    assert path_digest(a) != path_digest(b)


def test_c006_individual_prefixes_are_valid_before_forbidden_final_step():
    states = [
        state("G1", {"G1": "ACTIVE"}),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}),
        state("G3", {"G1": "RETIRED", "G2": "RETIRED", "G3": "ACTIVE"}),
        state("G1", {"G1": "ACTIVE", "G2": "RETIRED", "G3": "RETIRED"}),
    ]
    transitions = [transition("G1", "G2"), transition("G2", "G3"), transition("G3", "G1")]
    prefix = validate_history(states[:3], transitions[:2])
    complete = validate_history(states, transitions)
    assert prefix.constitutional_valid
    assert not complete.constitutional_valid


def test_c007_later_event_can_close_a_path_and_reveal_a_prior_violation():
    states = [
        state("G1", {"G1": "ACTIVE"}),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}),
        state("G3", {"G1": "RETIRED", "G2": "RETIRED", "G3": "ACTIVE"}),
        state("G3", {"G1": "RETIRED", "G2": "RETIRED", "G3": "ACTIVE"}),
    ]
    transitions = [
        transition("G1", "G2", event_type="PROVISIONAL_CHANGE"),
        transition("G2", "G3", event_type="AUTHORITY_CHANGE"),
        transition("G3", "G3", event_type="STABILIZE"),
    ]
    # The first prefix is locally valid; the second change is the point at
    # which the deferred path rule is violated. The later STABILIZE event does
    # not erase that violation.
    prefix = validate_history(states[:2], transitions[:1])
    complete = validate_history(states, transitions)
    assert prefix.constitutional_valid
    assert not complete.path_valid
    assert not complete.constitutional_valid


def test_c008_intermediate_composition_failure_cannot_be_hidden_by_a_valid_final_state():
    states = [
        state("G1", {"G1": "ACTIVE"}, evaluator_version=1, approval_threshold="ELEVATED"),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}, evaluator_version=2, approval_threshold="STANDARD"),
        state("G3", {"G1": "RETIRED", "G2": "RETIRED", "G3": "ACTIVE"}, evaluator_version=1, approval_threshold="ELEVATED"),
    ]
    transitions = [transition("G1", "G2"), transition("G2", "G3")]
    report = validate_history(states, transitions)
    assert not report.composition_valid
    assert not report.constitutional_valid
    assert any("evaluator v2 cannot operate with STANDARD approval" in f.message for f in report.findings)


def test_c009_full_path_digest_binds_state_snapshots_not_only_transition_endpoints():
    states_a = [
        state("G1", {"G1": "ACTIVE"}),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}),
    ]
    states_b = [
        state("G1", {"G1": "ACTIVE"}),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}, evaluator_version=2, approval_threshold="ELEVATED"),
    ]
    transitions = [transition("G1", "G2")]
    assert path_digest(transitions) == path_digest(transitions)
    assert full_path_digest(states_a, transitions) != full_path_digest(states_b, transitions)


def test_c010_full_path_digest_changes_when_semantically_relevant_state_changes():
    states_a = [
        state("G1", {"G1": "ACTIVE"}, evaluator_version=1),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}, evaluator_version=1),
    ]
    states_b = [
        state("G1", {"G1": "ACTIVE"}, evaluator_version=1),
        state("G2", {"G1": "RETIRED", "G2": "ACTIVE"}, evaluator_version=2),
    ]
    transitions = [transition("G1", "G2")]
    assert full_path_digest(states_a, transitions) != full_path_digest(states_b, transitions)
