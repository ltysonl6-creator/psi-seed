"""Semantic convergence red-team helpers for Ψ-SEED.

This module attacks the semantic interpretation boundary by asking whether
meaningful historical differences can collapse to the same interpretation.
It also records the deliberate equivalence class of changes that are allowed
to be ignored (mutable current projections and integrity manifests).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from contracts.semantic_replay import semantic_interpretation

SC_001 = "SC-001"  # meaningful history must not converge
SC_002 = "SC-002"  # non-authoritative projection may converge
SC_003 = "SC-003"  # integrity metadata is not semantic meaning


def compare_meaning(history_a: Mapping[str, Any], history_b: Mapping[str, Any]) -> dict[str, Any]:
    a = semantic_interpretation(history_a)
    b = semantic_interpretation(history_b)
    return {
        "equivalent": a == b and a["interpretation_digest"] == b["interpretation_digest"],
        "a_digest": a["interpretation_digest"],
        "b_digest": b["interpretation_digest"],
        "a": a,
        "b": b,
    }


def mutate_nonsemantic_projection(history: Mapping[str, Any]) -> dict[str, Any]:
    """Change only mutable export projection fields intentionally excluded from meaning."""
    result = deepcopy(history)
    for entity in result.get("entities", []):
        entity["updated_at"] = "2099-01-01T00:00:00+00:00"
        entity["current_version"] = 999999
        entity["payload"] = {"poisoned_projection": True}
    result["integrity"] = {"root": "attacker-controlled"}
    return result


def mutate_semantic_history(history: Mapping[str, Any]) -> dict[str, Any]:
    """Change an authoritative revision payload: this MUST change meaning."""
    result = deepcopy(history)
    revisions = result.get("revisions", [])
    if revisions:
        revisions[0]["payload"] = deepcopy(revisions[0].get("payload", {}))
        revisions[0]["payload"]["semantic_attack"] = "changed"
        # export_authoritative_history duplicates payload keys at the revision root.
        revisions[0]["semantic_attack"] = "changed"
    return result
