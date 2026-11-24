#!/usr/bin/env python3
"""Canonical Ψ-SEED v1.0 publication verifier.

This verifier checks the frozen constitutional boundary, required persistence
integration surface, and the executable test suite. It intentionally fails
closed when required artifacts are missing or the constitutional manifest is
not frozen.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = (
    "VERSION",
    "README.md",
    "CONSTITUTIONAL_FREEZE_V1.0.md",
    "CONSTITUTIONAL_CHANGE_POLICY_V1.0.md",
    "contracts/constitutional_contract.py",
    "contracts/constitutional_manifest.v1.0.json",
    "contracts/constitutional_path.py",
    "contracts/persistence_backend_contract.md",
    "contracts/schemas/transition-transaction.schema.json",
    "psi_seed/persistence/sqlite/backend.py",
    "psi_seed/persistence/sqlite/schema.py",
    "psi_seed/persistence/sqlite/errors.py",
    "psi_seed/persistence/testing/backend_protocol.py",
    "psi_seed/persistence/testing/__init__.py",
    "tests/persistence/test_versioning.py",
    "tests/persistence/test_immutability.py",
    "tests/persistence/test_reconstruction.py",
)

EXPECTED_INVARIANTS = [f"C-{i:03d}" for i in range(1, 13)]


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def verify_artifacts() -> list[str]:
    missing = [p for p in REQUIRED_FILES if not (ROOT / p).is_file()]
    if missing:
        raise RuntimeError("missing required artifacts: " + ", ".join(missing))
    return []


def verify_version() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if version != "1.0.0":
        raise RuntimeError(f"VERSION is {version!r}, expected '1.0.0'")


def verify_constitutional_manifest() -> None:
    manifest = json.loads(
        (ROOT / "contracts/constitutional_manifest.v1.0.json").read_text(
            encoding="utf-8"
        )
    )
    if manifest.get("contract_id") != "PSI-SEED-CONSTITUTION":
        raise RuntimeError("constitutional manifest contract_id mismatch")
    if manifest.get("version") != "1.0":
        raise RuntimeError("constitutional manifest version mismatch")
    if manifest.get("status") != "FROZEN":
        raise RuntimeError("constitutional manifest is not FROZEN")
    ids = [item.get("id") for item in manifest.get("invariants", [])]
    if ids != EXPECTED_INVARIANTS:
        raise RuntimeError(f"constitutional invariant registry mismatch: {ids!r}")


def run_tests() -> None:
    cmd = [sys.executable, "-m", "pytest", "-q"]
    completed = subprocess.run(cmd, cwd=ROOT, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"pytest failed with exit code {completed.returncode}")


def main() -> int:
    try:
        verify_artifacts()
        verify_version()
        verify_constitutional_manifest()
        print("PASS: required artifacts present")
        print("PASS: VERSION == 1.0.0")
        print("PASS: constitutional manifest is frozen with C-001..C-012")
        print("RUN: pytest -q")
        run_tests()
        print("PASS: Ψ-SEED v1.0 publication verification")
        return 0
    except Exception as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
