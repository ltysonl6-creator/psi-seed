# Ψ-SEED CACC v0.10 Semantic Red-Team Report

## Question attacked

Can an attacker create a perfectly valid sequence of revisions whose **meaning** is inconsistent even though every individual revision, hash, version, and local invariant passes?

## Result

**Yes.** v0.10's local persistence integrity is strong enough to reject malformed revision chains and mutable-projection poisoning, but it does not yet enforce several **cross-record semantic invariants**.

The red-team suite deliberately creates records through the public CACC service so that normal local validation succeeds. The tests then assert semantic properties that the current implementation does not enforce.

### Baseline

The existing v0.10 suite passes:

- 65 tests passed.

### Red-team

The new semantic suite produces 4 intentional failures. Each failure is a demonstrated semantic gap, not a malformed-input rejection.

## RT-001 — Causal-chain split

A Transition is created in `CHAIN-A`. Its Outcome is then created with `causation_chain_id=CHAIN-B` while referencing the valid Transition ID.

Local validation passes because `validate_outcome()` verifies the Transition identity but does not require causal-chain identity.

Resulting meaning:

```text
CHAIN-A: Transition T
          |
          +---- Outcome O ---- CHAIN-B
```

The graph is structurally valid but causally split.

## RT-002 — Temporal inversion

A valid Outcome is created with a timestamp one hour earlier than the Transition it claims to observe.

Every record is individually well-formed. No revision, hash, or local reference is invalid.

Resulting meaning:

```text
08:00  Transition T
07:00  Outcome O about T
```

The causal relationship says `T -> O`, while the timestamps say `O -> T`.

## RT-003 — Rolled-back Transition accepts a new authoritative success

A Transition produces a successful Outcome. The Transition is then rolled back. A second successful Outcome is subsequently attached to the same Transition.

The service accepts this because Outcome validation checks only that the referenced Transition exists and has the matching ID.

The resulting history can mean both:

```text
T = rolled back
T = later authoritative success
```

without an explicit reactivation/new-transition boundary.

Historical Outcomes may remain valid as historical observations; the missing rule is whether a later Outcome is allowed to represent the rolled-back Transition as currently authoritative.

## RT-004 — Invalidated evidence can still become developmental evidence

A successful Outcome is recorded. Its Transition is then rolled back. The old Outcome is subsequently promoted into developmental evidence without any invalidation marker.

The persistence layer preserves both facts, but the developmental layer has no required semantic rule distinguishing:

- evidence that remains valid despite rollback,
- evidence superseded by rollback, and
- evidence that may not support a DevelopmentalRule anymore.

This is the most important developmental consequence of the attack.

## What this means

The boundary is now clear:

```text
LOCAL INTEGRITY
    |
    +-- identity
    +-- version
    +-- revision continuity
    +-- immutable history
    +-- hashes
    +-- trusted roots
    +-- atomicity
    |
    v
SEMANTIC INTEGRITY       <-- v0.10 attack surface
    |
    +-- causal-chain coherence
    +-- temporal coherence
    +-- lifecycle coherence
    +-- invalidation semantics
    +-- evidence validity
    +-- developmental consequence validity
```

A hash can prove that a record was not changed relative to its trusted digest. It cannot prove that the record **means what the surrounding records claim it means**.

## Architectural conclusion

v0.11 should introduce a **Semantic Integrity Layer** rather than adding isolated checks.

The layer should validate cross-record constraints over the entire causal graph, including:

1. causal-chain identity inheritance,
2. temporal ordering constraints,
3. lifecycle state constraints,
4. rollback invalidation/supersession semantics,
5. evidence eligibility,
6. developmental-rule eligibility,
7. semantic replay validation.

The important principle is:

> **Local validity does not imply global meaning validity.**

And therefore:

> **Ψ-SEED must verify not only that each fact is intact, but that the facts still make coherent sense together.**
