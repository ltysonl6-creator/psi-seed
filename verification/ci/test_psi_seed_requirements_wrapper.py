from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "verification" / "ci" / "verify_psi_seed_requirements.py"
WRAPPER = ROOT / "verification" / "ci" / "run_psi_seed_requirements_verifier.sh"


def test_verifier_exists_and_is_executable():
    assert VERIFIER.is_file()
    assert WRAPPER.is_file()
    assert WRAPPER.stat().st_mode & 0o111


def test_verifier_accepts_current_tree():
    result = subprocess.run(
        [sys.executable, str(VERIFIER)], cwd=ROOT, text=True,
        capture_output=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: Ψ-SEED v1.0 publication verification" in result.stdout


def test_wrapper_accepts_current_tree():
    result = subprocess.run(
        [str(WRAPPER)], cwd=ROOT, text=True,
        capture_output=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
