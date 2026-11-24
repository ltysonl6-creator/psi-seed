"""Pure CACC joint validation rules."""
from __future__ import annotations
from typing import Any, Mapping

class CACCJointValidationError(ValueError):
    """A CACC causal-joint contract was violated."""

def require_ref(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise CACCJointValidationError(f"{field} must be a non-empty reference")
    return value

def validate_choice(choice: Mapping[str, Any], governance: Mapping[str, Any]) -> None:
    require_ref(choice, "choice_id")
    for field in ("possibility_id", "candidate_id", "governance_decision_id"):
        require_ref(choice, field)
    if governance.get("result") != "PERMITTED":
        raise CACCJointValidationError(
            "A committed Choice requires governance result PERMITTED"
        )

def validate_transition(transition: Mapping[str, Any], choice: Mapping[str, Any]) -> None:
    require_ref(transition, "transition_id")
    if transition.get("choice_id") != choice.get("choice_id"):
        raise CACCJointValidationError(
            "Transition choice_id must match the authoritative Choice"
        )
    for field in ("before_snapshot", "proposed_state", "evidence_delta", "post_state"):
        if field not in transition:
            raise CACCJointValidationError(f"Transition missing {field}")

def validate_outcome(outcome: Mapping[str, Any], transition: Mapping[str, Any]) -> None:
    require_ref(outcome, "outcome_id")
    if outcome.get("transition_id") != transition.get("transition_id"):
        raise CACCJointValidationError(
            "Outcome transition_id must match the authoritative Transition"
        )
