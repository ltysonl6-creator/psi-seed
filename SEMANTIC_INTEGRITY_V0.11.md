# Ψ-SEED CACC v0.11 — Semantic Integrity Layer

## Purpose

v0.10 established authoritative state projection and complete rollback semantics.
v0.11 adds the next boundary: **graph-level semantic integrity**.

Local integrity can prove that individual records are structurally valid, versioned,
hashed, and durably connected. Semantic integrity asks whether those valid records
can jointly describe a coherent CACC history.

> **Local validity does not imply global meaning validity.**

## Core rule

**Ψ-SEED may preserve a historical fact without treating that fact as authoritative evidence for the current state.**

A rollback therefore does not erase a previous outcome. It creates a lifecycle boundary:
- the old outcome remains historical fact;
- the rolled-back transition becomes `ROLLED_BACK` in current authoritative state;
- no later authoritative outcome may be attached to that transition;
- historical evidence that depends on that rolled-back outcome remains preserved but is
  semantically ineligible for developmental promotion.

## Semantic issue registry

| Code | Meaning |
|---|---|
| SI-001 | Causal-chain mismatch across a persisted joint |
| SI-002 | Temporal inversion between transition and claimed outcome |
| SI-003 | Outcome occurs after its transition was rolled back |
| SI-004 | Developmental evidence promotes an outcome from a rolled-back transition |
| SI-005 | Lifecycle contradiction, such as rolled-back transition retaining active state |
| SI-006 | Developmental evidence is ineligible for developmental use |
| SI-007 | Reserved for deterministic semantic replay mismatch |

## Validator boundary

The semantic validator is graph-level and read-mostly. It consumes authoritative history
and produces a deterministic report. It does not rewrite historical records to make the
report pass.

## Enforcement points

The CACC service now rejects:
1. outcome chain IDs that differ from the transition chain;
2. outcome timestamps preceding the transition timestamp;
3. new outcomes attached to a rolled-back or invalidated transition;
4. developmental evidence that references an outcome whose transition is rolled back;
5. developmental evidence whose chain differs from the referenced outcome's transition chain.

## Audit API

```python
report = svc.validate_semantic_integrity()
svc.assert_semantic_integrity()
```

The report is deterministic for a fixed authoritative history and contains `valid`,
`issue_count`, `issues`, and the detected rolled-back transition IDs.

## Non-goal

Semantic integrity does **not** retroactively declare an earlier observation false.
An outcome can remain a true historical observation while being ineligible as evidence
for the current developmental state after a rollback.
