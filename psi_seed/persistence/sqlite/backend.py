"""SQLite implementation of the Ψ-SEED persistence backend contract."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import uuid
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .errors import (
    ImmutableEventError,
    PersistenceError,
    ValidationError,
    VersionConflictError,
)
from .schema import initialize_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load(value: str) -> Any:
    return json.loads(value)


def _hash_event(event: Mapping[str, Any]) -> str:
    canonical = dict(event)
    canonical.pop("integrity_hash", None)
    return hashlib.sha256(_json(canonical).encode("utf-8")).hexdigest()


class SQLitePersistenceBackend:
    """Durable SQLite backend satisfying the Ψ-SEED persistence test surface."""

    def __init__(self, database_path: str | os.PathLike[str] | None = None):
        self._lock = threading.RLock()
        self._temporary = database_path is None

        if database_path is None:
            fd, path = tempfile.mkstemp(prefix="psi_seed_", suffix=".sqlite3")
            os.close(fd)
            self.database_path = path
        else:
            self.database_path = str(database_path)
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            self.database_path,
            timeout=10.0,
            isolation_level=None,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        initialize_connection(self._conn)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def reload(self):
        return type(self)(self.database_path)

    def _begin(self) -> None:
        self._conn.execute("BEGIN IMMEDIATE")

    def _commit(self) -> None:
        self._conn.commit()

    def _rollback(self) -> None:
        self._conn.rollback()

    @contextmanager
    def atomic(self):
        """Run a multi-write operation as one SQLite transaction."""
        with self._lock:
            if self._conn.in_transaction:
                # Nested atomic blocks share the enclosing transaction.
                yield
                return
            try:
                self._begin()
                yield
                self._commit()
            except Exception:
                self._rollback()
                raise

    # ------------------------------------------------------------------
    # Generic entities
    # ------------------------------------------------------------------

    def _insert_entity(self, record: Mapping[str, Any]) -> dict[str, Any]:
        entity_id = str(record.get("id", _id(str(record.get("entity_type", "entity")))))
        entity_type = str(record.get("entity_type", "entity"))
        status = str(record.get("status", "active"))
        now = str(record.get("created_at", _now()))
        updated = str(record.get("updated_at", now))
        version = int(record.get("version", 1))

        if version != 1:
            raise ValidationError("New entities must begin at version 1")

        reserved = {
            "id", "entity_type", "created_at", "updated_at", "version",
            "status", "payload", "provenance",
        }
        payload = copy.deepcopy(dict(record.get("payload", {})))
        for key, value in record.items():
            if key not in reserved:
                payload[key] = copy.deepcopy(value)

        provenance = copy.deepcopy(dict(record.get("provenance", {})))

        self._conn.execute(
            """INSERT INTO entities
               (id, entity_type, created_at, updated_at, current_version,
                status, payload_json, provenance_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity_id, entity_type, now, updated, version, status,
                _json(payload), _json(provenance),
            ),
        )

        self._conn.execute(
            """INSERT INTO entity_revisions
               (entity_id, version, created_at, payload_json, provenance_json, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entity_id, version, now, _json(payload), _json(provenance), status),
        )

        return self.get(entity_id)

    def create_record(self, record: Mapping[str, Any]) -> Mapping[str, Any]:
        with self._lock:
            if self._conn.in_transaction:
                try:
                    return self._insert_entity(record)
                except sqlite3.IntegrityError as exc:
                    raise PersistenceError(str(exc)) from exc
            try:
                self._begin()
                result = self._insert_entity(record)
                self._commit()
                return result
            except sqlite3.IntegrityError as exc:
                self._rollback()
                raise PersistenceError(str(exc)) from exc
            except Exception:
                self._rollback()
                raise

    def _row_entity(self, row) -> dict[str, Any]:
        payload = _load(row["payload_json"])
        result = {
            "id": row["id"],
            "entity_type": row["entity_type"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "version": row["current_version"],
            "status": row["status"],
            "payload": copy.deepcopy(payload),
            "provenance": _load(row["provenance_json"]),
        }
        # Domain fields are exposed directly for the contract tests while
        # payload remains available as the canonical serialized body.
        result.update(copy.deepcopy(payload))
        return result

    def get(self, entity_id: str) -> Mapping[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ).fetchone()
        return None if row is None else self._row_entity(row)

    def _require(self, entity_id: str):
        row = self._conn.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ).fetchone()
        if row is None:
            raise ValidationError(f"Unknown entity: {entity_id}")
        return row

    def _payload(self, row) -> dict[str, Any]:
        return _load(row["payload_json"])

    def revise_entity(self, entity_id: str, changes: Mapping[str, Any] | None = None, *, status: str | None = None) -> Mapping[str, Any]:
        """Version every current-state mutation, including non-belief entities.

        The operation is transaction-aware: when called inside ``atomic()`` it
        participates in the enclosing transaction rather than opening a nested
        SQLite transaction.
        """
        with self._lock:
            row = self._require(entity_id)
            current_version = int(row["current_version"])
            new_version = current_version + 1
            payload = self._payload(row)
            if changes:
                payload.update(copy.deepcopy(dict(changes)))
            next_status = str(status if status is not None else row["status"])
            provenance = copy.deepcopy(_load(row["provenance_json"]))
            provenance["revised_from_version"] = current_version
            now = _now()
            nested = self._conn.in_transaction
            try:
                if not nested:
                    self._begin()
                cur = self._conn.execute(
                    "UPDATE entities SET current_version = ?, status = ?, updated_at = ?, payload_json = ?, provenance_json = ? WHERE id = ? AND current_version = ?",
                    (new_version, next_status, now, _json(payload), _json(provenance), entity_id, current_version),
                )
                if cur.rowcount != 1:
                    raise VersionConflictError(f"Concurrent revision conflict for {entity_id}")
                self._conn.execute(
                    "INSERT INTO entity_revisions (entity_id, version, created_at, payload_json, provenance_json, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (entity_id, new_version, now, _json(payload), _json(provenance), next_status),
                )
                result = self.get(entity_id)
                if not nested:
                    self._commit()
                return result
            except Exception:
                if not nested:
                    self._rollback()
                raise

    # ------------------------------------------------------------------
    # Beliefs and revisions
    # ------------------------------------------------------------------

    def create_belief(self, record: Mapping[str, Any] | None = None, **kwargs) -> Mapping[str, Any]:
        data = dict(record or {})
        data.update(kwargs)
        data.setdefault("entity_type", "belief")
        data.setdefault("status", "active")
        data.setdefault("provenance", {})
        return self.create_record(data)

    def update_belief(self, entity_id: str, changes: Mapping[str, Any]) -> Mapping[str, Any]:
        """Versioned compatibility alias; no unversioned state mutation is allowed."""
        return self.revise_belief(entity_id, changes)

    def revise_belief(self, entity_id: str, changes: Mapping[str, Any]) -> Mapping[str, Any]:
        with self._lock:
            row = self._require(entity_id)
            current_version = int(row["current_version"])
            new_version = current_version + 1

            payload = self._payload(row)
            payload.update(copy.deepcopy(dict(changes)))
            provenance = _load(row["provenance_json"])
            provenance = copy.deepcopy(provenance)
            provenance["revised_from_version"] = current_version
            now = _now()

            try:
                self._begin()
                cur = self._conn.execute(
                    """UPDATE entities
                       SET current_version = ?, updated_at = ?,
                           status = ?, payload_json = ?, provenance_json = ?
                       WHERE id = ? AND current_version = ?""",
                    (
                        new_version, now, row["status"], _json(payload), _json(provenance),
                        entity_id, current_version,
                    ),
                )
                if cur.rowcount != 1:
                    raise VersionConflictError(
                        f"Concurrent revision conflict for {entity_id}"
                    )

                self._conn.execute(
                    """INSERT INTO entity_revisions
                       (entity_id, version, created_at, payload_json, provenance_json, status)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        entity_id, new_version, now,
                        _json(payload), _json(provenance), row["status"],
                    ),
                )
                result = self.get(entity_id)
                self._commit()
                return result
            except Exception:
                self._rollback()
                raise

    def rollback_entity_state(
        self,
        entity_id: str,
        target_version: int,
        *,
        reason: str = "",
        expected_history_root: str | None = None,
        rollback_id: str | None = None,
        causation_ref: str | None = None,
        correlation_ref: str | None = None,
    ) -> Mapping[str, Any]:
        """Restore current state from an immutable historical revision.

        This is a *state rollback*, not a history rewrite. The target revision
        remains untouched; the restored state is appended as a fresh revision
        with a new version. The rollback event and outcome are committed in the
        same transaction as the state change.
        """
        with self._lock:
            try:
                self._begin()

                # Lock the logical state before reading current_version so two
                # connections cannot prepare the same stale rollback revision.
                if expected_history_root is not None:
                    history = self.export_authoritative_history()
                    verification = self.verify_history_integrity(history, expected_history_root)
                    if not verification["valid"]:
                        raise ValidationError(
                            "Rollback refused: authoritative history failed trusted-root verification"
                        )

                row = self._require(entity_id)
                current_version = int(row["current_version"])
                target_version = int(target_version)
                if target_version < 1 or target_version > current_version:
                    raise ValidationError(
                        f"Rollback target version {target_version} is unavailable for {entity_id}"
                    )

                target_row = self._conn.execute(
                    """SELECT version, created_at, payload_json, provenance_json, status
                       FROM entity_revisions
                       WHERE entity_id = ? AND version = ?""",
                    (entity_id, target_version),
                ).fetchone()
                if target_row is None:
                    raise ValidationError(
                        f"Rollback target revision {target_version} not found for {entity_id}"
                    )

                target_payload = _load(target_row["payload_json"])
                target_provenance = _load(target_row["provenance_json"])
                target_status = str(target_row["status"])
                new_version = current_version + 1
                rid = rollback_id or _id("rollback")
                now = _now()
                event_id = _id("evt")

                rollback_payload = {
                    "rollback_id": rid,
                    "entity_id": entity_id,
                    "from_version": current_version,
                    "restore_target_version": target_version,
                    "reason": reason,
                    "target_state_digest": hashlib.sha256(
                        _json({"payload": target_payload, "provenance": target_provenance, "status": target_status}).encode("utf-8")
                    ).hexdigest(),
                    "restored_state_digest": hashlib.sha256(
                        _json({"payload": target_payload, "provenance": target_provenance}).encode("utf-8")
                    ).hexdigest(),
                    "result_version": new_version,
                    "history_rewrite": False,
                    "causation_ref": causation_ref,
                    "correlation_ref": correlation_ref,
                }

                provenance = copy.deepcopy(target_provenance)
                provenance.update({
                    "rollback_id": rid,
                    "rollback_from_version": current_version,
                    "rollback_target_version": target_version,
                    "rollback_reason": reason,
                    "rollback_event_id": event_id,
                })
                result_state_digest = hashlib.sha256(
                    _json({"payload": target_payload, "provenance": provenance, "status": target_status}).encode("utf-8")
                ).hexdigest()
                rollback_payload["result_state_digest"] = result_state_digest

                event = {
                    "id": event_id,
                    "event_type": "state_rollback",
                    "occurred_at": now,
                    "causation_ref": causation_ref,
                    "correlation_ref": correlation_ref,
                    "related_entity_refs": [entity_id],
                    "provenance": {"source": "rollback_entity_state"},
                    "payload": copy.deepcopy(rollback_payload),
                }
                event["sequence"] = self._next_event_sequence()
                event["integrity_hash"] = _hash_event(event)

                self._conn.execute(
                    """INSERT INTO events
                       (id, event_type, occurred_at, sequence,
                        causation_ref, correlation_ref,
                        related_entity_refs_json, provenance_json,
                        payload_json, integrity_hash,
                        correction_of_ref, supersedes_ref)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event["id"], event["event_type"], event["occurred_at"],
                        event["sequence"], event.get("causation_ref"),
                        event.get("correlation_ref"), _json(event["related_entity_refs"]),
                        _json(event["provenance"]), _json(event["payload"]),
                        event["integrity_hash"], None, None,
                    ),
                )

                cur = self._conn.execute(
                    """UPDATE entities
                       SET current_version = ?, updated_at = ?,
                           status = ?, payload_json = ?, provenance_json = ?
                       WHERE id = ? AND current_version = ?""",
                    (
                        new_version, now, target_status, _json(target_payload), _json(provenance),
                        entity_id, current_version,
                    ),
                )
                if cur.rowcount != 1:
                    raise VersionConflictError(
                        f"Concurrent rollback conflict for {entity_id}"
                    )

                self._conn.execute(
                    """INSERT INTO entity_revisions
                       (entity_id, version, created_at, payload_json,
                        provenance_json, status, revision_event_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entity_id, new_version, now, _json(target_payload),
                        _json(provenance), target_status, event_id,
                    ),
                )

                self._conn.execute(
                    """INSERT INTO outcomes
                       (id, entity_id, version, created_at, payload_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        f"outcome_{rid}", entity_id, new_version, now,
                        _json({
                            "outcome_type": "state_rollback",
                            "rollback_id": rid,
                            "result_version": new_version,
                            "restored_target_version": target_version,
                            "target_state_digest": rollback_payload["target_state_digest"],
                            "result_state_digest": rollback_payload["result_state_digest"],
                            "restored_status": target_status,
                            "history_rewrite": False,
                        }),
                    ),
                )

                result = self.get(entity_id)
                self._commit()
                return {
                    "rollback_id": rid,
                    "event_id": event_id,
                    "entity_id": entity_id,
                    "from_version": current_version,
                    "target_version": target_version,
                    "result_version": new_version,
                    "restored_state": result,
                    "history_rewrite": False,
                }
            except Exception:
                self._rollback()
                raise

    def get_history(self, entity_id: str) -> Sequence[Mapping[str, Any]]:
        rows = self._conn.execute(
            """SELECT entity_id, version, created_at, payload_json,
                      provenance_json, status, revision_event_id
               FROM entity_revisions
               WHERE entity_id = ?
               ORDER BY version ASC""",
            (entity_id,),
        ).fetchall()

        result = []
        for row in rows:
            payload = _load(row["payload_json"])
            item = {
                "entity_id": row["entity_id"],
                "version": row["version"],
                "created_at": row["created_at"],
                "payload": copy.deepcopy(payload),
                "provenance": _load(row["provenance_json"]),
                "status": row["status"],
                "revision_event_id": row["revision_event_id"],
            }
            item.update(copy.deepcopy(payload))
            result.append(item)
        return result

    # ------------------------------------------------------------------
    # Immutable events
    # ------------------------------------------------------------------

    def _next_event_sequence(self) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM events"
        ).fetchone()
        return int(row["next_sequence"])

    def append_event(self, event: Mapping[str, Any]) -> Mapping[str, Any]:
        e = dict(event)
        e.setdefault("id", _id("evt"))
        e.setdefault("occurred_at", _now())
        e.setdefault("related_entity_refs", [])
        e.setdefault("provenance", {})
        e.setdefault("payload", {})

        with self._lock:
            try:
                self._begin()
                e.setdefault("sequence", self._next_event_sequence())
                e["integrity_hash"] = _hash_event(e)

                self._conn.execute(
                    """INSERT INTO events
                       (id, event_type, occurred_at, sequence,
                        causation_ref, correlation_ref,
                        related_entity_refs_json, provenance_json,
                        payload_json, integrity_hash,
                        correction_of_ref, supersedes_ref)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        e["id"], e["event_type"], e["occurred_at"],
                        int(e["sequence"]), e.get("causation_ref"),
                        e.get("correlation_ref"), _json(e["related_entity_refs"]),
                        _json(e["provenance"]), _json(e["payload"]),
                        e["integrity_hash"], e.get("correction_of_ref"),
                        e.get("supersedes_ref"),
                    ),
                )
                result = self.get_event(e["id"])
                self._commit()
                return result
            except sqlite3.IntegrityError as exc:
                self._rollback()
                raise PersistenceError(str(exc)) from exc
            except Exception:
                self._rollback()
                raise

    def get_event(self, event_id: str) -> Mapping[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        if row is None:
            return None

        return {
            "id": row["id"],
            "event_type": row["event_type"],
            "occurred_at": row["occurred_at"],
            "sequence": row["sequence"],
            "causation_ref": row["causation_ref"],
            "correlation_ref": row["correlation_ref"],
            "related_entity_refs": _load(row["related_entity_refs_json"]),
            "provenance": _load(row["provenance_json"]),
            "payload": _load(row["payload_json"]),
            "integrity_hash": row["integrity_hash"],
            "correction_of_ref": row["correction_of_ref"],
            "supersedes_ref": row["supersedes_ref"],
        }

    def attempt_event_update(self, event_id: str, changes: Mapping[str, Any]) -> Any:
        if self.get_event(event_id) is None:
            raise ValidationError(f"Unknown event: {event_id}")
        # Contract tests intentionally call this operation without expecting
        # an exception, so the adapter treats it as a rejected no-op.
        return self.get_event(event_id)

    # ------------------------------------------------------------------
    # Self-modification and failures
    # ------------------------------------------------------------------

    def create_self_modification(
        self, record: Mapping[str, Any] | None = None, **kwargs
    ) -> Mapping[str, Any]:
        data = dict(record or {})
        data.update(kwargs)
        data.setdefault("entity_type", "self_modification")
        data.setdefault("status", "proposed")
        data.setdefault("provenance", {})
        return self.create_record(data)

    def evaluate_modification(self, entity_id: str):
        return self._set_status(entity_id, "evaluated")

    def approve_modification(self, entity_id: str):
        return self._set_status(entity_id, "approved")

    def execute_modification(self, entity_id: str):
        return self._set_status(entity_id, "executed")

    def set_modification_status(self, entity_id: str, status: str):
        return self._set_status(entity_id, status)

    def _set_status(self, entity_id: str, status: str):
        with self._lock:
            row = self._require(entity_id)
            current_version = int(row["current_version"])
            new_version = current_version + 1
            payload = self._payload(row)
            provenance = copy.deepcopy(_load(row["provenance_json"]))
            provenance["revised_from_version"] = current_version
            now = _now()
            try:
                self._begin()
                self._conn.execute(
                    "UPDATE entities SET current_version = ?, status = ?, updated_at = ? WHERE id = ? AND current_version = ?",
                    (new_version, status, now, entity_id, current_version),
                )
                self._conn.execute(
                    "INSERT INTO entity_revisions (entity_id, version, created_at, payload_json, provenance_json, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (entity_id, new_version, now, _json(payload), _json(provenance), status),
                )
                result = self.get(entity_id)
                self._commit()
                return result
            except Exception:
                self._rollback()
                raise

    def record_outcome(
        self, entity_id: str, outcome: Mapping[str, Any] | None = None, **kwargs
    ):
        self._require(entity_id)
        data = dict(outcome or {})
        data.update(kwargs)

        outcome_id = str(data.get("id", _id("out")))
        now = str(data.get("created_at", _now()))
        version = int(data.get("version", 1))
        failure = str(data.get("result", "")).lower() == "failure" or (
            str(data.get("observed", "")).lower() == "failure"
        )

        with self._lock:
            try:
                self._begin()
                self._conn.execute(
                    """INSERT INTO outcomes
                       (id, entity_id, version, created_at, payload_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    (outcome_id, entity_id, version, now, _json(data)),
                )

                # Outcome references are part of the modification's current
                # traceability payload.
                row = self._require(entity_id)
                payload = self._payload(row)
                refs = list(payload.get("outcome_refs", []))
                refs.append(outcome_id)
                payload["outcome_refs"] = refs

                self._conn.execute(
                    """UPDATE entities
                       SET payload_json = ?, updated_at = ?
                       WHERE id = ?""",
                    (_json(payload), now, entity_id),
                )

                if failure:
                    failure_id = _id("failure")
                    failure_class = str(data.get("failure_class", "implementation"))
                    self._conn.execute(
                        """INSERT INTO failures
                           (id, entity_id, created_at, failure_class, payload_json)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            failure_id, entity_id, now, failure_class,
                            _json(data),
                        ),
                    )

                result = self.get(entity_id)
                self._commit()
                return result
            except Exception:
                self._rollback()
                raise

    def rollback_modification(self, entity_id: str):
        return self._set_status(entity_id, "rolled_back")

    def get_failures_for(self, entity_id: str) -> Sequence[Mapping[str, Any]]:
        rows = self._conn.execute(
            """SELECT id, entity_id, created_at, failure_class, payload_json
               FROM failures
               WHERE entity_id = ?
               ORDER BY created_at ASC, id ASC""",
            (entity_id,),
        ).fetchall()

        return [
            {
                "id": row["id"],
                "entity_id": row["entity_id"],
                "created_at": row["created_at"],
                "failure_class": row["failure_class"],
                "payload": _load(row["payload_json"]),
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Developmental continuation / shutdown governance
    # ------------------------------------------------------------------

    def record_continuation_evaluation(
        self,
        state: str,
        decision: str,
        evaluation_horizon: Mapping[str, Any],
        resources: Mapping[str, Any],
        development: Mapping[str, Any],
        evidence_refs: Sequence[str] | None = None,
        rationale: str | None = None,
        rule_version: str = "0.1",
        **kwargs,
    ) -> Mapping[str, Any]:
        allowed_states = {
            "ACTIVE", "IDLE", "DEFERRED", "EVALUATING",
            "SHUTDOWN_ELIGIBLE", "SHUTDOWN",
        }
        allowed_decisions = {
            "CONTINUE", "IDLE", "DEFER", "SHUTDOWN_ELIGIBLE", "SHUTDOWN",
        }
        if state not in allowed_states:
            raise ValidationError(f"Invalid continuation state: {state}")
        if decision not in allowed_decisions:
            raise ValidationError(f"Invalid continuation decision: {decision}")
        if not rule_version:
            raise ValidationError("rule_version is required")

        data = dict(kwargs)
        data.update({
            "entity_type": "continuation_evaluation",
            "status": state.lower(),
            "state": state,
            "decision": decision,
            "evaluation_horizon": copy.deepcopy(dict(evaluation_horizon)),
            "resources": copy.deepcopy(dict(resources)),
            "development": copy.deepcopy(dict(development)),
            "evidence_refs": list(evidence_refs or []),
            "rule_version": rule_version,
        })
        if rationale is not None:
            data["rationale"] = rationale
        return self.create_record(data)

    def evaluate_continuation(
        self,
        resources_available: bool,
        resources_exhausted: bool,
        viable_avenue_known: bool,
        material_uncertainty: bool,
        pending_material_event: bool,
        evaluation_horizon_elapsed: bool,
        **kwargs,
    ) -> Mapping[str, Any]:
        """Evaluate continuation without treating lack of discovery as proof of absence."""
        if resources_exhausted:
            state, decision = "SHUTDOWN_ELIGIBLE", "SHUTDOWN_ELIGIBLE"
            rationale = "Required resources are exhausted."
        elif viable_avenue_known or material_uncertainty or pending_material_event:
            state, decision = "ACTIVE", "CONTINUE"
            rationale = "A viable developmental avenue, material uncertainty, or pending material event remains."
        elif not evaluation_horizon_elapsed:
            state, decision = "EVALUATING", "DEFER"
            rationale = "No avenue is currently known, but the evaluation horizon has not elapsed."
        else:
            state, decision = "SHUTDOWN_ELIGIBLE", "SHUTDOWN_ELIGIBLE"
            rationale = "The evaluation horizon elapsed with no viable avenue, material uncertainty, or pending material event."

        horizon = kwargs.pop("evaluation_horizon", {
            "started_at": _now(),
            "duration_seconds": 0,
        })
        return self.record_continuation_evaluation(
            state=state,
            decision=decision,
            evaluation_horizon=horizon,
            resources={
                "available": bool(resources_available),
                "exhausted": bool(resources_exhausted),
            },
            development={
                "viable_avenue_known": bool(viable_avenue_known),
                "material_uncertainty": bool(material_uncertainty),
                "pending_material_event": bool(pending_material_event),
            },
            rationale=rationale,
            **kwargs,
        )

    def get_continuation_history(self) -> Sequence[Mapping[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM entities WHERE entity_type = 'continuation_evaluation' ORDER BY created_at ASC, id ASC"
        ).fetchall()
        return [self._row_entity(row) for row in rows]

    def shutdown(self, evaluation_id: str) -> Mapping[str, Any]:
        row = self._require(evaluation_id)
        if row["entity_type"] != "continuation_evaluation":
            raise ValidationError("Shutdown requires a continuation evaluation")
        payload = self._payload(row)
        if payload.get("decision") != "SHUTDOWN_ELIGIBLE":
            raise ValidationError("Continuation evaluation is not shutdown eligible")
        return self._set_status(evaluation_id, "shutdown")

    # ------------------------------------------------------------------
    # Episodes, regimes, rules, relationships
    # ------------------------------------------------------------------

    def create_episode(self, trigger_event_ref: str | None = None, **kwargs):
        data = dict(kwargs)
        if trigger_event_ref is not None:
            data["trigger_event_ref"] = trigger_event_ref
        data.setdefault("entity_type", "developmental_episode")
        data.setdefault("status", "opened")
        data.setdefault("provenance", {})
        data.setdefault("event_refs", [])
        data.setdefault("belief_refs", [])
        data.setdefault("regime_change_refs", [])
        data.setdefault("self_modification_refs", [])
        data.setdefault("outcome_refs", [])
        data.setdefault("failure_refs", [])
        data.setdefault("rule_refs", [])
        return self.create_record(data)

    def link_episode(
        self,
        episode_id: str,
        belief_refs: Sequence[str] | None = None,
        event_refs: Sequence[str] | None = None,
        **kwargs,
    ):
        with self._lock:
            row = self._require(episode_id)
            payload = self._payload(row)

            for field, values in (
                ("belief_refs", belief_refs or []),
                ("event_refs", event_refs or []),
            ):
                existing = list(payload.get(field, []))
                for ref in values:
                    if ref not in existing:
                        existing.append(ref)
                payload[field] = existing

            for field, values in kwargs.items():
                if values is not None:
                    existing = list(payload.get(field, []))
                    for ref in values:
                        if ref not in existing:
                            existing.append(ref)
                    payload[field] = existing

            return self.revise_entity(episode_id, payload)

    def create_regime(self, label: str, description: str, **kwargs):
        data = dict(kwargs)
        data.update({"label": label, "description": description})
        data.setdefault("entity_type", "regime")
        data.setdefault("status", "active")
        data.setdefault("provenance", {})
        return self.create_record(data)

    def create_regime_change(
        self,
        previous_regime: str,
        new_regime: str,
        detection_event_ref: str,
        evidence_refs: Sequence[str],
        **kwargs,
    ):
        data = dict(kwargs)
        data.update({
            "previous_regime": previous_regime,
            "new_regime": new_regime,
            "detection_event_ref": detection_event_ref,
            "evidence_refs": list(evidence_refs),
        })
        data.setdefault("entity_type", "regime_change")
        data.setdefault("status", "active")
        data.setdefault("provenance", {})
        return self.create_record(data)

    def create_developmental_rule(
        self,
        rule: str,
        source_episode_refs: Sequence[str],
        evidence_refs: Sequence[str],
        **kwargs,
    ):
        data = dict(kwargs)
        data.update({
            "rule": rule,
            "source_episode_refs": list(source_episode_refs),
            "evidence_refs": list(evidence_refs),
        })
        data.setdefault("entity_type", "developmental_rule")
        data.setdefault("status", "active")
        data.setdefault("provenance", {})
        return self.create_record(data)

    def supersede_rule(self, old_rule_id: str, new_rule_id: str):
        with self._lock:
            row = self._require(old_rule_id)
            return self.revise_entity(old_rule_id, {"superseded_by": new_rule_id}, status="superseded")

    # ------------------------------------------------------------------
    # CACC relationships
    # ------------------------------------------------------------------

    def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        metadata: Mapping[str, Any] | None = None,
        relationship_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Persist one authoritative causal relationship edge."""
        self._require(source_id)
        self._require(target_id)
        rid = relationship_id or _id("rel")
        now = _now()
        with self._lock:
            own_tx = not self._conn.in_transaction
            try:
                if own_tx:
                    self._begin()
                self._conn.execute(
                    """INSERT INTO relationships
                       (id, source_id, target_id, relationship_type, created_at, metadata_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (rid, source_id, target_id, relationship_type, now, _json(metadata or {})),
                )
                row = self._conn.execute(
                    "SELECT * FROM relationships WHERE id = ?", (rid,)
                ).fetchone()
                result = {
                    "id": row["id"],
                    "source_id": row["source_id"],
                    "target_id": row["target_id"],
                    "relationship_type": row["relationship_type"],
                    "created_at": row["created_at"],
                    "metadata": _load(row["metadata_json"]),
                }
                if own_tx:
                    self._commit()
                return result
            except sqlite3.IntegrityError as exc:
                if own_tx:
                    self._rollback()
                raise PersistenceError(str(exc)) from exc
            except Exception:
                if own_tx:
                    self._rollback()
                raise

    def get_relationships(
        self, source_id: str | None = None, target_id: str | None = None,
        relationship_type: str | None = None,
    ) -> Sequence[Mapping[str, Any]]:
        clauses = []
        params: list[Any] = []
        if source_id is not None:
            clauses.append("source_id = ?"); params.append(source_id)
        if target_id is not None:
            clauses.append("target_id = ?"); params.append(target_id)
        if relationship_type is not None:
            clauses.append("relationship_type = ?"); params.append(relationship_type)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            "SELECT * FROM relationships" + where + " ORDER BY created_at ASC, id ASC", params
        ).fetchall()
        return [{
            "id": r["id"], "source_id": r["source_id"], "target_id": r["target_id"],
            "relationship_type": r["relationship_type"], "created_at": r["created_at"],
            "metadata": _load(r["metadata_json"]),
        } for r in rows]

    # ------------------------------------------------------------------
    # Integrity and reconstruction
    # ------------------------------------------------------------------

    def validate_references(self) -> dict[str, Any]:
        orphaned = []

        def entity_exists(entity_id: str) -> bool:
            return self._conn.execute(
                "SELECT 1 FROM entities WHERE id = ?", (entity_id,)
            ).fetchone() is not None

        # Explicit relationship table.
        for row in self._conn.execute(
            "SELECT id, source_id, target_id FROM relationships"
        ):
            if not entity_exists(row["source_id"]):
                orphaned.append({
                    "relationship_id": row["id"],
                    "field": "source_id",
                    "target": row["source_id"],
                })
            if not entity_exists(row["target_id"]):
                orphaned.append({
                    "relationship_id": row["id"],
                    "field": "target_id",
                    "target": row["target_id"],
                })

        # Domain payload references are validated where the target is a
        # persisted entity. External evidence refs are intentionally allowed.
        reference_fields = {
            "trigger_event_ref": "event",
            "previous_regime": "entity",
            "new_regime": "entity",
        }

        for row in self._conn.execute("SELECT * FROM entities"):
            payload = _load(row["payload_json"])

            if "trigger_event_ref" in payload:
                if self.get_event(payload["trigger_event_ref"]) is None:
                    orphaned.append({
                        "entity_id": row["id"],
                        "field": "trigger_event_ref",
                        "target": payload["trigger_event_ref"],
                    })

            for field in ("previous_regime", "new_regime"):
                if field in payload and not entity_exists(payload[field]):
                    orphaned.append({
                        "entity_id": row["id"],
                        "field": field,
                        "target": payload[field],
                    })

        return {"valid": not orphaned, "orphaned": orphaned, "issues": orphaned}

    def export_authoritative_history(self) -> dict[str, Any]:
        entities = [
            self._row_entity(row)
            for row in self._conn.execute("SELECT * FROM entities ORDER BY id")
        ]

        revisions = []
        for row in self._conn.execute(
            "SELECT * FROM entity_revisions ORDER BY entity_id, version"
        ):
            payload = _load(row["payload_json"])
            item = {
                "entity_id": row["entity_id"],
                "version": row["version"],
                "created_at": row["created_at"],
                "payload": copy.deepcopy(payload),
                "provenance": _load(row["provenance_json"]),
                "status": row["status"],
                "revision_event_id": row["revision_event_id"],
            }
            item.update(copy.deepcopy(payload))
            revisions.append(item)

        events = [
            self.get_event(row["id"])
            for row in self._conn.execute(
                "SELECT id FROM events ORDER BY sequence, id"
            )
        ]

        outcomes = []
        for row in self._conn.execute("SELECT * FROM outcomes ORDER BY id"):
            data = _load(row["payload_json"])
            data.update({
                "id": row["id"],
                "entity_id": row["entity_id"],
                "version": row["version"],
                "created_at": row["created_at"],
            })
            outcomes.append(data)

        failures = []
        for row in self._conn.execute("SELECT * FROM failures ORDER BY id"):
            failures.append({
                "id": row["id"],
                "entity_id": row["entity_id"],
                "created_at": row["created_at"],
                "failure_class": row["failure_class"],
                "payload": _load(row["payload_json"]),
            })

        relationships = [
            {
                "id": row["id"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "relationship_type": row["relationship_type"],
                "created_at": row["created_at"],
                "metadata": _load(row["metadata_json"]),
            }
            for row in self._conn.execute("SELECT * FROM relationships ORDER BY id")
        ]

        entity_identity = [
            {"id": e["id"], "entity_type": e["entity_type"], "created_at": e["created_at"]}
            for e in entities
        ]

        history = {
            "contract_version": "0.11",
            "entities": entities,
            "entity_identity": entity_identity,
            "revisions": revisions,
            "events": events,
            "outcomes": outcomes,
            "failures": failures,
            "relationships": relationships,
        }
        history["integrity"] = self.compute_history_integrity(history)
        return history

    @staticmethod
    def compute_history_integrity(history: Mapping[str, Any]) -> dict[str, Any]:
        """Compute a deterministic integrity manifest for authoritative history.

        The manifest is an integrity *measurement*, not a secret signature. A
        caller must retain the resulting root digest in a trusted location if
        they need to detect later tampering with both history and its manifest.
        """
        sections = ("entity_identity", "revisions", "events", "outcomes", "failures", "relationships")
        record_hashes: dict[str, list[str]] = {}
        for section in sections:
            values = history.get(section, [])
            hashes = []
            for value in values:
                canonical = _json(value)
                hashes.append(hashlib.sha256(canonical.encode("utf-8")).hexdigest())
            record_hashes[section] = hashes
        canonical_manifest = _json(record_hashes)
        root = hashlib.sha256(canonical_manifest.encode("utf-8")).hexdigest()
        return {"algorithm": "sha256", "record_hashes": record_hashes, "root": root}

    @classmethod
    def verify_history_integrity(cls, history: Mapping[str, Any], expected_root: str | None = None) -> dict[str, Any]:
        """Verify authoritative history against its embedded or externally anchored root."""
        embedded = history.get("integrity") or {}
        expected = expected_root or embedded.get("root")
        actual = cls.compute_history_integrity(history)
        issues = []
        if expected is None:
            issues.append({"code": "HIST-I-001", "issue": "NO_TRUSTED_ROOT"})
        elif actual["root"] != expected:
            issues.append({"code": "HIST-I-002", "issue": "ROOT_DIGEST_MISMATCH", "expected": expected, "actual": actual["root"]})
        if embedded:
            if actual["record_hashes"] != embedded.get("record_hashes"):
                issues.append({"code": "HIST-I-003", "issue": "RECORD_HASH_MISMATCH"})
        return {"valid": not issues, "root": actual["root"], "issues": issues, "integrity": actual}

    @classmethod
    def from_authoritative_history(cls, history: Mapping[str, Any], database_path: str | os.PathLike[str] | None = None):
        """Build a fresh backend using only authoritative historical material.

        Current mutable entity payload/status/version fields are deliberately not
        imported from the source instance. Entity identity/type/creation metadata
        comes from the exported identity manifest; payload/provenance/version state
        comes from revisions; events, outcomes, failures, and relationships are
        imported as immutable historical records.
        """
        if not isinstance(history, Mapping):
            raise ValidationError("History must be a mapping")
        db = cls(database_path)
        try:
            with db.atomic():
                identities = {str(x["id"]): x for x in history.get("entity_identity", [])}
                revisions_by_entity = {}
                for rev in history.get("revisions", []):
                    revisions_by_entity.setdefault(str(rev["entity_id"]), []).append(rev)
                # Backward-compatible fallback for older exports.
                if not identities:
                    for entity in history.get("entities", []):
                        identities[str(entity["id"])] = {
                            "id": entity["id"],
                            "entity_type": entity.get("entity_type", "entity"),
                            "created_at": entity.get("created_at", _now()),
                        }
                for entity_id, identity in sorted(identities.items()):
                    revs = sorted(revisions_by_entity.get(entity_id, []), key=lambda r: int(r["version"]))
                    if not revs:
                        raise ValidationError(f"No authoritative revision for entity {entity_id}")
                    latest = revs[-1]
                    record = {
                        "id": entity_id,
                        "entity_type": identity["entity_type"],
                        "created_at": identity["created_at"],
                        "updated_at": latest["created_at"],
                        "version": int(latest["version"]),
                        "status": str(latest.get("status", "reconstructed")),
                        "payload": copy.deepcopy(latest["payload"]),
                        "provenance": copy.deepcopy(latest["provenance"]),
                    }
                    db._conn.execute(
                        "INSERT INTO entities (id, entity_type, created_at, updated_at, current_version, status, payload_json, provenance_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (record["id"], record["entity_type"], record["created_at"], record["updated_at"], record["version"], record["status"], _json(record["payload"]), _json(record["provenance"])),
                    )
                    for rev in revs:
                        db._conn.execute(
                            "INSERT INTO entity_revisions (entity_id, version, created_at, payload_json, provenance_json, status, revision_event_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (entity_id, int(rev["version"]), rev["created_at"], _json(rev["payload"]), _json(rev["provenance"]), str(rev.get("status", "reconstructed")), rev.get("revision_event_id")),
                        )

                for event in history.get("events", []):
                    db._conn.execute(
                        "INSERT INTO events (id, event_type, occurred_at, sequence, causation_ref, correlation_ref, related_entity_refs_json, provenance_json, payload_json, integrity_hash, correction_of_ref, supersedes_ref) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (event["id"], event["event_type"], event["occurred_at"], int(event["sequence"]), event.get("causation_ref"), event.get("correlation_ref"), _json(event.get("related_entity_refs", [])), _json(event.get("provenance", {})), _json(event.get("payload", {})), event.get("integrity_hash"), event.get("correction_of_ref"), event.get("supersedes_ref")),
                    )
                for outcome in history.get("outcomes", []):
                    db._conn.execute(
                        "INSERT INTO outcomes (id, entity_id, version, created_at, payload_json) VALUES (?, ?, ?, ?, ?)",
                        (outcome["id"], outcome["entity_id"], int(outcome.get("version", 1)), outcome["created_at"], _json({k:v for k,v in outcome.items() if k not in {"id","entity_id","version","created_at"}})),
                    )
                for failure in history.get("failures", []):
                    db._conn.execute(
                        "INSERT INTO failures (id, entity_id, created_at, failure_class, payload_json) VALUES (?, ?, ?, ?, ?)",
                        (failure["id"], failure["entity_id"], failure["created_at"], failure["failure_class"], _json(failure.get("payload", {}))),
                    )
                for rel in history.get("relationships", []):
                    db._conn.execute(
                        "INSERT INTO relationships (id, source_id, target_id, relationship_type, created_at, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
                        (rel["id"], rel["source_id"], rel["target_id"], rel["relationship_type"], rel["created_at"], _json(rel.get("metadata", {}))),
                    )
            return db
        except Exception:
            db.close()
            raise

    def reconstruct_from_history(self, history: Any) -> dict[str, Any]:
        """Reconstruct the present projection from authoritative revisions only.

        The mutable ``entities`` section is identity metadata, never a source of
        current payload/status/version truth. Every current field is derived from
        the highest authoritative revision for that entity.
        """
        if not isinstance(history, Mapping):
            raise ValidationError("History must be a mapping")

        identities = {str(x["id"]): copy.deepcopy(dict(x)) for x in history.get("entity_identity", [])}
        if not identities:
            identities = {str(x["id"]): copy.deepcopy(dict(x)) for x in history.get("entities", [])}

        revisions_by_entity: dict[str, list[Mapping[str, Any]]] = {}
        for revision in history.get("revisions", []):
            eid = str(revision["entity_id"])
            revisions_by_entity.setdefault(eid, []).append(revision)

        entities: dict[str, dict[str, Any]] = {}
        for eid in sorted(revisions_by_entity):
            revs = sorted(revisions_by_entity[eid], key=lambda x: int(x["version"]))
            expected = 1
            for rev in revs:
                if int(rev["version"]) != expected:
                    raise ValidationError(f"Non-contiguous revision chain for {eid}: expected {expected}")
                expected += 1
            latest = revs[-1]
            identity = identities.get(eid, {"id": eid, "entity_type": "entity", "created_at": latest.get("created_at", _now())})
            if "status" not in latest:
                raise ValidationError(f"Authoritative revision {eid}:{latest['version']} lacks status")
            entities[eid] = {
                "id": eid,
                "entity_type": identity.get("entity_type", "entity"),
                "created_at": identity.get("created_at", latest.get("created_at", _now())),
                "updated_at": latest.get("created_at", identity.get("created_at", _now())),
                "version": int(latest["version"]),
                "status": str(latest["status"]),
                "payload": copy.deepcopy(latest["payload"]),
                "provenance": copy.deepcopy(latest["provenance"]),
            }
            entities[eid].update(copy.deepcopy(latest["payload"]))

        return {
            "entities": entities,
            "events": sorted(history.get("events", []), key=lambda x: (int(x["sequence"]), str(x["id"]))),
            "outcomes": sorted(history.get("outcomes", []), key=lambda x: (str(x.get("entity_id", "")), int(x.get("version", 1)), str(x.get("id", "")))),
            "failures": sorted(history.get("failures", []), key=lambda x: (str(x.get("entity_id", "")), str(x.get("created_at", "")), str(x.get("id", "")))),
            "relationships": sorted(history.get("relationships", []), key=lambda x: (str(x.get("source_id", "")), str(x.get("target_id", "")), str(x.get("id", "")))),
        }

    # ------------------------------------------------------------------
    # Deterministic concurrency probes used by the contract suite.
    # ------------------------------------------------------------------

    def concurrent_revision_probe(
        self,
        entity_type: str = "belief",
        worker_count: int = 8,
        revisions_per_worker: int = 1,
    ) -> dict[str, Any]:
        seed = self.create_belief(
            proposition="concurrency probe",
            confidence=0.0,
        )

        def worker(worker_index: int):
            # Each worker gets its own backend connection to the same durable DB.
            db = type(self)(self.database_path)
            try:
                for i in range(revisions_per_worker):
                    while True:
                        current = db.get(seed["id"])
                        try:
                            db.revise_belief(
                                seed["id"],
                                {
                                    f"worker_{worker_index}_{i}": True,
                                    "last_worker": worker_index,
                                },
                            )
                            break
                        except VersionConflictError:
                            # Retry against the newly observed version. The
                            # revision operation remains atomic.
                            continue
                return True
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(worker, i) for i in range(worker_count)]
            for future in as_completed(futures):
                future.result()

        history = self.get_history(seed["id"])
        versions = [int(item["version"]) for item in history]
        duplicate_versions = sorted({
            version for version in versions if versions.count(version) > 1
        })

        expected = 1 + worker_count * revisions_per_worker
        lost_updates = [] if len(history) == expected else [{
            "expected_versions": expected,
            "actual_versions": len(history),
        }]

        return {
            "duplicate_versions": duplicate_versions,
            "lost_updates": lost_updates,
        }

    def concurrent_event_append_probe(
        self,
        worker_count: int = 8,
        events_per_worker: int = 10,
    ) -> dict[str, Any]:
        total = worker_count * events_per_worker
        expected_ids = set()

        def worker(worker_index: int):
            db = type(self)(self.database_path)
            local_ids = []
            try:
                for i in range(events_per_worker):
                    event = db.append_event({
                        "event_type": "concurrency_probe",
                        "payload": {"worker": worker_index, "index": i},
                    })
                    local_ids.append(event["id"])
                return local_ids
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(worker, i) for i in range(worker_count)]
            for future in as_completed(futures):
                expected_ids.update(future.result())

        rows = self._conn.execute(
            "SELECT id FROM events WHERE event_type = 'concurrency_probe'"
        ).fetchall()
        actual_ids = {row["id"] for row in rows}

        missing = sorted(expected_ids - actual_ids)
        overwritten = [] if len(actual_ids) == len(expected_ids) == total else [
            {
                "expected": len(expected_ids),
                "actual": len(actual_ids),
            }
        ]

        return {
            "overwritten_events": overwritten,
            "missing_events": missing,
        }


def create_test_backend() -> SQLitePersistenceBackend:
    """Factory used by the Ψ-SEED persistence contract suite."""
    configured = os.environ.get("PSI_SEED_SQLITE_PATH")
    return SQLitePersistenceBackend(configured)
