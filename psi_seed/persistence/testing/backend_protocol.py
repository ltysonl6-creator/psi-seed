"""Contract-test interface for Ψ-SEED persistence backends.

This module deliberately contains no fake persistence implementation.
The persistence contract tests must exercise the backend under test.

A production or integration backend is supplied through the
``PSI_SEED_TEST_BACKEND`` environment variable, using an import path
such as ``my_package.persistence:create_test_backend``.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence


class PersistenceBackendError(RuntimeError):
    """Base error for persistence contract-test backend failures."""


class BackendNotConfiguredError(PersistenceBackendError):
    """Raised when the contract tests have no backend configured."""


@dataclass(frozen=True)
class PersistenceTestBackend(Protocol):
    """Behavioral interface required by Ψ-SEED persistence tests.

    The protocol is intentionally expressed in terms of plain mappings
    so the contract suite does not prescribe the production domain
    model, ORM, or storage engine.

    Implementations must preserve the semantics defined by
    ``contracts/persistence_backend_contract.md`` and invariants
    P-001 through P-015.
    """

    # --- lifecycle / generic access ---

    def close(self) -> None:
        """Release backend resources."""

    def reload(self) -> "PersistenceTestBackend":
        """Return a fresh view of the same durable state."""

    def get(self, entity_id: str) -> Mapping[str, Any] | None:
        """Return the authoritative current record for an entity."""

    def create_record(self, record: Mapping[str, Any]) -> Mapping[str, Any]:
        """Create a generic persistent record."""

    # --- beliefs / versioning ---

    def create_belief(self, record: Mapping[str, Any]) -> Mapping[str, Any]:
        """Persist a new belief at its initial version."""

    def update_belief(
        self, entity_id: str, changes: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Update current belief state without rewriting history."""

    def revise_belief(
        self, entity_id: str, changes: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Create an explicit new belief revision."""

    def get_history(self, entity_id: str) -> Sequence[Mapping[str, Any]]:
        """Return authoritative historical revisions in stable order."""

    # --- events ---

    def append_event(self, event: Mapping[str, Any]) -> Mapping[str, Any]:
        """Append an immutable historical event."""

    def get_event(self, event_id: str) -> Mapping[str, Any] | None:
        """Return an immutable event by identity."""

    def attempt_event_update(
        self, event_id: str, changes: Mapping[str, Any]
    ) -> Any:
        """Attempt to mutate an event; must be rejected or otherwise
        preserve the original event exactly."""

    # --- self-modification / outcomes ---

    def create_self_modification(
        self, record: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Persist a self-modification proposal."""

    def record_outcome(
        self, entity_id: str, outcome: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Persist an outcome without deleting prior outcomes."""

    def set_modification_status(
        self, entity_id: str, status: str
    ) -> Mapping[str, Any]:
        """Transition a self-modification to an explicit status."""

    def execute_modification(
        self, entity_id: str
    ) -> Mapping[str, Any]:
        """Record execution while preserving modification history."""

    def rollback_modification(
        self, entity_id: str
    ) -> Mapping[str, Any]:
        """Rollback current effect without erasing execution/failure history."""

    def get_failures_for(
        self, entity_id: str
    ) -> Sequence[Mapping[str, Any]]:
        """Return retained failures associated with an entity."""

    # --- provenance / traceability ---

    def validate_references(self) -> Any:
        """Validate critical references and report any orphaned refs."""

    def export_authoritative_history(self) -> Any:
        """Export the complete authoritative historical record."""

    def reconstruct_from_history(self, history: Any) -> Any:
        """Reconstruct authoritative state from exported history."""


def _load_factory(spec: str) -> Callable[[], PersistenceTestBackend]:
    if ":" in spec:
        module_name, attr_name = spec.split(":", 1)
    else:
        module_name, attr_name = spec, "create_test_backend"

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise BackendNotConfiguredError(
            f"Unable to import configured Ψ-SEED persistence backend "
            f"{module_name!r}: {exc}"
        ) from exc

    try:
        factory = getattr(module, attr_name)
    except AttributeError as exc:
        raise BackendNotConfiguredError(
            f"Configured backend {spec!r} does not expose "
            f"{attr_name!r}."
        ) from exc

    if not callable(factory):
        raise BackendNotConfiguredError(
            f"Configured backend factory {spec!r} is not callable."
        )

    return factory


def create_test_backend() -> PersistenceTestBackend:
    """Create the persistence backend used by Ψ-SEED contract tests.

    Configuration is intentionally external to the contract suite:

        PSI_SEED_TEST_BACKEND=package.module:create_test_backend

    This prevents the tests from silently testing a fake in-memory
    implementation instead of the real persistence boundary.

    If no backend is configured, the tests fail loudly with an
    actionable error.
    """

    spec = os.environ.get("PSI_SEED_TEST_BACKEND", "psi_seed.persistence.sqlite:create_test_backend")
    factory = _load_factory(spec)
    backend = factory()

    required = (
        "close",
        "reload",
        "get",
        "create_record",
        "create_belief",
        "update_belief",
        "revise_belief",
        "get_history",
        "append_event",
        "get_event",
        "attempt_event_update",
        "create_self_modification",
        "record_outcome",
        "set_modification_status",
        "execute_modification",
        "rollback_modification",
        "get_failures_for",
        "validate_references",
        "export_authoritative_history",
        "reconstruct_from_history",
    )
    missing = [name for name in required if not callable(getattr(backend, name, None))]
    if missing:
        raise BackendNotConfiguredError(
            "Configured Ψ-SEED persistence backend is incomplete. "
            f"Missing required methods: {', '.join(missing)}"
        )

    return backend
