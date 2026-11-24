from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
from typing import Any, Mapping


class TrustedRootError(Exception):
    pass


@dataclass(frozen=True)
class TrustedRootRecord:
    contract: str
    algorithm: str
    history_scope: str
    root_digest: str
    anchored_at: str
    history_generation: int
    status: str
    provenance: Mapping[str, Any]
    previous_root_digest: str | None = None
    signature: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        d = {
            "contract": self.contract,
            "algorithm": self.algorithm,
            "history_scope": self.history_scope,
            "root_digest": self.root_digest,
            "anchored_at": self.anchored_at,
            "history_generation": self.history_generation,
            "status": self.status,
            "provenance": dict(self.provenance),
        }
        if self.previous_root_digest is not None:
            d["previous_root_digest"] = self.previous_root_digest
        if self.signature is not None:
            d["signature"] = dict(self.signature)
        return d


class FileTrustedRootStore:
    """Versioned external trust-root registry.

    Root records and the current-generation pointer live outside the mutable
    history. A rollback changes the pointer only; it never rewrites or deletes
    an older root record.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"records": [], "active": {}}
        return json.loads(self.path.read_text())

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
        os.replace(tmp, self.path)

    def put(self, record: TrustedRootRecord) -> None:
        if record.contract != "CACC-TR-001":
            raise TrustedRootError("TRUST_ROOT_CONTRACT_MISMATCH")
        if record.algorithm != "sha256":
            raise TrustedRootError("TRUST_ROOT_ALGORITHM_MISMATCH")
        if len(record.root_digest) != 64:
            raise TrustedRootError("TRUST_ROOT_DIGEST_INVALID")

        data = self._load()
        records = data["records"]
        existing = next(
            (r for r in records
             if r["history_scope"] == record.history_scope
             and r["history_generation"] == record.history_generation),
            None,
        )

        if existing is not None:
            if existing["root_digest"] != record.root_digest:
                raise TrustedRootError("TRUST_ROOT_ROTATION_INVALID")
            return

        generations = [
            r["history_generation"] for r in records
            if r["history_scope"] == record.history_scope
        ]
        if generations and record.history_generation <= max(generations):
            raise TrustedRootError("TRUST_ROOT_GENERATION_NOT_MONOTONIC")

        records.append(record.as_dict())
        data["active"].setdefault(record.history_scope, record.history_generation)
        self._save(data)

    def get(self, history_scope: str, generation: int) -> TrustedRootRecord | None:
        data = self._load()
        for r in data["records"]:
            if r["history_scope"] == history_scope and r["history_generation"] == generation:
                return TrustedRootRecord(**r)
        return None

    def active_generation(self, history_scope: str) -> int | None:
        return self._load()["active"].get(history_scope)

    def rotate(self, record: TrustedRootRecord) -> None:
        self.put(record)
        data = self._load()
        data["active"][record.history_scope] = record.history_generation
        # Previous generation remains in records unchanged.
        self._save(data)

    def rollback(self, history_scope: str, target_generation: int) -> dict[str, Any]:
        data = self._load()
        current = data["active"].get(history_scope)
        target = next(
            (r for r in data["records"]
             if r["history_scope"] == history_scope
             and r["history_generation"] == target_generation),
            None,
        )
        if target is None:
            raise TrustedRootError("TRUST_ROOT_ROLLBACK_TARGET_NOT_FOUND")
        if current is None:
            raise TrustedRootError("TRUST_ROOT_NOT_FOUND")

        data["active"][history_scope] = target_generation
        audit = {
            "event": "TRUST_ROOT_ROLLBACK",
            "history_scope": history_scope,
            "from_generation": current,
            "to_generation": target_generation,
        }
        data.setdefault("rollback_audit", []).append(audit)
        self._save(data)
        return audit

    def verify(
        self,
        history: Mapping[str, Any],
        history_scope: str,
        generation: int,
        computed_root: str,
    ) -> dict[str, Any]:
        record = self.get(history_scope, generation)
        if record is None:
            raise TrustedRootError("TRUST_ROOT_NOT_FOUND")
        if record.root_digest != computed_root:
            raise TrustedRootError("TRUST_ROOT_DIGEST_MISMATCH")
        if self.active_generation(history_scope) != generation:
            raise TrustedRootError("TRUST_ROOT_NOT_ACTIVE")
        return {
            "verified": True,
            "history_scope": history_scope,
            "history_generation": generation,
            "root_digest": computed_root,
        }

    def export_registry(self) -> dict[str, Any]:
        return self._load()
