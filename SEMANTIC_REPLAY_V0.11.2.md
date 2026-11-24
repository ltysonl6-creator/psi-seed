# Ψ-SEED CACC v0.11.2 — Semantic Replay Integrity

## Purpose

v0.11.2 closes the semantic-replay attack surface discovered by the v0.11.1 red team.

The contract is no longer merely:

> fresh reconstruction reproduces the same bytes.

It is:

> a fresh Ψ-SEED independently derives the same meaning from authoritative history, and that meaning satisfies the semantic contracts.

## New semantic boundaries

- **SI-008 — Revision chronology**
  - revision versions must be contiguous;
  - revision timestamps must not move backward within an entity.
- **SI-009 — Revision/event coherence**
  - a referenced revision event must exist;
  - the revision cannot precede its event;
  - the revision event must identify the revised entity when related references are present.
- **SI-010 — Semantic interpretation mismatch**
  - source and fresh authoritative histories must produce identical semantic interpretations, not merely identical current projections.

## Key test

Two histories can converge on the same current state while having different developmental meaning:

```text
History A: A -> B
History B: A -> X -> B
```

Both currently equal `B`. They are **not semantically equivalent** because the second history contains an additional experience.

## Principle

> **Current state is not sufficient to define meaning. History is part of state identity.**

## Replay contract

```text
authoritative history
        |
        v
fresh reconstruction
        |
        v
independent semantic interpretation
        |
        +-- causal coherence
        +-- temporal coherence
        +-- lifecycle coherence
        +-- revision chronology
        +-- revision/event coherence
        +-- developmental eligibility
        |
        v
semantic interpretation digest
        |
        v
source == fresh ?
        |
     YES / NO
```

Replay is still read-mostly. It does not repair, delete, rewrite, or reinterpret historical facts in place.
