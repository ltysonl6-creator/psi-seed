# Ψ-SEED Constitutional Path Contract v0.11.8

## Purpose

This package extends constitutional validation from current-state and individual-transition checks to ordered-path checks.

## Core rule

**C-001 — Legitimate Becoming**

Ψ-SEED MUST NOT enter or maintain a constitutionally illegitimate state through any sequence of transitions, even when every individual transition and every resulting intermediate configuration is independently constitutionally valid.

**C-002 — Path Authority**

Constitutional validity MUST be evaluated against the authoritative ordered history that produced the current state, not solely against the current configuration.

**C-003 — Convergent-State Non-Equivalence**

Two identical current configurations MUST NOT be assumed constitutionally equivalent when their authoritative transition histories differ.

**C-004 — Rollback Is Part of the Path**

A rollback MUST be represented and evaluated as a constitutional transition. It MUST NOT erase, rewrite, or bypass prior path constraints.

## Important boundary

A SHA-256 path digest provides deterministic identity for an ordered path. It does **not** establish authenticity or authority by itself. An independently trusted root is still required to identify the authoritative history.

## Demonstrated attack

G1 ACTIVE → G2 ACTIVE → G3 ACTIVE → G1 ACTIVE.

Every snapshot can satisfy the state rule "exactly one active generation." Every transition can have correct endpoints. The final configuration can therefore look locally valid. The path is nevertheless invalid because G1 was retired before being reactivated.

## Non-local prefix attack

The first two transitions are constitutionally valid. Only the third transition makes the complete path invalid. Therefore prefix-by-prefix validation is insufficient unless the validator evaluates the proposed path extension against the constitutional path rules.

## Composition boundary

Path validity is distinct from compositional validity. A configuration can be invalid because the combination of effective authority properties is forbidden, even if the latest delta looks locally harmless.

## v0.11.9 hardening findings

### H-001 — Intermediate composition must be validated

Composition validity MUST be evaluated for every resulting state in the authoritative path, not only the final state. A constitutionally invalid intermediate authority configuration cannot become legitimate merely because a later transition restores a valid configuration.

### H-002 — Path identity must bind state snapshots

A transition-only digest is insufficient to identify a complete constitutional path when state snapshots contain semantically relevant authority configuration. The authoritative path digest MUST include the ordered state snapshots and transitions together.

### H-003 — Compatibility digest is not authority

The legacy transition-only digest remains available for compatibility, but MUST NOT be used as the authoritative identity of a constitutional path.

## Required validator order

CURRENT STATE → LOCAL DELTA → RESULTING STATE → COMPOSITION → PATH → CONSTITUTIONAL CLOSURE → COMMIT

The ordering is an implementation recommendation; the contract requirement is that all applicable predicates are evaluated before commit.
