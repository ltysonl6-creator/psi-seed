# Ψ-SEED CACC Stress / Atomicity Pass v0.2

## Scope

This pass implements the next architectural step after CACC-JOINTS-001:

1. atomic persistence for multi-write CACC operations;
2. causal-chain reconstruction and integrity verification;
3. endpoint-type verification for persisted joints;
4. deliberate broken-joint detection;
5. rollback-on-failure behavior for a partially completed Choice transaction;
6. preservation of the existing CACC and continuation tests.

## Atomicity

`SQLitePersistenceBackend.atomic()` provides a transaction boundary. CACC service
operations that create a domain entity and its causal edge now execute inside one
transaction.

If the entity write succeeds but the relationship write fails, the entity is
rolled back with the relationship. The operation cannot leave a half-committed
Choice/Transition/Outcome chain.

## Reconstruction

`CACCService.reconstruct_cacc_chain(chain_id)` collects persisted causal edges,
resolves their endpoint entities, and reports:

- missing required joints;
- orphaned joints;
- causation-chain mismatches;
- duplicate required joints;
- endpoint entity-type mismatches.

`assert_cacc_chain_integrity()` raises a CACC validation error when integrity
fails.

## Adversarial tests

Added tests deliberately:

- force a relationship-write failure after a Choice entity has been created;
- delete the `choice_executes_transition` joint and verify reconstruction detects
the missing edge.

## Verification

`pytest -q` → **17 passed**.

## Remaining boundary

The current reconstruction verifier treats the six core decision/consequence
joints as the required executable chain:

Possibility → Evaluation → Candidate → Governance → Choice → Transition → Outcome

The developmental tail (Evidence → Episode → Rule → changed possibility space)
is represented by CACC-JOINTS-001 but is not yet required by the core chain
verifier. That should be the next extension after this atomicity pass.
