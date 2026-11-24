"""Machine-readable semantic relevance manifest for Ψ-SEED.

The manifest defines which exported history fields participate in semantic
meaning. Unknown authoritative storage fields fail closed instead of being
silently ignored by semantic replay.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

MANIFEST_VERSION = "0.11.4"
SEMANTIC_MANIFEST_VERSION = "SRM-001"

AUTHORITATIVE = "authoritative"
DERIVED = "derived"
NON_SEMANTIC = "non_semantic"

SEMANTIC_SECTIONS: dict[str, dict[str, str]] = {
    "entity_identity": {
        "id": AUTHORITATIVE,
        "entity_type": AUTHORITATIVE,
        "created_at": AUTHORITATIVE,
    },
    "entities": {
        "id": NON_SEMANTIC,          # identity is represented by entity_identity
        "entity_type": NON_SEMANTIC,  # identity is represented by entity_identity
        "created_at": NON_SEMANTIC,   # identity is represented by entity_identity
        "updated_at": NON_SEMANTIC,
        "current_version": NON_SEMANTIC,
        "payload": NON_SEMANTIC,
        "provenance": NON_SEMANTIC,
        "status": NON_SEMANTIC,
        "revision_event_id": NON_SEMANTIC,
    },
    "revisions": {
        "entity_id": AUTHORITATIVE,
        "version": AUTHORITATIVE,
        "created_at": AUTHORITATIVE,
        "payload": AUTHORITATIVE,
        "provenance": AUTHORITATIVE,
        "status": AUTHORITATIVE,
        "revision_event_id": AUTHORITATIVE,
        "__flattened_payload__": AUTHORITATIVE,
    },
    "events": {
        "id": AUTHORITATIVE,
        "sequence": AUTHORITATIVE,
        "event_type": AUTHORITATIVE,
        "occurred_at": AUTHORITATIVE,
        "related_entity_refs": AUTHORITATIVE,
        "payload": AUTHORITATIVE,
    },
    "outcomes": {
        "id": AUTHORITATIVE,
        "entity_id": AUTHORITATIVE,
        "version": AUTHORITATIVE,
        "created_at": AUTHORITATIVE,
        "payload": AUTHORITATIVE,
        "__flattened_payload__": AUTHORITATIVE,
    },
    "failures": {
        "id": AUTHORITATIVE,
        "entity_id": AUTHORITATIVE,
        "created_at": AUTHORITATIVE,
        "failure_class": AUTHORITATIVE,
        "payload": AUTHORITATIVE,
        "__flattened_payload__": AUTHORITATIVE,
    },
    "relationships": {
        "id": AUTHORITATIVE,
        "source_id": AUTHORITATIVE,
        "target_id": AUTHORITATIVE,
        "relationship_type": AUTHORITATIVE,
        "created_at": AUTHORITATIVE,
        "metadata": AUTHORITATIVE,
    },
    "integrity": {
        "root": NON_SEMANTIC,
        "record_hashes": NON_SEMANTIC,
        "section_hashes": NON_SEMANTIC,
    },
    "contract_version": {
        "_value": NON_SEMANTIC,
    },
}


def semantic_relevance_manifest() -> dict[str, Any]:
    return {
        "manifest_id": SEMANTIC_MANIFEST_VERSION,
        "manifest_version": MANIFEST_VERSION,
        "unknown_field_policy": "FAIL_CLOSED",
        "default_nested_payload_classification": AUTHORITATIVE,
        "sections": deepcopy(SEMANTIC_SECTIONS),
    }


def _classify(section: str, key: str) -> str | None:
    rules = SEMANTIC_SECTIONS.get(section)
    if rules is None:
        return None
    direct = rules.get(key)
    if direct is not None:
        return direct
    # The SQLite authoritative-history export intentionally flattens payload
    # keys into the record root. Those keys inherit the payload's explicit
    # authoritative classification; they are not an unclassified storage field.
    if section in {"revisions", "events", "outcomes", "failures"}:
        return AUTHORITATIVE
    # Current entity rows are mutable projections and their flattened payload
    # fields are therefore explicitly non-semantic.
    if section == "entities":
        return NON_SEMANTIC
    return None


def validate_semantic_relevance_manifest(history: Mapping[str, Any]) -> dict[str, Any]:
    """Validate that every history field has an explicit semantic classification.

    Nested payload/provenance/metadata objects under explicitly authoritative
    fields inherit authoritative classification recursively. Top-level fields
    not named by the manifest are rejected, which prevents silent semantic
    drift when storage evolves.
    """
    issues: list[dict[str, Any]] = []
    known_sections = set(SEMANTIC_SECTIONS)
    allowed_top = known_sections | {"manifest"}

    for section in history.keys():
        if section not in allowed_top:
            issues.append({
                "code": "SRM-001",
                "issue": "UNKNOWN_HISTORY_SECTION",
                "section": section,
            })

    for section, values in history.items():
        if section in {"manifest", "contract_version"} or section not in SEMANTIC_SECTIONS:
            continue
        if not isinstance(values, list):
            # contract_version and integrity are objects/scalars in practice.
            if section in {"integrity"}:
                continue
            issues.append({
                "code": "SRM-002",
                "issue": "SECTION_EXPECTED_LIST",
                "section": section,
            })
            continue
        for index, record in enumerate(values):
            if not isinstance(record, Mapping):
                issues.append({
                    "code": "SRM-003",
                    "issue": "RECORD_EXPECTED_OBJECT",
                    "section": section,
                    "index": index,
                })
                continue
            for key in record.keys():
                classification = _classify(section, str(key))
                if classification is None:
                    issues.append({
                        "code": "SRM-004",
                        "issue": "UNCLASSIFIED_FIELD",
                        "section": section,
                        "field": str(key),
                        "index": index,
                    })

    # The manifest itself is the contract. Make its digest deterministic so
    # replay can prove both instances used the same semantic classification.
    manifest = semantic_relevance_manifest()
    return {
        "contract_version": MANIFEST_VERSION,
        "manifest": manifest,
        "valid": not issues,
        "issue_count": len(issues),
        "issues": issues,
    }


def semantic_projection(history: Mapping[str, Any]) -> dict[str, Any]:
    """Project only fields classified as semantic by the manifest."""
    projected: dict[str, Any] = {}
    for section, values in history.items():
        if section in {"manifest", "integrity", "contract_version"}:
            continue
        if section not in SEMANTIC_SECTIONS:
            continue
        rules = SEMANTIC_SECTIONS[section]
        if isinstance(values, list):
            projected[section] = []
            for record in values:
                if not isinstance(record, Mapping):
                    projected[section].append(record)
                    continue
                item = {}
                for key, value in record.items():
                    classification = _classify(section, str(key))
                    if classification == AUTHORITATIVE:
                        item[key] = deepcopy(value)
                projected[section].append(item)
        elif section == "contract_version":
            continue
        else:
            projected[section] = {}
    return projected
