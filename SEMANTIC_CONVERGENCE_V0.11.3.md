# Ψ-SEED v0.11.3 — Semantic Convergence Red Team

## Attack question
Can two histories that mean different things collapse to the same semantic interpretation?

## Contract
A fresh reconstruction may ignore fields that are explicitly non-authoritative projections,
but it must not collapse distinct authoritative histories into one meaning.

### Allowed convergence
- mutable current-state projection fields (`updated_at`, `current_version`, current payload projection)
- integrity manifest metadata

These are deliberately excluded from semantic meaning because authoritative revisions/events/etc.
are the source of truth.

### Forbidden convergence
Any change to authoritative:
- revision payload/provenance/status
- revision chronology or event linkage
- event records
- outcomes
- failures
- relationships
- entity identity

must change the semantic interpretation or produce a semantic-integrity finding.

## Attack corpus
- SC-001 meaningful revision mutation must not converge.
- SC-002 non-authoritative projection poisoning is allowed to converge.
- SC-003 different revision paths ending in the same current state must not converge.

## Result
The v0.11.2 semantic interpretation boundary passes this convergence corpus.
No semantic-convergence hole was found in the tested authoritative sections.

This is a red-team result, not proof that the interpretation is complete. The next boundary is
to establish a machine-readable semantic relevance manifest so that future fields cannot be
silently added to authoritative storage without deciding whether they belong to meaning.
