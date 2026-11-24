# Ψ-SEED Constitutional Path v0.12

## History Authority Hardening

v0.12 separates two questions:

1. **Constitutional validity:** is the supplied sequence internally a legitimate path?
2. **Authoritative completeness:** is this sequence allowed to stand in for the complete authoritative history?

`validate_history()` remains useful for live prefixes. It does not claim that a prefix is the whole history.

`validate_authoritative_history()` adds an authority boundary requiring:
- explicit completeness declaration;
- stable transition identity;
- contiguous zero-based sequence numbers;
- parent-digest lineage from an external genesis anchor;
- no duplicate transition identities;
- an externally supplied terminal anchor.

The terminal anchor is intentionally external. A history cannot prove its own completeness by declaring itself complete.

## Attacks covered

- incomplete prefix presented as complete;
- reordered records;
- duplicated/replayed transition identity;
- forked branches presented as one linear history;
- truncated prefix with a claimed terminal boundary;
- complete linear history with matching external terminal anchor.

## Boundary

This layer proves structural completeness relative to supplied anchors. It does **not** prove that the anchors themselves are trustworthy. That remains the responsibility of the trusted-root / authority layer.

Principle:

> A history may establish that its records form a coherent chain. It may not establish, by its own declaration, that no earlier or later authoritative records exist.
