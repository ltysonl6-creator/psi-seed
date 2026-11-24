# Ψ-SEED Persistence Backend Implementation Contract

**Path:** `runtime/persistence/backend_implementation_contract.md`  
**Status:** Canonical Implementation Contract  
**Version:** 0.1

## 1. Purpose

This contract defines the concrete behavioral requirements for a Ψ-SEED persistence backend.

The backend makes the persistence contract executable against durable storage.

Core rule:

> **Current state may change. Historical evidence may not be silently rewritten.**

The initial implementation may use SQLite. The behavioral contract remains storage-engine independent.

## 2. Architectural Boundary

```text
Ψ-SEED runtime
      |
      v
Persistence service / adapter
      |
      v
Persistence backend contract
      |
      v
SQLite adapter
      |
      v
Durable database
```

The backend owns identity, versioning, historical preservation, event immutability, reference integrity, transactions, concurrency control, and reconstruction.

It does not own Pathfinder scoring, Curiosity Governance decisions, belief interpretation, or self-modification approval.

## 3. Required Factory

The integration boundary is:

```python
from psi_seed.persistence.testing import create_test_backend

backend = create_test_backend()
```

The configured test factory must return a real persistence backend, not a mock or fake.

Example:

```text
PSI_SEED_TEST_BACKEND=package.module:create_test_backend
```

## 4. Required Backend Surface

```python
close() -> None
reload() -> PersistenceTestBackend

get(entity_id: str) -> Mapping[str, Any] | None
create_record(record: Mapping[str, Any]) -> Mapping[str, Any]

create_belief(record: Mapping[str, Any]) -> Mapping[str, Any]
update_belief(entity_id: str, changes: Mapping[str, Any]) -> Mapping[str, Any]
revise_belief(entity_id: str, changes: Mapping[str, Any]) -> Mapping[str, Any]
get_history(entity_id: str) -> Sequence[Mapping[str, Any]]

append_event(event: Mapping[str, Any]) -> Mapping[str, Any]
get_event(event_id: str) -> Mapping[str, Any] | None
attempt_event_update(event_id: str, changes: Mapping[str, Any]) -> Any

create_self_modification(record: Mapping[str, Any]) -> Mapping[str, Any]
record_outcome(entity_id: str, outcome: Mapping[str, Any]) -> Mapping[str, Any]
set_modification_status(entity_id: str, status: str) -> Mapping[str, Any]
execute_modification(entity_id: str) -> Mapping[str, Any]
rollback_modification(entity_id: str) -> Mapping[str, Any]
get_failures_for(entity_id: str) -> Sequence[Mapping[str, Any]]

validate_references() -> Any
export_authoritative_history() -> Any
reconstruct_from_history(history: Any) -> Any
```

## 5. Identity

### P-001 — Stable Identity

Once assigned, an entity identity never changes.

### P-002 — Unique Identity

Distinct persistent entities must never share an identity. Identity assignment must be atomic with persistence.

## 6. Versioning

The backend must distinguish current state from historical revisions.

```text
v1 -> v2 -> v3 -> v4
```

All authoritative revisions remain retrievable.

### P-003 — Monotonic Version

For one logical entity:

```text
v(n+1) > v(n)
```

Versions must never silently move backward or be reused.

### P-006 — Explicit Revision

A historical change must create an explicit revision. Updating current state must not destroy the previous authoritative state.

## 7. Historical Preservation

### P-004 — Historical Preservation

Later revisions must not make earlier authoritative revisions disappear.

### P-005 — Event Immutability

Events are append-only. Authoritative event fields cannot be silently mutated.

Corrections are represented by new events.

`attempt_event_update()` must reject mutation or otherwise guarantee that the original event remains exactly unchanged.

## 8. Provenance

### P-007 — Provenance Preservation

Persistent developmental records must retain enough provenance to establish what created them, when, from which operation/event, and what evidence supports them.

Updating current state may add provenance but may not silently discard historical provenance.

## 9. Failure Persistence

Failures are first-class historical information.

### P-008 — Failure Retention

A failure remains retrievable even after recovery or later state changes.

Failure records should distinguish at least:

```text
expected
unexpected
partial
inconclusive
environmental
regime-dependent
implementation
```

## 10. Self-Modification

The backend must preserve the complete lifecycle:

```text
proposed
evaluated
approved
rejected
executed
successful
failed
inconclusive
retained
rolled_back
quarantined
```

Rollback changes current operational state but never erases proposal, approval, execution, outcome, failure, evidence, or rollback history.

### P-009 — Modification Traceability

An executed modification remains traceable to its target, proposal, rationale, approval, execution, outcome, failure, and rollback where applicable.

### P-010 — Rollback Preservation

Rollback preserves the historical fact that the modification was executed.

## 11. Regime Changes

A regime change preserves:

```text
previous_regime
new_regime
detection_event
evidence
affected_entities
```

### P-011 — Regime Traceability

Historical records remain linkable to the regime under which they occurred.

Later reinterpretation may add interpretation records but may not rewrite original evidence.

## 12. Developmental Episodes

Episodes may reference:

```text
events
beliefs
regime changes
self-modifications
outcomes
failures
rules
parent episode
child episodes
```

### P-012 — Episode Traceability

Required episode references must resolve to authoritative records. Historical links survive later state transitions.

## 13. Developmental Rules

A rule preserves:

```text
rule
source episodes
supporting evidence
scope
exceptions
contradictions
validation counts
confidence
regime context
```

### P-013 — Rule Traceability

Rules remain traceable to originating episodes and evidence.

Superseded rules remain historically retrievable.

## 14. Referential Integrity

### P-014 — No Orphaned Critical References

A transaction must not commit a critical reference to a record that does not exist.

If corruption already exists, `validate_references()` must identify it.

## 15. Deterministic Reconstruction

### P-015 — Deterministic Reconstruction

Given identical authoritative history, reconstruction must produce identical authoritative state.

Reconstruction cannot depend on:

- object identity
- cache state
- process-local memory
- random ordering
- nondeterministic timestamps

Where order matters, an explicit stable ordering key must be used.

## 16. Transactions

Operations creating or modifying multiple logically dependent records must be atomic.

Valid outcomes are:

```text
COMMITTED:
    all required writes are durable

ROLLED_BACK:
    none of the writes are visible as committed history
```

Examples requiring atomicity include revision plus provenance, self-modification plus execution event, failure outcome plus failure reference, and rule plus source-episode references.

## 17. Concurrency

The backend must prevent:

- duplicate version numbers;
- lost revisions;
- event overwrite;
- broken concurrent references;
- conflicting authoritative current-state claims.

The implementation may use transactions, uniqueness constraints, compare-and-swap/version checks, explicit locks, or serialized writes.

The mechanism must be documented and tested.

## 18. SQLite Requirements

The initial SQLite adapter should explicitly configure:

```text
foreign_keys = ON
appropriate journal mode
busy timeout
explicit transactions
```

The implementation must not depend on SQLite defaults where an invariant requires a specific behavior.

Database constraints should enforce directly enforceable invariants; application validation handles semantic invariants.

## 19. Recommended Persistence Model

The implementation should separate:

```text
current state
historical revision
immutable event
relationship/reference
outcome
failure
```

A recommended physical model is:

```text
entities
entity_revisions
events
outcomes
relationships
failures
```

with specialized tables or typed payloads for:

```text
beliefs
regime_changes
self_modifications
developmental_episodes
developmental_rules
```

The physical schema may differ if behavioral guarantees remain satisfied.

## 20. Deletion

Destructive deletion of authoritative developmental history is prohibited through ordinary runtime mutation APIs.

Prefer:

```text
retired
superseded
invalidated
quarantined
```

Any physical purge requires a separately governed mechanism.

## 21. Recovery

After interruption, the backend must be able to distinguish:

```text
NOT_COMMITTED
COMMITTED
RECOVERY_REQUIRED
```

It must never fabricate history to make state appear coherent.

## 22. Cache

Caching is permitted but never authoritative.

After:

```python
backend.reload()
```

the backend must observe durable state rather than stale process-local state.

## 23. Serialization

Persistent representations must be deterministic.

Structured payloads require stable field meanings, stable identifiers, defined timestamp representation, and explicit ordering where order is semantically meaningful.

Canonical serialization should be used for integrity hashes.

## 24. Error Contract

At minimum, distinguish:

```text
ValidationError
IdentityConflictError
VersionConflictError
ImmutableEventError
ReferenceIntegrityError
TransactionError
ConcurrencyError
PersistenceError
RecoveryRequiredError
```

Failed operations must not be reported as successful.

## 25. Failure Recording

The system must distinguish:

```text
operation failed
```

from:

```text
failure record was never persisted
```

Where a failure itself is developmental history, it must survive rollback of the operation through a defined compensating or separate durable transaction.

The mechanism must be documented.

## 26. Test Requirements

Conformance requires the durable backend to pass the P-001 through P-015 contract tests, including:

- revision preservation;
- immutable events;
- failure retention;
- rollback preservation;
- provenance;
- regime traceability;
- episode traceability;
- rule provenance;
- reference validation;
- deterministic reconstruction;
- concurrent revision safety;
- concurrent event append safety;
- durable reload behavior.

## 27. Test Database Isolation

The test factory must create isolated durable state.

Each ordinary test instance must have fresh logical state.

Concurrency tests may explicitly share a database instance.

The test factory may accept a database path or obtain one through test-runner configuration.

## 28. Implementation Order

Build the first SQLite implementation in this order:

```text
1. database initialization
2. schema and constraints
3. connection and transaction layer
4. identity generation
5. event persistence
6. entity and revision persistence
7. provenance and relationship persistence
8. outcomes and failures
9. self-modification lifecycle
10. regime changes
11. developmental episodes
12. developmental rules
13. reconstruction
14. concurrency controls
15. contract-test integration
```

Do not build Pathfinder or Curiosity Governance into this layer.

## 29. Conformance Rule

The backend is conformant only when behavior—not merely schema, documentation, or API shape—satisfies the persistence contract and P-001 through P-015 under normal, failure, reload, recovery, and concurrent execution.

> **Ψ-SEED may change because of experience, but it must not lose the experience that caused it to change.**
