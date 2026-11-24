import hashlib
import json

import pytest

from psi_seed.cacc.trusted_root import (
    FileTrustedRootStore,
    TrustedRootError,
    TrustedRootRecord,
)


def root(text):
    return hashlib.sha256(text.encode()).hexdigest()


def rec(gen, digest, previous=None):
    return TrustedRootRecord(
        "CACC-TR-001",
        "sha256",
        "seed-main",
        digest,
        f"2026-11-24T00:0{gen}:00+00:00",
        gen,
        "ACTIVE",
        {"source": "test", "generation": gen},
        previous_root_digest=previous,
    )


def test_rotation_preserves_prior_root(tmp_path):
    s = FileTrustedRootStore(tmp_path / "roots.json")
    r1 = rec(1, root("history-1"))
    s.put(r1)
    r2 = rec(2, root("history-2"), r1.root_digest)
    s.rotate(r2)

    assert s.active_generation("seed-main") == 2
    assert s.get("seed-main", 1).root_digest == r1.root_digest
    assert s.get("seed-main", 2).root_digest == r2.root_digest


def test_rollback_changes_pointer_not_history(tmp_path):
    s = FileTrustedRootStore(tmp_path / "roots.json")
    r1 = rec(1, root("history-1"))
    r2 = rec(2, root("history-2"), r1.root_digest)
    s.put(r1)
    s.rotate(r2)

    audit = s.rollback("seed-main", 1)

    assert audit["from_generation"] == 2
    assert audit["to_generation"] == 1
    assert s.active_generation("seed-main") == 1
    assert s.get("seed-main", 2).root_digest == r2.root_digest
    registry = s.export_registry()
    assert registry["rollback_audit"][-1] == audit


def test_rollback_target_must_exist(tmp_path):
    s = FileTrustedRootStore(tmp_path / "roots.json")
    s.put(rec(1, root("history-1")))
    with pytest.raises(TrustedRootError, match="TRUST_ROOT_ROLLBACK_TARGET_NOT_FOUND"):
        s.rollback("seed-main", 99)


def test_rollback_does_not_accept_tampered_old_root(tmp_path):
    s = FileTrustedRootStore(tmp_path / "roots.json")
    r1 = rec(1, root("history-1"))
    r2 = rec(2, root("history-2"), r1.root_digest)
    s.put(r1)
    s.rotate(r2)

    # Attack: rewrite the stored R1 digest after R2 exists.
    data = s.export_registry()
    data["records"][0]["root_digest"] = root("tampered-history-1")
    (tmp_path / "roots.json").write_text(json.dumps(data, indent=2))

    # The pointer rollback itself is not allowed to make tampered R1 valid;
    # verification must still fail against the recorded R1 digest.
    s.rollback("seed-main", 1)
    with pytest.raises(TrustedRootError, match="TRUST_ROOT_DIGEST_MISMATCH"):
        s.verify({}, "seed-main", 1, r1.root_digest)


def test_repeated_rollback_is_a_state_change_with_history_preserved(tmp_path):
    s = FileTrustedRootStore(tmp_path / "roots.json")
    r1 = rec(1, root("history-1"))
    r2 = rec(2, root("history-2"), r1.root_digest)
    s.put(r1)
    s.rotate(r2)
    s.rollback("seed-main", 1)
    s.rotate(r2)
    s.rollback("seed-main", 1)

    registry = s.export_registry()
    assert [r["history_generation"] for r in registry["records"]] == [1, 2]
    assert len(registry["rollback_audit"]) == 2
    assert s.active_generation("seed-main") == 1
