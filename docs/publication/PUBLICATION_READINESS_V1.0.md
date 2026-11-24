# Ψ-SEED v1.0 Publication Readiness

Status: **READY FOR PUBLICATION CANDIDATE**

## Frozen boundary

The constitutional contract is frozen at version 1.0.

Permanent constitutional identifiers:

- C-001 through C-012
- STATE → TRANSITION → COMPOSITION → PATH → AUTHORITY

The constitution governs not only permissible states, but legitimate ways of becoming those states.

## Verified integration

The canonical package contains:

- frozen constitutional contract and manifest;
- constitutional path validator;
- SQLite persistence backend;
- persistence backend protocol;
- P-001 through P-015 persistence contract tests;
- CACC and semantic-integrity regression tests;
- standalone publication verifier;
- CI wrapper.

The publication verifier checks required artifacts and then executes the full pytest suite.

## Verification rule

A publication candidate is accepted only when the verifier exits successfully in a clean checkout.

The verifier is intentionally fail-closed for missing artifacts or a non-frozen constitutional manifest.

## Remaining publication decisions

These are release-administration decisions rather than constitutional design changes:

1. choose a public hosting location;
2. choose a license;
3. create the public repository/release tag;
4. optionally add external CI (GitHub Actions or equivalent);
5. publish the release archive and checksum.

No constitutional redesign is required for these steps.
