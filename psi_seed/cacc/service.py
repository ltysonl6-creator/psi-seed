"""Persistence-facing CACC-001 joint service."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
import copy
import hashlib
import json
from typing import Any, Mapping, Sequence

from contracts.cacc_joint_validation import (
    CACCJointValidationError, validate_choice, validate_transition, validate_outcome
)
from contracts.semantic_integrity import validate_semantic_integrity
from contracts.cacc_relationship_types import (
    POSSIBILITY_EVALUATED_BY, EVALUATION_SELECTED_AS_CANDIDATE,
    CANDIDATE_GOVERNED_BY, GOVERNANCE_AUTHORIZES_CHOICE, CHOICE_EXECUTES_TRANSITION,
    TRANSITION_PRODUCES_OUTCOME, OUTCOME_PERSISTED_AS_EVIDENCE,
    EVIDENCE_FORMS_EPISODE, EPISODE_SUPPORTS_RULE,
    FAILURE_FROM_TRANSITION, ROLLBACK_OF_TRANSITION,
    DEVELOPMENT_CHANGES_POSSIBILITY_SPACE,
)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"

class CACCService:
    """Create CACC objects and persist their causal edges on an existing backend."""

    def __init__(self, backend):
        self.backend = backend

    def _create(self, entity_type: str, payload: Mapping[str, Any]):
        data = dict(payload)
        data.setdefault("id", _id(entity_type))
        data.setdefault("entity_type", entity_type)
        data.setdefault("status", "active")
        data.setdefault("created_at", _now())
        data.setdefault("provenance", {})
        return self.backend.create_record(data)

    def _relate(self, source_id: str, target_id: str, relationship_type: str,
                chain_id: str, metadata: Mapping[str, Any] | None = None):
        return self.backend.create_relationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            metadata={
                **dict(metadata or {}),
                "causation_chain_id": chain_id,
                "contract": "CACC-JOINTS-001",
            },
            relationship_id=_id("rel"),
        )

    def create_possibility(self, payload: Mapping[str, Any]):
        return self._create("possibility", payload)

    def record_evaluation(self, payload: Mapping[str, Any]):
        with self.backend.atomic():
            if self.backend.get(payload["possibility_id"]) is None:
                raise CACCJointValidationError("Unknown possibility")
            result = self._create("evaluation", payload)
            self._relate(payload["possibility_id"], result["id"],
                         POSSIBILITY_EVALUATED_BY, payload["causation_chain_id"])
            return result

    def select_candidate(self, payload: Mapping[str, Any]):
        with self.backend.atomic():
            if self.backend.get(payload["evaluation_id"]) is None:
                raise CACCJointValidationError("Unknown evaluation")
            result = self._create("candidate_selection", payload)
            self._relate(payload["evaluation_id"], result["id"],
                         EVALUATION_SELECTED_AS_CANDIDATE, payload["causation_chain_id"])
            return result

    def record_governance(self, payload: Mapping[str, Any]):
        with self.backend.atomic():
            candidate = self.backend.get(payload["candidate_id"])
            if candidate is None:
                raise CACCJointValidationError("Unknown candidate")
            if candidate.get("entity_type") != "candidate_selection":
                raise CACCJointValidationError("candidate_id must reference a candidate_selection")
            result = self._create("governance_decision", payload)
            self._relate(payload["candidate_id"], result["id"],
                         CANDIDATE_GOVERNED_BY, payload["causation_chain_id"])
            return result

    def create_choice(self, payload: Mapping[str, Any]):
        with self.backend.atomic():
            payload = dict(payload)
            payload.setdefault("choice_id", payload.get("id", _id("choice")))
            payload.setdefault("id", payload["choice_id"])
            governance = self.backend.get(payload["governance_decision_id"])
            candidate = self.backend.get(payload["candidate_id"])
            possibility = self.backend.get(payload["possibility_id"])
            if governance is None:
                raise CACCJointValidationError("Unknown governance decision")
            if candidate is None or candidate.get("entity_type") != "candidate_selection":
                raise CACCJointValidationError("candidate_id must reference a candidate_selection")
            if possibility is None or possibility.get("entity_type") != "possibility":
                raise CACCJointValidationError("possibility_id must reference a possibility")
            if governance.get("candidate_id") != payload["candidate_id"]:
                raise CACCJointValidationError("Governance candidate_id does not match Choice candidate_id")
            if candidate.get("possibility_id") != payload["possibility_id"]:
                raise CACCJointValidationError("Choice possibility_id does not match candidate selection")
            validate_choice(payload, governance)
            result = self._create("choice", payload)
            self._relate(payload["governance_decision_id"], result["id"],
                         GOVERNANCE_AUTHORIZES_CHOICE, payload["causation_chain_id"])
            return result

    def create_transition(self, payload: Mapping[str, Any]):
        with self.backend.atomic():
            payload = dict(payload)
            payload.setdefault("transition_id", payload.get("id", _id("transition")))
            payload.setdefault("id", payload["transition_id"])
            choice = self.backend.get(payload["choice_id"])
            if choice is None or choice.get("entity_type") != "choice":
                raise CACCJointValidationError("choice_id must reference an authoritative Choice")
            validate_transition(payload, choice)
            result = self._create("transition_transaction", payload)
            self._relate(payload["choice_id"], result["id"],
                         CHOICE_EXECUTES_TRANSITION, payload["causation_chain_id"])
            return result

    def record_outcome(self, payload: Mapping[str, Any]):
        with self.backend.atomic():
            transition = self.backend.get(payload["transition_id"])
            if transition is None or transition.get("entity_type") != "transition_transaction":
                raise CACCJointValidationError("transition_id must reference a transition_transaction")
            payload = dict(payload)
            payload.setdefault("outcome_id", payload.get("id", _id("outcome")))
            payload.setdefault("id", payload["outcome_id"])
            if payload.get("causation_chain_id") != transition.get("causation_chain_id"):
                raise CACCJointValidationError("Outcome causation_chain_id must match Transition causation_chain_id")
            if str(transition.get("status", "")).upper() in {"ROLLED_BACK", "INVALIDATED"}:
                raise CACCJointValidationError("A rolled-back or invalidated Transition cannot produce a new authoritative Outcome")
            transition_time = transition.get("timestamp", transition.get("created_at"))
            outcome_time = payload.get("timestamp")
            from datetime import datetime
            if transition_time and outcome_time:
                try:
                    tt = datetime.fromisoformat(str(transition_time).replace("Z", "+00:00"))
                    ot = datetime.fromisoformat(str(outcome_time).replace("Z", "+00:00"))
                except ValueError:
                    tt = ot = None
                if tt is not None and ot is not None and ot < tt:
                    raise CACCJointValidationError("Outcome timestamp cannot precede Transition timestamp")
            validate_outcome(payload, transition)
            result = self._create("cacc_outcome", payload)
            self._relate(payload["transition_id"], result["id"],
                         TRANSITION_PRODUCES_OUTCOME, payload["causation_chain_id"])
            return result

    def link_developmental_evidence(self, evidence_id: str,
                                    outcome_refs: Sequence[str], chain_id: str):
        with self.backend.atomic():
            if not outcome_refs:
                raise CACCJointValidationError("Evidence requires at least one outcome")
            for ref in outcome_refs:
                outcome = self.backend.get(ref)
                if outcome is None or outcome.get("entity_type") != "cacc_outcome":
                    raise CACCJointValidationError(f"Unknown outcome: {ref}")
                transition_id = outcome.get("transition_id")
                transition = self.backend.get(transition_id) if transition_id else None
                if transition and str(transition.get("status", "")).upper() in {"ROLLED_BACK", "INVALIDATED"}:
                    raise CACCJointValidationError(f"Outcome {ref} is ineligible for developmental evidence because its transition was rolled back")
                if transition and transition.get("causation_chain_id") != chain_id:
                    raise CACCJointValidationError(f"Outcome {ref} does not belong to causation chain {chain_id}")
            result = self._create("developmental_evidence", {
                "id": evidence_id, "outcome_refs": list(outcome_refs),
                "causation_chain_id": chain_id, "created_at": _now(),
            })
            for ref in outcome_refs:
                self._relate(ref, evidence_id, OUTCOME_PERSISTED_AS_EVIDENCE, chain_id)
            return result

    def create_developmental_episode(self, payload: Mapping[str, Any]):
        """Create an Episode and atomically attach its developmental evidence."""
        with self.backend.atomic():
            evidence_id = payload.get("evidence_id")
            if not evidence_id or self.backend.get(evidence_id) is None:
                raise CACCJointValidationError("Episode requires an existing developmental evidence record")
            episode_id = payload.get("episode_id", payload.get("id", _id("episode")))
            data = dict(payload)
            data.setdefault("id", episode_id)
            data.setdefault("entity_type", "developmental_episode")
            data.setdefault("status", "opened")
            data.setdefault("causation_chain_id", payload["causation_chain_id"])
            result = self._create("developmental_episode", data)
            self._relate(evidence_id, result["id"], EVIDENCE_FORMS_EPISODE, payload["causation_chain_id"])
            return result

    def create_developmental_rule(self, payload: Mapping[str, Any]):
        """Create a DevelopmentalRule and atomically attach its source Episode."""
        with self.backend.atomic():
            episode_id = payload.get("episode_id")
            if not episode_id or self.backend.get(episode_id) is None:
                raise CACCJointValidationError("Rule requires an existing developmental episode")
            data = dict(payload)
            rule_id = data.get("rule_id", data.get("id", _id("rule")))
            data.setdefault("id", rule_id)
            data.setdefault("entity_type", "developmental_rule")
            data.setdefault("status", "active")
            data.setdefault("causation_chain_id", payload["causation_chain_id"])
            result = self._create("developmental_rule", data)
            self._relate(episode_id, result["id"], EPISODE_SUPPORTS_RULE, payload["causation_chain_id"])
            return result

    def create_developmental_change(self, payload: Mapping[str, Any]):
        """Create a developmental change and atomically link it to a future possibility."""
        with self.backend.atomic():
            rule_id = payload.get("rule_id")
            possibility_id = payload.get("possibility_id")
            if not rule_id or self.backend.get(rule_id) is None:
                raise CACCJointValidationError("Developmental change requires an existing rule")
            possibility = self.backend.get(possibility_id) if possibility_id else None
            if possibility is None or possibility.get("entity_type") != "possibility":
                raise CACCJointValidationError("Developmental change requires a future possibility")
            data = dict(payload)
            change_id = data.get("change_id", data.get("id", _id("development")))
            data.setdefault("id", change_id)
            data.setdefault("entity_type", "developmental_change")
            data.setdefault("status", "committed")
            data.setdefault("causation_chain_id", payload["causation_chain_id"])
            result = self._create("developmental_change", data)
            self._relate(result["id"], possibility_id, DEVELOPMENT_CHANGES_POSSIBILITY_SPACE, payload["causation_chain_id"], {"role": "future_possibility", "rule_id": rule_id})
            return result

    def link_episode(self, episode_id: str, evidence_id: str, chain_id: str):
        with self.backend.atomic():
            episode = self.backend.get(episode_id)
            evidence = self.backend.get(evidence_id)
            if episode is None or episode.get("entity_type") != "developmental_episode":
                raise CACCJointValidationError("episode_id must reference a developmental_episode")
            if evidence is None or evidence.get("entity_type") != "developmental_evidence":
                raise CACCJointValidationError("evidence_id must reference developmental_evidence")
            self._relate(evidence_id, episode_id, EVIDENCE_FORMS_EPISODE, chain_id)
            return self.backend.get(episode_id)

    def link_rule(self, rule_id: str, episode_id: str, chain_id: str):
        with self.backend.atomic():
            rule = self.backend.get(rule_id)
            episode = self.backend.get(episode_id)
            if rule is None or rule.get("entity_type") != "developmental_rule":
                raise CACCJointValidationError("rule_id must reference a developmental_rule")
            if episode is None or episode.get("entity_type") != "developmental_episode":
                raise CACCJointValidationError("episode_id must reference a developmental_episode")
            self._relate(episode_id, rule_id, EPISODE_SUPPORTS_RULE, chain_id)
            return self.backend.get(rule_id)

    def link_failure(self, failure_id: str, transition_id: str, chain_id: str):
        with self.backend.atomic():
            transition = self.backend.get(transition_id)
            failure = self.backend.get(failure_id)
            if transition is None or transition.get("entity_type") != "transition_transaction":
                raise CACCJointValidationError("transition_id must reference a transition_transaction")
            if failure is None:
                raise CACCJointValidationError("Unknown failure record")
            self._relate(transition_id, failure_id, FAILURE_FROM_TRANSITION, chain_id)

    def link_rollback(self, rollback_id: str, transition_id: str, chain_id: str):
        with self.backend.atomic():
            transition = self.backend.get(transition_id)
            rollback = self.backend.get(rollback_id)
            if transition is None or transition.get("entity_type") != "transition_transaction":
                raise CACCJointValidationError("transition_id must reference a transition_transaction")
            if rollback is None:
                raise CACCJointValidationError("Unknown rollback record")
            self._relate(transition_id, rollback_id, ROLLBACK_OF_TRANSITION, chain_id)

    def rollback_state(
        self,
        entity_id: str,
        target_version: int,
        *,
        reason: str = "",
        expected_history_root: str | None = None,
        rollback_id: str | None = None,
        chain_id: str | None = None,
        transition_id: str | None = None,
    ):
        """Restore an entity's current state from immutable history.

        The rollback is itself a new persisted fact. Historical revisions and
        events are retained, and the resulting state receives a new version.
        """
        result = self.backend.rollback_entity_state(
            entity_id,
            target_version,
            reason=reason,
            expected_history_root=expected_history_root,
            rollback_id=rollback_id,
            causation_ref=chain_id,
        )
        if chain_id and transition_id:
            with self.backend.atomic():
                transition = self.backend.get(transition_id)
                if transition is None or transition.get("entity_type") != "transition_transaction":
                    raise CACCJointValidationError("transition_id must reference a transition_transaction")
                rollback_entity = self._create("transition_rollback", {
                    "id": result["rollback_id"],
                    "rollback_id": result["rollback_id"],
                    "transition_id": transition_id,
                    "entity_id": entity_id,
                    "target_version": target_version,
                    "result_version": result["result_version"],
                    "reason": reason,
                    "causation_chain_id": chain_id,
                    "status": "committed",
                })
                self._relate(transition_id, rollback_entity["id"], ROLLBACK_OF_TRANSITION, chain_id, {"state_rollback_event_id": result["event_id"]})
                result = dict(result)
                result["rollback_entity_id"] = rollback_entity["id"]
        return result

    def rollback_transition(self, transition_id: str, rollback_id: str | None = None, reason: str = "", chain_id: str | None = None):
        """Record a rollback as a new immutable fact; never rewrite the transition."""
        with self.backend.atomic():
            transition = self.backend.get(transition_id)
            if transition is None or transition.get("entity_type") != "transition_transaction":
                raise CACCJointValidationError("transition_id must reference a transition_transaction")
            cid = chain_id or transition.get("causation_chain_id")
            if not cid:
                raise CACCJointValidationError("Rollback requires a causation_chain_id")
            rid = rollback_id or _id("rollback")
            before = copy.deepcopy(transition.get("before_snapshot", {}))
            rollback = self._create("transition_rollback", {
                "id": rid,
                "rollback_id": rid,
                "transition_id": transition_id,
                "restored_state": before,
                "reason": reason,
                "causation_chain_id": cid,
                "status": "committed",
            })
            self._relate(transition_id, rollback["id"], ROLLBACK_OF_TRANSITION, cid)
            # Rollback is a lifecycle boundary. The original transition remains
            # immutable history, but its current authoritative lifecycle state
            # becomes ROLLED_BACK through a new revision.
            self.backend.revise_entity(transition_id, status="ROLLED_BACK")
            return rollback

    def validate_semantic_integrity(self) -> Mapping[str, Any]:
        """Audit authoritative history for graph-level semantic contradictions."""
        return validate_semantic_integrity(self.backend.export_authoritative_history())

    def assert_semantic_integrity(self) -> Mapping[str, Any]:
        report = self.validate_semantic_integrity()
        if not report["valid"]:
            raise CACCJointValidationError(f"Semantic integrity failure: {report['issues']}")
        return report

    def rebuild_fresh_from_authoritative_history(self, history: Mapping[str, Any]):
        """Create a new persistence instance from authoritative history only."""
        from psi_seed.persistence.sqlite.backend import SQLitePersistenceBackend
        return SQLitePersistenceBackend.from_authoritative_history(history)

    @staticmethod
    def semantic_projection(backend: Any) -> Mapping[str, Any]:
        """Project durable meaning, excluding mutable current-state fields."""
        h = backend.export_authoritative_history()
        return {
            "entity_identity": sorted(h.get("entity_identity", []), key=lambda x: str(x["id"])),
            "revisions": sorted(h.get("revisions", []), key=lambda x: (str(x["entity_id"]), int(x["version"]))),
            "events": sorted(h.get("events", []), key=lambda x: (int(x["sequence"]), str(x["id"]))),
            "outcomes": sorted(h.get("outcomes", []), key=lambda x: str(x["id"])),
            "failures": sorted(h.get("failures", []), key=lambda x: str(x["id"])),
            "relationships": sorted(h.get("relationships", []), key=lambda x: str(x["id"])),
        }

    def assert_fresh_rebuild_semantically_equivalent(self, history: Mapping[str, Any], source_backend: Any):
        fresh = self.rebuild_fresh_from_authoritative_history(history)
        source_semantic = self.semantic_projection_from_history(history)
        fresh_semantic = self.semantic_projection(fresh)
        if source_semantic != fresh_semantic:
            fresh.close()
            raise CACCJointValidationError("Fresh rebuild is not semantically equivalent to authoritative history")
        return fresh

    def semantic_replay(self, history: Mapping[str, Any], fresh_history: Mapping[str, Any]) -> Mapping[str, Any]:
        """Compare source and fresh histories at the level of semantic interpretation."""
        from contracts.semantic_replay import semantic_replay
        return semantic_replay(history, fresh_history)

    def verify_authoritative_history(self, history: Mapping[str, Any], expected_root: str | None = None) -> Mapping[str, Any]:
        """Verify an authoritative export before replay/reconstruction."""
        return self.backend.verify_history_integrity(history, expected_root)

    @staticmethod
    def semantic_projection_from_history(history: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "entity_identity": sorted(history.get("entity_identity", []), key=lambda x: str(x["id"])),
            "revisions": sorted(history.get("revisions", []), key=lambda x: (str(x["entity_id"]), int(x["version"]))),
            "events": sorted(history.get("events", []), key=lambda x: (int(x["sequence"]), str(x["id"]))),
            "outcomes": sorted(history.get("outcomes", []), key=lambda x: str(x["id"])),
            "failures": sorted(history.get("failures", []), key=lambda x: str(x["id"])),
            "relationships": sorted(history.get("relationships", []), key=lambda x: str(x["id"])),
        }

    def replay_cacc_chain(self, chain_id: str) -> Mapping[str, Any]:
        """Deterministically replay the authoritative exported chain and return a digest.

        Replay here means rebuilding the causal projection from exported authoritative
        history without mutating the live database. It is intentionally separate from
        executing domain actions again.
        """
        history = self.backend.export_authoritative_history()
        rebuilt = self.backend.reconstruct_from_history(history)
        rels = [r for r in rebuilt["relationships"]
                if r.get("metadata", {}).get("causation_chain_id") == chain_id]
        entities = {}
        ids = set()
        for r in rels:
            ids.update((r["source_id"], r["target_id"]))
        for eid in sorted(ids):
            if eid in rebuilt["entities"]:
                entities[eid] = rebuilt["entities"][eid]
        projection = {
            "chain_id": chain_id,
            "entities": entities,
            "relationships": rels,
        }
        canonical = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        projection["digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return projection

    def reconstruct_cacc_chain_from_backend(self, backend: Any, chain_id: str) -> Mapping[str, Any]:
        """Run CACC reconstruction against an explicitly supplied backend."""
        original = self.backend
        try:
            self.backend = backend
            return self.reconstruct_cacc_chain(chain_id)
        finally:
            self.backend = original

    def reconstruct_cacc_chain(self, chain_id: str) -> Mapping[str, Any]:
        """Reconstruct and verify the persisted CACC chain for one causation id."""
        relationships = [
            r for r in self.backend.get_relationships()
            if r["metadata"].get("causation_chain_id") == chain_id
        ]
        nodes = {}
        for r in relationships:
            for entity_id in (r["source_id"], r["target_id"]):
                entity = self.backend.get(entity_id)
                if entity is not None:
                    nodes[entity_id] = entity

        core_required = {
            POSSIBILITY_EVALUATED_BY,
            EVALUATION_SELECTED_AS_CANDIDATE,
            CANDIDATE_GOVERNED_BY,
            GOVERNANCE_AUTHORIZES_CHOICE,
            CHOICE_EXECUTES_TRANSITION,
            TRANSITION_PRODUCES_OUTCOME,
        }
        tail_types = {
            OUTCOME_PERSISTED_AS_EVIDENCE,
            EVIDENCE_FORMS_EPISODE,
            EPISODE_SUPPORTS_RULE,
            DEVELOPMENT_CHANGES_POSSIBILITY_SPACE,
        }
        required = set(core_required)
        if any(r["relationship_type"] in tail_types for r in relationships):
            required |= tail_types
        issues = []
        present = {r["relationship_type"] for r in relationships}
        for rel_type in sorted(required - present):
            issues.append({"code": "CACC-V-001", "issue": "MISSING_REQUIRED_JOINT", "relationship_type": rel_type})

        expected_types = {
            POSSIBILITY_EVALUATED_BY: ("possibility", "evaluation"),
            EVALUATION_SELECTED_AS_CANDIDATE: ("evaluation", "candidate_selection"),
            CANDIDATE_GOVERNED_BY: ("candidate_selection", "governance_decision"),
            GOVERNANCE_AUTHORIZES_CHOICE: ("governance_decision", "choice"),
            CHOICE_EXECUTES_TRANSITION: ("choice", "transition_transaction"),
            TRANSITION_PRODUCES_OUTCOME: ("transition_transaction", "cacc_outcome"),
            OUTCOME_PERSISTED_AS_EVIDENCE: ("cacc_outcome", "developmental_evidence"),
            EVIDENCE_FORMS_EPISODE: ("developmental_evidence", "developmental_episode"),
            EPISODE_SUPPORTS_RULE: ("developmental_episode", "developmental_rule"),
            DEVELOPMENT_CHANGES_POSSIBILITY_SPACE: ("developmental_change", "possibility"),
        }
        for r in relationships:
            if r["source_id"] not in nodes or r["target_id"] not in nodes:
                issues.append({"code": "CACC-V-002", "issue": "ORPHANED_JOINT", "relationship_id": r["id"]})
                continue
            if r["metadata"].get("causation_chain_id") != chain_id:
                issues.append({"code": "CACC-V-003", "issue": "CAUSATION_CHAIN_MISMATCH", "relationship_id": r["id"]})
            expected = expected_types.get(r["relationship_type"])
            if expected and (nodes[r["source_id"]].get("entity_type"), nodes[r["target_id"]].get("entity_type")) != expected:
                issues.append({"code": "CACC-V-005", "issue": "JOINT_ENDPOINT_TYPE_MISMATCH", "relationship_id": r["id"], "expected": expected})

        # Validate payload references against the actual causal edges. This prevents
        # a payload from being silently rewired while its relationship graph remains intact.
        payload_expectations = {
            GOVERNANCE_AUTHORIZES_CHOICE: ("governance_decision_id", "target_id"),
            CHOICE_EXECUTES_TRANSITION: ("choice_id", "target_id"),
            TRANSITION_PRODUCES_OUTCOME: ("transition_id", "target_id"),
            EVIDENCE_FORMS_EPISODE: ("evidence_id", "target_id"),
            EPISODE_SUPPORTS_RULE: ("episode_id", "target_id"),
        }
        for r in relationships:
            spec = payload_expectations.get(r["relationship_type"])
            if spec:
                field, endpoint = spec
                entity = nodes.get(r[endpoint], {})
                if entity.get(field) != r["source_id"]:
                    issues.append({"code": "CACC-V-006", "issue": "PAYLOAD_JOINT_REFERENCE_MISMATCH", "relationship_id": r["id"], "field": field})

        # Historical preservation check: current payload must agree with its latest revision.
        for entity_id in sorted(nodes):
            history = list(self.backend.get_history(entity_id))
            if history:
                latest = history[-1]
                current = nodes[entity_id]
                if current.get("payload") != latest.get("payload"):
                    issues.append({"code": "CACC-V-007", "issue": "CURRENT_PAYLOAD_DIFFERS_FROM_AUTHORITATIVE_REVISION", "entity_id": entity_id})

        def exactly_one(rel_type):
            return [r for r in relationships if r["relationship_type"] == rel_type]

        for rel_type in sorted(required):
            rs = exactly_one(rel_type)
            if len(rs) > 1:
                issues.append({"code": "CACC-V-004", "issue": "DUPLICATE_REQUIRED_JOINT", "relationship_type": rel_type, "count": len(rs)})

        return {
            "chain_id": chain_id,
            "valid": not issues,
            "issues": issues,
            "relationships": relationships,
            "entities": nodes,
        }

    def assert_cacc_chain_integrity(self, chain_id: str) -> Mapping[str, Any]:
        result = self.reconstruct_cacc_chain(chain_id)
        if not result["valid"]:
            raise CACCJointValidationError(f"CACC chain integrity failure: {result['issues']}")
        return result

