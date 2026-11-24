"""Graph-level semantic integrity for Ψ-SEED CACC history.

Local persistence checks answer: "is this record structurally valid?"
Semantic integrity answers: "can these individually valid records jointly mean
what the CACC contract says they mean?"

This module is deliberately read-mostly. It derives findings from authoritative
history and does not rewrite historical facts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

SI_CAUSAL_CHAIN = "SI-001"
SI_TEMPORAL_ORDER = "SI-002"
SI_ROLLED_BACK_TRANSITION = "SI-003"
SI_INVALIDATED_EVIDENCE = "SI-004"
SI_LIFECYCLE_CONTRADICTION = "SI-005"
SI_DEVELOPMENTAL_INELIGIBLE = "SI-006"
SI_REPLAY_MISMATCH = "SI-007"
SI_REVISION_CHRONOLOGY = "SI-008"
SI_EVENT_REVISION_COHERENCE = "SI-009"

CORE_ORDER = (
    "possibility",
    "evaluation",
    "candidate_selection",
    "governance_decision",
    "choice",
    "transition_transaction",
    "cacc_outcome",
)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _issue(code: str, issue: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "issue": issue, **details}


def _entities(history: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result = {}
    for entity in history.get("entities", []):
        result[str(entity["id"])] = entity
    for revision in history.get("revisions", []):
        eid = str(revision["entity_id"])
        if eid not in result:
            result[eid] = revision
    return result


def _relationships(history: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return list(history.get("relationships", []))


def _chain_of(entity: Mapping[str, Any] | None) -> str | None:
    if not entity:
        return None
    return entity.get("causation_chain_id") or entity.get("payload", {}).get("causation_chain_id")


def _time_of(entity: Mapping[str, Any] | None) -> datetime | None:
    if not entity:
        return None
    payload = entity.get("payload", {})
    for key in ("timestamp", "decision_time", "selected_at", "decided_at", "evaluated_at", "created_at"):
        value = entity.get(key, payload.get(key))
        parsed = _parse_time(value)
        if parsed is not None:
            return parsed
    return None


def _rollback_transition_ids(history: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    entities = _entities(history)
    for entity in entities.values():
        if entity.get("entity_type") == "transition_rollback":
            tid = entity.get("transition_id", entity.get("payload", {}).get("transition_id"))
            if tid:
                ids.add(str(tid))
    for rel in _relationships(history):
        if rel.get("relationship_type") == "ROLLBACK_OF_TRANSITION":
            source = entities.get(str(rel.get("source_id")))
            target = entities.get(str(rel.get("target_id")))
            if source and source.get("entity_type") == "transition_transaction":
                ids.add(str(source["id"]))
            elif target and target.get("entity_type") == "transition_transaction":
                ids.add(str(target["id"]))
    return ids


def _outcome_transition_map(history: Mapping[str, Any]) -> dict[str, str]:
    entities = _entities(history)
    result: dict[str, str] = {}
    for entity in entities.values():
        if entity.get("entity_type") == "cacc_outcome":
            tid = entity.get("transition_id", entity.get("payload", {}).get("transition_id"))
            if tid:
                result[str(entity["id"])] = str(tid)
    return result


def validate_semantic_integrity(history: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic graph-level semantic integrity report.

    Findings are derived only from authoritative history. No finding deletes,
    edits, or retroactively changes the historical fact that caused it.
    """
    entities = _entities(history)
    rels = _relationships(history)
    issues: list[dict[str, Any]] = []
    rollback_transitions = _rollback_transition_ids(history)
    outcome_transition = _outcome_transition_map(history)

    # SI-001: every causal joint and payload node must remain in one chain.
    for rel in rels:
        chain = rel.get("metadata", {}).get("causation_chain_id")
        if not chain:
            continue
        source = entities.get(str(rel.get("source_id")))
        target = entities.get(str(rel.get("target_id")))
        if source and _chain_of(source) and _chain_of(source) != chain:
            issues.append(_issue(SI_CAUSAL_CHAIN, "CAUSAL_CHAIN_MISMATCH", relationship_id=rel.get("id"), endpoint="source", expected=chain, actual=_chain_of(source)))
        if target and _chain_of(target) and _chain_of(target) != chain:
            issues.append(_issue(SI_CAUSAL_CHAIN, "CAUSAL_CHAIN_MISMATCH", relationship_id=rel.get("id"), endpoint="target", expected=chain, actual=_chain_of(target)))

    # SI-002: a consequence cannot precede the transition it claims to observe.
    for outcome_id, transition_id in outcome_transition.items():
        outcome = entities.get(outcome_id)
        transition = entities.get(transition_id)
        ot = _time_of(outcome)
        tt = _time_of(transition)
        if ot is not None and tt is not None and ot < tt:
            issues.append(_issue(SI_TEMPORAL_ORDER, "OUTCOME_PRECEDES_TRANSITION", outcome_id=outcome_id, transition_id=transition_id, transition_time=tt.isoformat(), outcome_time=ot.isoformat()))

    # SI-008 / SI-009: revision chronology and revision-event coherence.
    by_entity: dict[str, list[Mapping[str, Any]]] = {}
    events = {str(e.get("id")): e for e in history.get("events", [])}
    for revision in history.get("revisions", []):
        by_entity.setdefault(str(revision.get("entity_id")), []).append(revision)
    for entity_id, revisions in sorted(by_entity.items()):
        revisions = sorted(revisions, key=lambda r: int(r.get("version", 0)))
        expected_version = 1
        previous_time = None
        previous_version = None
        for revision in revisions:
            version = int(revision.get("version", 0))
            if version != expected_version:
                issues.append(_issue(SI_REVISION_CHRONOLOGY, "REVISION_VERSION_GAP", entity_id=entity_id, expected_version=expected_version, actual_version=version))
            current_time = _parse_time(revision.get("created_at"))
            if previous_time is not None and current_time is not None and current_time < previous_time:
                issues.append(_issue(SI_REVISION_CHRONOLOGY, "REVISION_TIME_INVERSION", entity_id=entity_id, previous_version=previous_version, previous_time=previous_time.isoformat(), version=version, created_at=current_time.isoformat()))
            event_id = revision.get("revision_event_id")
            if event_id:
                event = events.get(str(event_id))
                if event is None:
                    issues.append(_issue(SI_EVENT_REVISION_COHERENCE, "REVISION_EVENT_MISSING", entity_id=entity_id, version=version, revision_event_id=event_id))
                else:
                    event_time = _parse_time(event.get("occurred_at"))
                    if current_time is not None and event_time is not None and event_time > current_time:
                        issues.append(_issue(SI_EVENT_REVISION_COHERENCE, "REVISION_PRECEDES_ITS_EVENT", entity_id=entity_id, version=version, revision_event_id=event_id, revision_time=current_time.isoformat(), event_time=event_time.isoformat()))
                    refs = {str(x) for x in event.get("related_entity_refs", [])}
                    if refs and entity_id not in refs:
                        issues.append(_issue(SI_EVENT_REVISION_COHERENCE, "REVISION_EVENT_MISSING_ENTITY_REF", entity_id=entity_id, version=version, revision_event_id=event_id))
            previous_time = current_time or previous_time
            previous_version = version
            expected_version = version + 1

    # SI-003 / SI-005: rollback is a lifecycle boundary. Historical outcomes
    # remain facts, but no later authoritative success may attach to the rolled-back transition.
    for outcome_id, transition_id in outcome_transition.items():
        if transition_id in rollback_transitions:
            outcome = entities.get(outcome_id)
            transition = entities.get(transition_id)
            ot = _time_of(outcome)
            rollback_times = []
            for entity in entities.values():
                if entity.get("entity_type") == "transition_rollback" and str(entity.get("transition_id", entity.get("payload", {}).get("transition_id"))) == transition_id:
                    rt = _time_of(entity)
                    if rt is not None:
                        rollback_times.append(rt)
            if rollback_times and ot is not None and any(ot > rt for rt in rollback_times):
                issues.append(_issue(SI_ROLLED_BACK_TRANSITION, "OUTCOME_AFTER_ROLLBACK", outcome_id=outcome_id, transition_id=transition_id))

    # SI-004 / SI-006: developmental evidence cannot silently promote an outcome
    # whose causal transition has been rolled back. Existing historical evidence
    # remains preserved and is reported as ineligible rather than deleted.
    for entity in entities.values():
        if entity.get("entity_type") != "developmental_evidence":
            continue
        refs = entity.get("outcome_refs", entity.get("payload", {}).get("outcome_refs", [])) or []
        for outcome_id in refs:
            transition_id = outcome_transition.get(str(outcome_id))
            if transition_id in rollback_transitions:
                issues.append(_issue(SI_INVALIDATED_EVIDENCE, "EVIDENCE_FROM_ROLLED_BACK_OUTCOME", evidence_id=entity.get("id"), outcome_id=outcome_id, transition_id=transition_id))
                issues.append(_issue(SI_DEVELOPMENTAL_INELIGIBLE, "DEVELOPMENTAL_EVIDENCE_INELIGIBLE", evidence_id=entity.get("id"), outcome_id=outcome_id, reason="causal transition rolled back"))

    # SI-005: an authoritative transition marked rolled_back cannot also claim
    # a current committed lifecycle state.
    for entity in entities.values():
        if entity.get("entity_type") != "transition_transaction":
            continue
        status = entity.get("status", entity.get("payload", {}).get("status"))
        if entity.get("id") in rollback_transitions and str(status).upper() in {"COMMITTED", "ACTIVE"}:
            issues.append(_issue(SI_LIFECYCLE_CONTRADICTION, "ROLLED_BACK_TRANSITION_RETAINS_ACTIVE_STATUS", transition_id=entity.get("id"), status=status))

    return {
        "contract_version": "0.11",
        "valid": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "rollback_transition_ids": sorted(rollback_transitions),
    }


def assert_semantic_integrity(history: Mapping[str, Any]) -> dict[str, Any]:
    report = validate_semantic_integrity(history)
    if not report["valid"]:
        raise ValueError(f"Semantic integrity failure: {report['issues']}")
    return report
