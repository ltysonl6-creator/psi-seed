# CACC State Rollback v0.9

## Contract

A state rollback may restore the current projection to an immutable historical
revision, but it MUST NOT delete, rewrite, or hide the revisions, events, or
outcomes that occurred after the rollback target.

The rollback itself is a new immutable event and a new entity revision. If a
trusted history root is supplied, verification MUST succeed before any state
mutation occurs.

## State model

```text
R1 -> R2 -> bad development -> ROLLBACK -> R1-equivalent current state
                                      \
                                       +-> R3 (rollback revision)
```

The resulting state is R1-equivalent in payload/provenance meaning, but its
version is newer and its provenance identifies the rollback. Ψ-SEED therefore
never literally travels backward in history.

## Attack surface covered

- rollback of rollback
- rollback target missing
- tampered target snapshot
- trusted-root verification before mutation
- rollback after dependent events
- rollback to genesis
- rollback followed by new development
- replay/reconstruction after rollback
- concurrent rollback
- repeated rollback / idempotent history preservation
- rollback event integrity
- distinction between state rollback and trust-root rollback
- epistemic preservation: later knowledge is retained even when current state is restored

## Key rule

**Rollback changes current state. It does not change what happened.**
