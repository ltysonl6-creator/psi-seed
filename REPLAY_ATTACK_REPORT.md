# CACC Replay Attack — v0.5

## Question
Can authoritative history be used to build a genuinely fresh Ψ-SEED persistence instance, then prove semantic equivalence without importing mutable current state?

## Result
**25 tests passed.**

## Changes
- Added `SQLitePersistenceBackend.from_authoritative_history()`.
- Added an `entity_identity` manifest to authoritative export.
- Fresh rebuild imports stable identity metadata plus revision history, events, outcomes, failures, and relationships.
- Mutable current payload/status/version is not copied from the source entity table.
- Added semantic projection that compares durable meaning rather than mutable current-state bookkeeping.
- Added CACC service helpers for fresh rebuild and reconstruction against an explicitly supplied backend.

## Adversarial checks
1. Export authoritative history.
2. Create a brand-new SQLite instance from that history.
3. Compare semantic projections.
4. Verify the fresh instance reconstructs the CACC chain.
5. Mutate the source instance's current payload after export.
6. Verify the fresh instance remains unchanged and semantically equivalent to the exported history.

## Boundary
This proves deterministic historical reconstruction from the exported contract surface. It does **not** yet prove that every possible corruption of the exported history itself is detectable, nor that arbitrary external side effects can be safely replayed. Those are separate attack surfaces.

## Principle
**Current state is not the authority for reconstruction. Authoritative history is.**
