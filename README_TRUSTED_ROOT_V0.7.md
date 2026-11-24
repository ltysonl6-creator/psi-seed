# Ψ-SEED CACC Trusted Root v0.7

This package adds CACC-TR-001, the trusted-root contract.

Core rule:
**A mutable history can never authorize its own integrity.**

The package includes:
- `contracts/trusted_root_contract.md`
- `contracts/schemas/trusted-root.schema.json`
- `psi_seed/cacc/trusted_root.py`
- tests for external anchoring, root replacement rejection, and fail-closed verification

This implementation uses a separately stored root record as the local trust
mode. It explicitly does not claim protection from an attacker who can modify
both the history database and the trust-root store.

For stronger deployment, replace the local store with a signed-root or
external trust-service implementation while preserving CACC-TR-001.
