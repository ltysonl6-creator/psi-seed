# Ψ-SEED v0.11.5 — Semantic Manifest Authority

## SMA-001 — The semantic manifest is an authority boundary

The Semantic Relevance Manifest decides which persisted history fields are meaning-bearing. Because that decision changes the interpretation of authoritative history, the manifest cannot be trusted merely because it is present in the history it interprets.

### Trust rule

> **A semantic manifest cannot authorize its own integrity.**

A trusted manifest authority owns the active manifest generation. Historical storage may contain a copy for provenance, but that copy is evidence, not authority.

## Generation model

```text
Trusted Semantic Manifest Authority
              |
              v
      Active Manifest Generation
              |
              v
   Semantic Relevance Projection
              |
              v
      Semantic Interpretation
              |
              v
       Semantic Replay
```

Manifest generations are immutable records. Rotation creates a new generation and retires the previous active generation. Rollback changes only the active pointer; it does not delete or rewrite prior generations.

## Attack coverage

- mutate an authoritative field classification
- downgrade to an older/permissive manifest
- replace the manifest while leaving history unchanged
- remove the trusted manifest entirely
- use a retired generation as if it were active
- rotate and roll back without erasing prior manifest generations
- attempt to let embedded history authorize a changed manifest

## Fail-closed rule

If the active trusted manifest is absent, inactive, unknown, or its digest does not match its canonical contents, semantic interpretation is not authoritative.

## Key distinction

The manifest determines **meaning**. The trusted authority determines **which manifest is allowed to determine meaning**.

That gives Ψ-SEED two separate questions:

1. What counts as meaningful? — the manifest contract.
2. Who gets to say? — the trusted semantic manifest authority.
