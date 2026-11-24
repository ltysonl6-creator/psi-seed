"""Trusted authority for the Ψ-SEED Semantic Relevance Manifest.

The semantic manifest is an authority boundary: it determines what history
counts as meaning-bearing. Therefore a mutable history or the manifest itself
cannot silently authorize a changed manifest.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping

SMA_CONTRACT = "SMA-001"
MANIFEST_ID = "SRM-001"
ACTIVE = "ACTIVE"
RETIRED = "RETIRED"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(manifest).encode("utf-8")).hexdigest()


def make_manifest_record(manifest: Mapping[str, Any], generation: int,
                         *, previous_manifest_digest: str | None = None,
                         effective_at: str | None = None,
                         status: str = ACTIVE) -> dict[str, Any]:
    if generation < 1:
        raise ValueError("generation must be >= 1")
    if status not in {ACTIVE, RETIRED}:
        raise ValueError("invalid manifest status")
    digest = manifest_digest(manifest)
    return {
        "authority_contract": SMA_CONTRACT,
        "manifest_id": str(manifest["manifest_id"]),
        "manifest_version": str(manifest["manifest_version"]),
        "generation": generation,
        "manifest_digest": digest,
        "previous_manifest_digest": previous_manifest_digest,
        "effective_at": effective_at,
        "status": status,
        "manifest": deepcopy(dict(manifest)),
    }


class TrustedSemanticManifestAuthority:
    """In-memory reference implementation of the trusted manifest boundary.

    The implementation intentionally preserves retired generations. Rotation
    changes the active pointer; it never rewrites an old manifest record.
    """

    def __init__(self) -> None:
        self._records: dict[int, dict[str, Any]] = {}
        self._active_generation: int | None = None

    @property
    def records(self) -> dict[int, dict[str, Any]]:
        return deepcopy(self._records)

    @property
    def active_generation(self) -> int | None:
        return self._active_generation

    def install_initial(self, manifest: Mapping[str, Any], *, effective_at: str | None = None) -> dict[str, Any]:
        if self._records:
            raise ValueError("initial manifest already installed")
        record = make_manifest_record(manifest, 1, effective_at=effective_at)
        self._records[1] = record
        self._active_generation = 1
        return deepcopy(record)

    def rotate(self, manifest: Mapping[str, Any], *, effective_at: str | None = None) -> dict[str, Any]:
        if self._active_generation is None:
            raise ValueError("no active manifest")
        generation = max(self._records) + 1
        previous = self._records[self._active_generation]["manifest_digest"]
        old = self._records[self._active_generation]
        old["status"] = RETIRED
        record = make_manifest_record(
            manifest, generation,
            previous_manifest_digest=previous,
            effective_at=effective_at,
        )
        self._records[generation] = record
        self._active_generation = generation
        return deepcopy(record)

    def rollback(self, target_generation: int) -> dict[str, Any]:
        if target_generation not in self._records:
            raise ValueError("target manifest generation does not exist")
        # Rollback changes only the active pointer. Existing records remain intact.
        for generation, record in self._records.items():
            record["status"] = ACTIVE if generation == target_generation else RETIRED
        self._active_generation = target_generation
        return deepcopy(self._records[target_generation])

    def verify(self, manifest_record: Mapping[str, Any]) -> bool:
        generation = int(manifest_record["generation"])
        trusted = self._records.get(generation)
        if trusted is None or generation != self._active_generation:
            return False
        if trusted["manifest_digest"] != manifest_record.get("manifest_digest"):
            return False
        if trusted["manifest_digest"] != manifest_digest(manifest_record.get("manifest", {})):
            return False
        return trusted["manifest"] == manifest_record.get("manifest")


def validate_manifest_authority(history: Mapping[str, Any], authority: TrustedSemanticManifestAuthority,
                                 manifest_record: Mapping[str, Any] | None) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if manifest_record is None:
        issues.append({"code": "SMA-002", "issue": "MISSING_TRUSTED_MANIFEST"})
        return {"valid": False, "issues": issues}
    if not authority.verify(manifest_record):
        issues.append({"code": "SMA-003", "issue": "UNTRUSTED_OR_INACTIVE_MANIFEST",
                       "generation": manifest_record.get("generation")})
        return {"valid": False, "issues": issues}
    if history.get("manifest") is not None and history.get("manifest") != manifest_record["manifest"]:
        issues.append({"code": "SMA-004", "issue": "HISTORY_MANIFEST_DISAGREES_WITH_TRUSTED_MANIFEST"})
    return {"valid": not issues, "issues": issues}


def authorized_semantic_manifest(history: Mapping[str, Any],
                                 authority: TrustedSemanticManifestAuthority,
                                 manifest_record: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the trusted manifest only when the external authority approves it."""
    report = validate_manifest_authority(history, authority, manifest_record)
    if not report["valid"]:
        raise ValueError("semantic manifest authority validation failed")
    return deepcopy(manifest_record["manifest"])
