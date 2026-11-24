# CACC Integrity Loop v0.4

## Question
Can the full CACC loop survive corruption, rollback, reconstruction, and replay without changing what actually happened?

## Result
**23 tests passed.**

The answer is: **yes for the integrity properties implemented here, with one important boundary: replay is a deterministic reconstruction/replay audit, not re-execution of real-world side effects.**

## Added
- deterministic `replay_cacc_chain(chain_id)` projection + SHA-256 digest
- replay is non-mutating
- current entity payload is checked against its authoritative latest revision
- causal payload references are checked against persisted relationship endpoints
- `rollback_transition(...)` records rollback as a new immutable fact
- rollback restores the transition's `before_snapshot` as recorded state without rewriting the original transition or outcome
- adversarial tests for payload corruption and payload rewiring
- rollback preservation test
- deterministic, non-mutating replay test

## Integrity properties demonstrated
1. Corrupting current payload is detected.
2. Rewiring a payload reference while leaving the causal edge intact is detected.
3. Deleting a causal joint is detected.
4. A rollback does not erase the original transition or outcome.
5. Replay produces the same digest on repeated runs.
6. Replay does not mutate authoritative history.
7. The complete developmental chain remains reconstructable after rollback.

## Boundary
The replay mechanism deliberately does **not** re-run external actions. It replays the authoritative persisted causal projection. A future execution-replay layer would need explicit idempotency and side-effect isolation contracts before it could safely re-execute transitions.

## Core principle
**Rollback changes current state; it does not rewrite what happened. Replay reconstructs what happened; it does not make it happen again.**
