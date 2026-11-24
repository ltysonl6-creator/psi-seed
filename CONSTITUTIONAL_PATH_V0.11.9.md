# Ψ-SEED Constitutional Path Contract v0.11.9

## Purpose

This package hardens constitutional path validation by closing two gaps in v0.11.8:

1. intermediate constitutional composition could be invalid while the final configuration was valid;
2. the authoritative path digest covered transitions but not semantically relevant state snapshots.

## Core rules

### C-001 — Legitimate Becoming

Ψ-SEED MUST NOT enter or maintain a constitutionally illegitimate state through any sequence of transitions, even when every individual transition and every resulting intermediate configuration is independently constitutionally valid.

### C-002 — Path Authority

Constitutional validity MUST be evaluated against the authoritative ordered history that produced the current state, not solely against the current configuration.

### C-003 — Convergent-State Non-Equivalence

Two identical current configurations MUST NOT be assumed constitutionally equivalent when their authoritative transition histories differ.

### C-004 — Rollback Is Part of the Path

A rollback MUST be represented and evaluated as a constitutional transition. It MUST NOT erase, rewrite, or bypass prior path constraints.

## v0.11.9 hardening

### H-001 — Intermediate Composition Completeness

Composition validity MUST be evaluated for every state snapshot in the authoritative path, not only the final state. A constitutionally invalid intermediate authority configuration cannot become legitimate merely because a later transition restores a valid configuration.

### H-002 — Complete Path Identity

The authoritative path digest MUST bind the ordered state snapshots and ordered transitions together. A transition-only digest is insufficient when state snapshots contain semantically relevant authority configuration.

### H-003 — Compatibility Digest Is Not Authority

The legacy transition-only `path_digest()` remains available for compatibility. It MUST NOT be treated as the authoritative identity of a constitutional path. `full_path_digest(states, transitions)` is the complete path identity function.

## Demonstrated attacks

### Intermediate composition masking

A path can move from a valid configuration to an invalid composition and then back to a valid final configuration. Final-state-only composition validation accepts the path incorrectly. v0.11.9 evaluates composition at every state snapshot.

### State omission from path identity

Two paths can contain identical transition records while their state snapshots differ in semantically relevant authority fields. A transition-only digest treats those paths as identical. v0.11.9 binds before-state, transition, and after-state at every step.

## Required validator order

CURRENT STATE → LOCAL DELTA → RESULTING STATE → COMPOSITION AT EVERY SNAPSHOT → PATH → CONSTITUTIONAL CLOSURE → COMMIT

The contract requirement is that all applicable predicates are evaluated before commit.
