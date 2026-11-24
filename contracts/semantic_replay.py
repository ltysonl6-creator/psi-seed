"""Deterministic semantic replay for Ψ-SEED CACC.

Semantic replay answers a stronger question than byte equality:
can an independent fresh instance derive the same meaning from authoritative
history, and is that meaning itself temporally and causally coherent?

This module is read-mostly. It never edits authoritative history.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Mapping

from contracts.semantic_integrity import (
    SI_REPLAY_MISMATCH,
    validate_semantic_integrity,
)
from contracts.semantic_relevance_manifest import (
    semantic_projection,
    validate_semantic_relevance_manifest,
)

SI_REVISION_CHRONOLOGY = "SI-008"
SI_EVENT_REVISION_COHERENCE = "SI-009"
SI_REPLAY_INTERPRETATION = "SI-010"


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _issue(code: str, issue: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "issue": issue, **details}


def _revision_chronology(history: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    by_entity: dict[str, list[Mapping[str, Any]]] = {}
    for rev in history.get("revisions", []):
        by_entity.setdefault(str(rev["entity_id"]), []).append(rev)

    events = {str(e["id"]): e for e in history.get("events", [])}
    for entity_id, revisions in sorted(by_entity.items()):
        revisions = sorted(revisions, key=lambda r: int(r["version"]))
        expected = 1
        previous_time: datetime | None = None
        previous_version: int | None = None
        for rev in revisions:
            version = int(rev["version"])
            if version != expected:
                issues.append(_issue(
                    SI_REVISION_CHRONOLOGY,
                    "REVISION_VERSION_GAP",
                    entity_id=entity_id,
                    expected_version=expected,
                    actual_version=version,
                ))
            current_time = _parse_time(rev.get("created_at"))
            if previous_time is not None and current_time is not None and current_time < previous_time:
                issues.append(_issue(
                    SI_REVISION_CHRONOLOGY,
                    "REVISION_TIME_INVERSION",
                    entity_id=entity_id,
                    previous_version=previous_version,
                    previous_time=previous_time.isoformat(),
                    version=version,
                    created_at=current_time.isoformat(),
                ))
            event_id = rev.get("revision_event_id")
            if event_id:
                event = events.get(str(event_id))
                if event is None:
                    issues.append(_issue(
                        SI_EVENT_REVISION_COHERENCE,
                        "REVISION_EVENT_MISSING",
                        entity_id=entity_id,
                        version=version,
                        revision_event_id=event_id,
                    ))
                else:
                    event_time = _parse_time(event.get("occurred_at"))
                    if current_time is not None and event_time is not None and event_time > current_time:
                        issues.append(_issue(
                            SI_EVENT_REVISION_COHERENCE,
                            "REVISION_PRECEDES_ITS_EVENT",
                            entity_id=entity_id,
                            version=version,
                            revision_event_id=event_id,
                            revision_time=current_time.isoformat(),
                            event_time=event_time.isoformat(),
                        ))
                    refs = {str(x) for x in event.get("related_entity_refs", [])}
                    if refs and entity_id not in refs:
                        issues.append(_issue(
                            SI_EVENT_REVISION_COHERENCE,
                            "REVISION_EVENT_MISSING_ENTITY_REF",
                            entity_id=entity_id,
                            version=version,
                            revision_event_id=event_id,
                        ))
            previous_time = current_time or previous_time
            previous_version = version
            expected = version + 1
    return issues


def semantic_interpretation(history: Mapping[str, Any]) -> dict[str, Any]:
    """Return the deterministic meaning-bearing projection of authoritative history."""
    manifest_report = validate_semantic_relevance_manifest(history)
    integrity = validate_semantic_integrity(history)
    chronology = _revision_chronology(history)
    issues = list(manifest_report["issues"]) + list(integrity["issues"]) + chronology
    projected = semantic_projection(history)

    # Meaning includes the full authoritative causal/history trace, not merely
    # the latest current-state projection.
    meaning = {
        "contract_version": "0.11",
        "semantic_integrity_valid": not issues,
        "issues": issues,
        "rollback_transition_ids": integrity.get("rollback_transition_ids", []),
        "manifest_version": manifest_report["manifest"]["manifest_version"],
        "manifest_id": manifest_report["manifest"]["manifest_id"],
        **{section: sorted(values, key=lambda x: str(x) if not isinstance(x, Mapping) else str(x.get("id", x.get("entity_id", "")))) for section, values in projected.items()},
    }
    meaning["interpretation_digest"] = _digest(meaning)
    return meaning


def semantic_replay(history: Mapping[str, Any], fresh_history: Mapping[str, Any]) -> dict[str, Any]:
    """Compare two authoritative histories at the level of semantic interpretation."""
    source = semantic_interpretation(history)
    fresh = semantic_interpretation(fresh_history)
    equal = source["interpretation_digest"] == fresh["interpretation_digest"] and source == fresh
    issues: list[dict[str, Any]] = []
    if not equal:
        issues.append(_issue(
            SI_REPLAY_INTERPRETATION,
            "SEMANTIC_INTERPRETATION_MISMATCH",
            source_digest=source["interpretation_digest"],
            fresh_digest=fresh["interpretation_digest"],
        ))
    return {
        "contract_version": "0.11",
        "equivalent": equal,
        "source": source,
        "fresh": fresh,
        "issues": issues,
        "digest": _digest({"source": source, "fresh": fresh, "issues": issues}),
    }


def authorized_semantic_interpretation(history: Mapping[str, Any], authority: Any,
                                       manifest_record: Mapping[str, Any] | None) -> dict[str, Any]:
    """Semantic interpretation that fails closed unless the manifest is trusted."""
    from contracts.semantic_manifest_authority import validate_manifest_authority
    report = validate_manifest_authority(history, authority, manifest_record)
    if not report["valid"]:
        return {
            "contract_version": "0.11.5",
            "semantic_integrity_valid": False,
            "issues": report["issues"],
            "interpretation_digest": _digest(report["issues"]),
        }
    return semantic_interpretation(history)
