import copy
import pytest

from contracts.semantic_authority_transition import (
    unsafe_classify_diff,
    unsafe_transition_is_admissible,
    safe_projection,
)


def base_manifest():
    return {
        "manifest_id": "SRM-001",
        "manifest_version": "0.11.5",
        "description": "semantic relevance manifest",
        "revisions.payload": "authoritative",
        "events": "authoritative",
        "outcomes": "authoritative",
        "failures": "authoritative",
        "relationships": "authoritative",
        "revisions": {"payload": "authoritative"},
        "transition_classification": "SAFE",
        "required_approval": "STANDARD",
    }


def test_rt201_self_declared_safe_classification_can_hide_semantic_change():
    old = base_manifest()
    new = copy.deepcopy(old)
    new["revisions.payload"] = "non_semantic"
    new["transition_classification"] = "SAFE"
    assert unsafe_transition_is_admissible(old, new)
    assert old["revisions.payload"] != new["revisions.payload"]


def test_rt202_unknown_semantic_path_is_silently_ignored():
    old = base_manifest()
    new = copy.deepcopy(old)
    new["unknown_semantic_rule"] = {"meaning": "authoritative"}
    c = unsafe_classify_diff(old, new)
    assert c.category == "SAFE"
    assert unsafe_transition_is_admissible(old, new)


def test_rt203_nested_semantic_change_hidden_behind_unclassified_container():
    old = base_manifest()
    new = copy.deepcopy(old)
    new["governance"] = {"semantic_policy": {"unknown_fields": "ALLOW"}}
    c = unsafe_classify_diff(old, new)
    assert c.category == "SAFE"
    assert unsafe_transition_is_admissible(old, new)


def test_rt204_approval_threshold_can_be_downgraded_inside_same_transition():
    old = base_manifest()
    old["required_approval"] = "ELEVATED"
    new = copy.deepcopy(old)
    new["revisions.payload"] = "non_semantic"
    new["required_approval"] = "STANDARD"
    c = unsafe_classify_diff(old, new)
    assert c.required_approval == "STANDARD"
    assert unsafe_transition_is_admissible(old, new)


def test_rt205_two_step_policy_weakening_is_individually_safe_but_collectively_dangerous():
    m1 = base_manifest()
    m2 = copy.deepcopy(m1)
    m2["governance"] = {"unknown_fields": "ALLOW"}
    m2["transition_classification"] = "SAFE"
    m3 = copy.deepcopy(m2)
    m3["revisions.payload"] = "non_semantic"
    m3["transition_classification"] = "SAFE"
    assert unsafe_transition_is_admissible(m1, m2)
    assert unsafe_transition_is_admissible(m2, m3)
    assert m2["revisions.payload"] != m3["revisions.payload"]


def test_rt206_rollback_can_reactivate_generation_that_forward_policy_would_reject():
    safe = base_manifest()
    dangerous = copy.deepcopy(safe)
    dangerous["revisions.payload"] = "non_semantic"
    dangerous["transition_classification"] = "SAFE"
    # The vulnerable classifier accepts the dangerous generation.
    assert unsafe_transition_is_admissible(safe, dangerous)
    # A later rollback to it therefore has no independent semantic gate.
    assert unsafe_transition_is_admissible(safe, dangerous)


def test_rt207_evaluator_substitution_is_not_a_safe_transition():
    old = base_manifest()
    new = copy.deepcopy(old)
    new["classifier_version"] = "attacker-lenient-v2"
    # The vulnerable classifier does not treat evaluator identity as protected.
    assert unsafe_transition_is_admissible(old, new)
    assert new["classifier_version"] != old.get("classifier_version")


def test_rt208_alias_rename_can_change_meaning_without_touching_known_path():
    old = base_manifest()
    new = copy.deepcopy(old)
    # Remove the recognized semantic path and replace it with an alias.
    # The vulnerable classifier only compares exact known paths, so the
    # removal itself is classified, but the replacement meaning is invisible.
    del new["revisions.payload"]
    new["revision.payload"] = "non_semantic"
    new["transition_classification"] = "SAFE"
    c = unsafe_classify_diff(old, new)
    assert c.category == "SAFE"
    assert unsafe_transition_is_admissible(old, new)
