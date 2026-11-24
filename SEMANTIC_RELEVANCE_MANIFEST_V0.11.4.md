# Ψ-SEED v0.11.4 — Semantic Relevance Manifest

## Purpose

The Semantic Relevance Manifest (SRM-001) makes the boundary between authoritative history and non-semantic projection fields machine-readable.

The goal is to prevent a future storage field from being silently ignored by semantic replay.

## Core rule

> **Every history field must have a declared semantic treatment. Unknown top-level history sections fail closed.**

## Classifications

- `authoritative` — participates in semantic interpretation and replay.
- `derived` — reconstructed from authoritative history; never independently authoritative.
- `non_semantic` — explicitly excluded from semantic meaning.

## Export-format decision

The SQLite authoritative-history exporter flattens payload keys into the record root for revisions, events, outcomes, and failures. Those flattened keys inherit the explicit classification of the containing `payload` and are therefore authoritative.

Current `entities` are mutable projections. Their flattened payload fields and projection metadata are explicitly non-semantic; authoritative identity is represented separately in `entity_identity`, while authoritative state history lives in `revisions`.

This is a deliberate contract decision, not an inference performed by the replay engine.

## Fail-closed boundary

A new top-level section such as:

```text
future_authoritative_section
```

is rejected until the manifest is updated.

A new flattened revision payload field is accepted as authoritative because the manifest explicitly declares the entire revision payload namespace authoritative. Its presence therefore changes semantic interpretation rather than disappearing from replay.

## Replay requirement

Semantic replay now includes:

```text
manifest_id
manifest_version
semantic projection
semantic integrity findings
interpretation digest
```

A fresh Ψ-SEED must use the same SRM contract to derive the same semantic interpretation.

## New issue codes

- `SRM-001` — unknown history section
- `SRM-002` — section shape mismatch
- `SRM-003` — record shape mismatch
- `SRM-004` — unclassified field

## Verification

The complete inherited suite plus the Semantic Relevance Manifest tests passes:

**86 tests passed.**

The manifest is intentionally read-mostly. It classifies meaning; it does not rewrite historical facts.
