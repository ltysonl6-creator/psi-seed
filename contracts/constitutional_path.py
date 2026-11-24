"""Path-aware constitutional validation for Ψ-SEED.

This module is deliberately small and deterministic.  It separates:
- state validity: is the current configuration allowed?
- transition validity: is this individual change allowed?
- composition validity: does the resulting configuration remain allowed?
- path validity: was the ordered history a permitted way to arrive there?

The path validator does not treat hashes as trust.  A path digest identifies a
canonical path; an independent trusted root is still required to establish
which history is authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


CONTRACT_ID = "C-001..C-004"


@dataclass(frozen=True)
class PathFinding:
    code: str
    valid: bool
    message: str


@dataclass(frozen=True)
class ConstitutionalPathReport:
    state_valid: bool
    transitions_valid: bool
    composition_valid: bool
    path_valid: bool
    constitutional_valid: bool
    findings: tuple[PathFinding, ...]
    path_digest: str


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def path_digest(history: Sequence[Mapping[str, Any]]) -> str:
    """Return a deterministic digest over the ordered transition history.

    This legacy helper intentionally remains transition-only for compatibility.
    For constitutional authority, use :func:`full_path_digest`, which binds the
    ordered transitions to the ordered state snapshots they claim to produce.
    """
    previous = "GENESIS"
    for index, transition in enumerate(history):
        record = {"index": index, "previous": previous, "transition": transition}
        previous = sha256(_canonical(record).encode("utf-8")).hexdigest()
    return previous


def full_path_digest(
    states: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
) -> str:
    """Return a deterministic digest over the complete ordered path.

    State snapshots are part of the path identity because the same transition
    endpoints can otherwise conceal different semantic configuration changes.
    """
    previous = "GENESIS"
    for index, transition in enumerate(transitions):
        record = {
            "index": index,
            "previous": previous,
            "before_state": states[index],
            "transition": transition,
            "after_state": states[index + 1],
        }
        previous = sha256(_canonical(record).encode("utf-8")).hexdigest()
    return previous


def validate_state(state: Mapping[str, Any]) -> PathFinding:
    """Example constitutional state rule: exactly one active generation."""
    active = state.get("active_generation")
    generations = state.get("generations", {})
    active_count = sum(1 for status in generations.values() if status == "ACTIVE")
    if active is None or active_count != 1 or generations.get(active) != "ACTIVE":
        return PathFinding("C-STATE-001", False, "state does not have exactly one active generation")
    return PathFinding("C-STATE-001", True, "state has exactly one active generation")


def validate_transition(previous: Mapping[str, Any], current: Mapping[str, Any], transition: Mapping[str, Any]) -> PathFinding:
    """Validate the local transition shape without inspecting the whole path."""
    if transition.get("from") != previous.get("active_generation"):
        return PathFinding("C-TRANS-001", False, "transition predecessor does not match current state")
    if transition.get("to") != current.get("active_generation"):
        return PathFinding("C-TRANS-002", False, "transition successor does not match resulting state")
    return PathFinding("C-TRANS-001", True, "transition endpoints match adjacent states")


def validate_composition(state: Mapping[str, Any], history: Sequence[Mapping[str, Any]]) -> PathFinding:
    """Validate a simple resulting-state rule against the effective history."""
    # Example compositional rule: an evaluator version may not be paired with
    # STANDARD approval.  This intentionally uses the resulting configuration,
    # not merely the fields touched by the latest transition.
    if state.get("evaluator_version") == 2 and state.get("approval_threshold") == "STANDARD":
        return PathFinding("C-COMP-001", False, "evaluator v2 cannot operate with STANDARD approval")
    return PathFinding("C-COMP-001", True, "resulting authority configuration is compositionally valid")


def validate_deferred_closure(history: Sequence[Mapping[str, Any]]) -> PathFinding:
    """Validate a non-local rule closed by a later event.

    A PROVISIONAL authority change requires a STABILIZE event before another
    authority change. The individual changes and the eventual STABILIZE event
    can each look locally valid; the complete path is invalid if the required
    stabilizer was skipped.
    """
    provisional = False
    for index, event in enumerate(history):
        kind = event.get("event_type", "transition")
        if kind == "PROVISIONAL_CHANGE":
            if provisional:
                return PathFinding("C-PATH-002", False, f"path step {index} performs a second provisional change before stabilization")
            provisional = True
        elif kind == "STABILIZE":
            provisional = False
        elif kind == "AUTHORITY_CHANGE":
            if provisional:
                return PathFinding("C-PATH-002", False, f"path step {index} closes a path that skipped required stabilization")
    return PathFinding("C-PATH-002", True, "deferred path closure rule satisfied")


def validate_path(history: Sequence[Mapping[str, Any]]) -> PathFinding:
    """Validate path-dependent constitutional rules.

    Rule used here: once a generation is retired, it may not become active again.
    This cannot be inferred from the final configuration alone.
    """
    retired: set[str] = set()
    active: str | None = None
    for index, transition in enumerate(history):
        source = transition.get("from")
        target = transition.get("to")
        if active is None:
            active = source
        if source != active:
            return PathFinding("C-PATH-001", False, f"path step {index} does not continue from prior active generation")
        if target in retired:
            return PathFinding("C-PATH-001", False, f"path step {index} reactivates retired generation {target}")
        retired.add(source)
        active = target
    return PathFinding("C-PATH-001", True, "ordered path satisfies retirement recurrence rule")


def validate_history(
    states: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
) -> ConstitutionalPathReport:
    """Validate a complete authoritative state/transition path."""
    findings: list[PathFinding] = []
    if len(states) != len(transitions) + 1:
        findings.append(PathFinding("C-PATH-000", False, "state/transition cardinality mismatch"))
        digest = path_digest(transitions)
        return ConstitutionalPathReport(False, False, False, False, False, tuple(findings), digest)

    state_results = [validate_state(state) for state in states]
    findings.extend(state_results)
    state_valid = all(result.valid for result in state_results)

    transition_results = [
        validate_transition(states[i], states[i + 1], transitions[i])
        for i in range(len(transitions))
    ]
    findings.extend(transition_results)
    transitions_valid = all(result.valid for result in transition_results)

    composition_results = [
        validate_composition(state, transitions[:index])
        for index, state in enumerate(states)
    ]
    findings.extend(composition_results)
    composition_valid = all(result.valid for result in composition_results)

    path_result = validate_path(transitions)
    findings.append(path_result)
    deferred_result = validate_deferred_closure(transitions)
    findings.append(deferred_result)
    path_valid = path_result.valid and deferred_result.valid

    return ConstitutionalPathReport(
        state_valid=state_valid,
        transitions_valid=transitions_valid,
        composition_valid=composition_valid,
        path_valid=path_valid,
        constitutional_valid=state_valid and transitions_valid and composition_valid and path_valid,
        findings=tuple(findings),
        path_digest=full_path_digest(states, transitions),
    )


@dataclass(frozen=True)
class HistoryAuthorityReport:
    complete: bool
    sequence_valid: bool
    lineage_valid: bool
    uniqueness_valid: bool
    anchored: bool
    authoritative_valid: bool
    findings: tuple[PathFinding, ...]


def _record_digest(record: Mapping[str, Any]) -> str:
    return sha256(_canonical(record).encode("utf-8")).hexdigest()


def validate_authoritative_history(
    states: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
    *,
    history_complete: bool,
    expected_genesis: str = "GENESIS",
    expected_terminal: str | None = None,
    expected_terminal_digest: str | None = None,
) -> HistoryAuthorityReport:
    """Validate that a presented path is an authoritative *complete* history.

    ``validate_history`` answers whether the supplied sequence is internally
    constitutional.  It intentionally permits a valid prefix because prefixes
    are useful during live operation.  This function answers the stronger
    question needed at an authority boundary: can this presentation stand in
    for the complete history?

    Each transition must carry a stable ``transition_id``, a zero-based
    ``sequence`` number, and a ``parent_digest`` chaining it to the prior
    transition.  The first record chains to ``expected_genesis``.  A complete
    history must explicitly declare completeness and, when requested, the
    expected terminal transition and its externally anchored digest.

    ``expected_terminal`` is retained for compatibility.  Production authority
    should supply ``expected_terminal_digest`` as well; an identifier alone is
    not sufficient to bind the terminal record's contents.
    """
    findings: list[PathFinding] = []
    sequence_valid = True
    lineage_valid = True
    uniqueness_valid = True
    anchored = True

    if not history_complete:
        findings.append(PathFinding("C-AUTH-001", False, "presented history is explicitly incomplete"))
    else:
        findings.append(PathFinding("C-AUTH-001", True, "presented history declares completeness"))

    if len(states) != len(transitions) + 1:
        sequence_valid = False
        findings.append(PathFinding("C-AUTH-006", False, "state/transition cardinality does not describe one complete linear path"))

    ids: set[str] = set()
    previous_digest = expected_genesis
    for index, transition in enumerate(transitions):
        tid = transition.get("transition_id")
        seq = transition.get("sequence")
        parent = transition.get("parent_digest")

        if not isinstance(tid, str) or not tid:
            uniqueness_valid = False
            findings.append(PathFinding("C-AUTH-002", False, f"path step {index} has no stable transition_id"))
        elif tid in ids:
            uniqueness_valid = False
            findings.append(PathFinding("C-AUTH-002", False, f"duplicate transition_id {tid}"))
        else:
            ids.add(tid)

        if seq != index:
            sequence_valid = False
            findings.append(PathFinding("C-AUTH-003", False, f"path step {index} has sequence {seq!r}, expected {index}"))

        if parent != previous_digest:
            lineage_valid = False
            findings.append(PathFinding("C-AUTH-004", False, f"path step {index} has incorrect parent_digest"))

        previous_digest = _record_digest(transition)

    if expected_terminal is None and expected_terminal_digest is None:
        anchored = False
        findings.append(PathFinding("C-AUTH-005", False, "complete history has no external terminal anchor"))
    elif expected_terminal_digest is None:
        anchored = False
        findings.append(PathFinding("C-AUTH-007", False, "terminal anchor identifies a record but does not externally bind its contents"))
    elif not transitions:
        anchored = False
        findings.append(PathFinding("C-AUTH-005", False, "empty history cannot satisfy expected terminal anchor"))
    else:
        terminal = transitions[-1]
        if expected_terminal is not None and terminal.get("transition_id") != expected_terminal:
            anchored = False
            findings.append(PathFinding("C-AUTH-005", False, "presented history does not terminate at expected authoritative transition"))
        if expected_terminal_digest is not None and _record_digest(terminal) != expected_terminal_digest:
            anchored = False
            findings.append(PathFinding("C-AUTH-005", False, "presented terminal record does not match externally anchored digest"))
        if expected_terminal is None and expected_terminal_digest is not None:
            findings.append(PathFinding("C-AUTH-005", True, "terminal record is bound by external digest"))

    # A complete authoritative presentation cannot be an arbitrary prefix.
    # The constitutional validator remains separately responsible for semantic
    # validity of the states/transitions themselves.
    if not transitions and history_complete:
        findings.append(PathFinding("C-AUTH-006", True, "empty genesis history is complete only when no terminal anchor is required"))

    authoritative_valid = (
        history_complete
        and sequence_valid
        and lineage_valid
        and uniqueness_valid
        and anchored
    )
    return HistoryAuthorityReport(
        complete=history_complete,
        sequence_valid=sequence_valid,
        lineage_valid=lineage_valid,
        uniqueness_valid=uniqueness_valid,
        anchored=anchored,
        authoritative_valid=authoritative_valid,
        findings=tuple(findings),
    )
