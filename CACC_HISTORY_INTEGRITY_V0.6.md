# CACC History Integrity v0.6

## Result

The replay attack was extended with an authoritative-history integrity layer.

**29 tests pass.**

## What changed

`SQLitePersistenceBackend.export_authoritative_history()` now emits an `integrity` manifest containing:

- SHA-256 algorithm identifier
- deterministic per-record hashes for entity identities, revisions, events, outcomes, failures, and relationships
- a deterministic root digest over those record hashes

New verification API:

- `SQLitePersistenceBackend.compute_history_integrity(history)`
- `SQLitePersistenceBackend.verify_history_integrity(history, expected_root=None)`
- `CACCService.verify_authoritative_history(history, expected_root=None)`

## Attack coverage

The test suite now demonstrates:

1. A clean authoritative export verifies against its anchored root.
2. A tampered revision fails verification against the original anchored root.
3. A tampered relationship fails verification against the original anchored root.
4. An internally inconsistent embedded manifest is detected.
5. Existing fresh-rebuild and replay tests still pass.

## Important boundary

A digest is not itself a trusted authority. If an attacker can modify both the history and its embedded integrity manifest, the embedded manifest cannot prove that the replacement is authentic.

For tamper detection against a hostile writer, the root digest must be retained in a trusted location outside the mutable history being checked, or replaced by a stronger authenticated mechanism such as a digital signature / external trust anchor.

Therefore the current contract is:

**Authoritative history + trusted integrity root -> tampering is detectable.**

It is intentionally not claimed that an unanchored SHA-256 manifest provides authenticity by itself.

## Architectural consequence

Replay is now conceptually:

```text
LIVE INSTANCE
     |
     | export
     v
AUTHORITATIVE HISTORY
     |
     | verify against trusted root
     v
INTEGRITY-VALID HISTORY
     |
     | fresh reconstruction
     v
FRESH INSTANCE
     |
     | semantic comparison / causal verification
     v
EQUIVALENCE
```

The next hardening step, if desired, is to define the trusted-root storage/signature contract rather than adding more hashing ad hoc.
