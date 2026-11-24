# Ψ-SEED Constitutional Contract v1.0

**Status: FROZEN**

This package is the canonical v1.0 constitutional freeze for Ψ-SEED's
constitutional path model.

The constitution has five layers:

```text
STATE → TRANSITION → COMPOSITION → PATH → AUTHORITY
```

The governing principle is:

> Ψ-SEED's constitution governs not only what it may be, but the legitimate
> ways by which it may become what it becomes.

## Canonical files

- `contracts/constitutional_contract.py` — permanent invariant registry.
- `contracts/constitutional_manifest.v1.0.json` — machine-readable freeze manifest.
- `contracts/constitutional_path.py` — deterministic state/transition/composition/path/authority validation.
- `CONSTITUTIONAL_FREEZE_V1.0.md` — normative contract and change rules.
- `tests/cacc/test_constitutional_freeze_v1.py` — freeze regression tests.

Historical red-team and implementation reports remain in this package as
provenance. They are not alternate authorities for the v1.0 contract.

## Authority rule

`validate_history()` checks constitutional coherence of the supplied sequence.
It may be used for live prefixes.

`validate_authoritative_history()` checks whether the supplied sequence can
stand in for complete authoritative history. It requires an explicit
completeness declaration, stable identity, contiguous sequence numbers,
parent-digest lineage, and an external terminal anchor.

For production authority, bind the terminal record to an externally trusted
digest and use the trusted-root / semantic-authority layer to establish which
anchor is authoritative. A path digest by itself is not a trust root.

## v1.0 freeze

C-001 through C-012 are permanent API identifiers. Strengthening an existing
invariant is an implementation change; changing its meaning or adding a new
constitutional category requires an explicit constitutional version change.

## Publication candidate

This tree is the canonical Ψ-SEED v1.0 publication candidate.

Run the complete verifier from the repository root:

```text
verification/ci/run_psi_seed_requirements_verifier.sh
```

The verifier checks the frozen constitutional manifest, required persistence artifacts, and the complete pytest suite.

The constitutional boundary is frozen. Changes to constitutional meaning require an explicit constitutional version change; ordinary implementation hardening does not.
