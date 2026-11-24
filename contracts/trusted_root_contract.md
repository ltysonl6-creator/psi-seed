# CACC Trusted-Root Contract — CACC-TR-001

## Purpose

Define where Ψ-SEED obtains the authority that a persisted authoritative-history
integrity root is the expected root, without relying on the mutable history
being verified.

## Core rule

**The history being verified MUST NOT be the sole authority for the root used
to verify that history.**

An embedded integrity manifest may describe a history. It cannot authenticate
itself.

## Trust hierarchy

```text
Trusted Root Authority
        |
        v
Trusted Integrity Root
        |
        v
Authoritative History
        |
        v
Integrity Verification
        |
        v
Fresh Reconstruction
```

The trusted root is an external trust anchor relative to the history object.

## Root record

A trusted-root record contains:

- `contract`: `CACC-TR-001`
- `algorithm`: `sha256`
- `history_scope`: stable identifier for the history stream / instance
- `root_digest`: expected deterministic integrity root
- `anchored_at`: UTC timestamp
- `history_generation`: monotonic generation identifier
- `previous_root_digest`: optional predecessor root
- `status`: `ACTIVE` or `RETIRED`
- `provenance`: source and operator metadata
- `signature`: optional authenticated signature envelope

The root record is NOT stored inside the authoritative-history payload.

## Authority requirements

A root source MUST satisfy:

1. It is separately addressable from the mutable history.
2. A history export cannot rewrite its own expected root.
3. Root replacement is explicit and auditable.
4. Root generations are monotonic.
5. A retired root remains historically discoverable.
6. Verification fails closed when no trusted root exists.
7. Verification fails closed on algorithm, scope, generation, or digest mismatch.
8. Trust-root mutation is itself recorded outside the history being protected.

## Supported trust modes

### Mode A — Protected local anchor

A root record is stored in a separately permissioned file or operating-system
protected store.

This provides tamper detection against ordinary history writers, but is NOT
a cryptographic guarantee against an attacker who can modify both stores.

### Mode B — Signed root

A trusted public key is held outside the mutable history. The root record is
signed by the corresponding private key.

Verification requires a valid signature, expected key identifier, expected
scope, and valid generation.

### Mode C — External trust service

The expected root is obtained from an external append-only or authenticated
trust service / KMS / HSM-backed system.

The external service is authoritative for the root.

## Root rotation

Root rotation is not history rewriting.

```text
R1 ACTIVE
  |
  | explicit rotation
  v
R1 RETIRED
R2 ACTIVE
```

The old root remains verifiable for the history generation it anchored.

A new root MUST NOT silently replace an old root for the same generation.

## Verification sequence

```text
1. Load history.
2. Load trusted root from an external trust source.
3. Verify root scope and generation.
4. Recompute history integrity root.
5. Compare computed root to trusted root.
6. Only then reconstruct.
7. Compare reconstructed semantic projection.
```

If step 2 fails, reconstruction from the history MUST be rejected as
**UNTRUSTED_HISTORY** rather than treated as valid.

## What this contract does not claim

A trusted root does not prove that the original history was truthful when it
was first created. It proves that the history presented for verification
matches the externally anchored root.

Truth of the underlying events remains a separate provenance/governance
problem.

## Required API

```text
put_trusted_root(root_record)
get_trusted_root(history_scope, generation)
retire_trusted_root(history_scope, generation)
verify_history_against_trusted_root(history, history_scope, generation)
```

## Required failures

- `TRUST_ROOT_NOT_FOUND`
- `TRUST_ROOT_SCOPE_MISMATCH`
- `TRUST_ROOT_GENERATION_MISMATCH`
- `TRUST_ROOT_ALGORITHM_MISMATCH`
- `TRUST_ROOT_DIGEST_MISMATCH`
- `TRUST_ROOT_SIGNATURE_INVALID`
- `TRUST_ROOT_RETIRED`
- `TRUST_ROOT_ROTATION_INVALID`

## Fundamental invariant

**TR-001: A mutable history can never authorize its own integrity.**

That is the joint we are closing.


## Root rotation and rollback

Root rotation creates a new generation and changes the external active-generation
pointer. Earlier root records remain immutable and discoverable.

```text
R1 ACTIVE
  |
  | rotate
  v
R1 RETAINED
R2 ACTIVE
```

A rollback changes only the external active-generation pointer:

```text
R1 RETAINED
R2 ACTIVE
  |
  | rollback
  v
R1 ACTIVE POINTER
R2 RETAINED
```

The rollback MUST NOT:
- delete R2
- rewrite R2
- change R1's digest
- erase the rollback audit
- pretend R2 never existed

Rollback changes the **current trust state**, not historical root records.

A rollback target MUST already exist and MUST be verified before the active
pointer is changed.

## Rollback integrity rule

**TR-002: Rollback may change which trusted generation is current, but it
must not rewrite the generations that existed before the rollback.**

If the current authoritative-history projection also needs to roll back, that
is a separate state-transition operation and must be recorded by the
persistence/transition contracts. Changing the trust-root pointer alone does
not erase later history.
