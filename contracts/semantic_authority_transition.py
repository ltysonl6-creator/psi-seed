"""Red-team reference model for SMA-002 semantic authority transitions.

This module deliberately exposes common unsafe classifier designs so tests can
prove the attacks. It is not presented as the final production implementation.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Classification:
    category: str
    required_approval: str
    reasons: tuple[str, ...] = ()


# UNSAFE: only a handful of known paths are classified. Everything else is
# silently treated as non-semantic.
KNOWN_PATHS = {
    "manifest_version": "metadata",
    "description": "metadata",
    "revisions.payload": "semantic",
    "events": "semantic",
    "outcomes": "semantic",
    "failures": "semantic",
    "relationships": "semantic",
}


def unsafe_classify_diff(old: Mapping[str, Any], new: Mapping[str, Any]) -> Classification:
    """A deliberately vulnerable classifier used by the red-team tests."""
    reasons: list[str] = []
    category = "SAFE"
    approval = "STANDARD"

    # UNSAFE: caller-controlled self declaration. If present, it overrides
    # the evaluator result rather than merely being an input to it.
    declared = new.get("transition_classification")

    # UNSAFE: only exact known paths are inspected.
    for path, kind in KNOWN_PATHS.items():
        old_value = old.get(path)
        new_value = new.get(path)
        if old_value != new_value:
            reasons.append(path)
            if kind == "semantic":
                category = "MEANING_CHANGING"
                approval = "ELEVATED"

    # UNSAFE: caller can lower approval in the same transition.
    if new.get("required_approval") == "STANDARD":
        approval = "STANDARD"

    # UNSAFE: self-declared category is applied after the actual diff scan.
    if declared in {"SAFE", "MEANING_EXPANDING", "MEANING_REDUCING", "INCOMPATIBLE", "CONSTITUTIONAL"}:
        category = declared

    return Classification(category, approval, tuple(reasons))


def unsafe_transition_is_admissible(old: Mapping[str, Any], new: Mapping[str, Any]) -> bool:
    c = unsafe_classify_diff(old, new)
    return c.category in {"SAFE", "MEANING_EXPANDING"} and c.required_approval in {"STANDARD", "ELEVATED"}


def safe_projection(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Illustrative semantic projection used to detect classifier blindness."""
    return {
        "revisions": deepcopy(manifest.get("revisions", {})),
        "events": deepcopy(manifest.get("events", {})),
        "outcomes": deepcopy(manifest.get("outcomes", {})),
        "failures": deepcopy(manifest.get("failures", {})),
        "relationships": deepcopy(manifest.get("relationships", {})),
    }
