import hashlib
import json
from psi_seed.cacc.trusted_root import FileTrustedRootStore, TrustedRootError, TrustedRootRecord


def test_trusted_root_is_external_and_verifies(tmp_path):
    store = FileTrustedRootStore(tmp_path / "trusted-root.json")
    digest = hashlib.sha256(b"authoritative-history").hexdigest()
    record = TrustedRootRecord(
        contract="CACC-TR-001",
        algorithm="sha256",
        history_scope="seed-main",
        root_digest=digest,
        anchored_at="2026-11-24T00:00:00+00:00",
        history_generation=1,
        status="ACTIVE",
        provenance={"source": "test"},
    )
    store.put(record)
    assert store.verify({}, "seed-main", 1, digest)["verified"] is True


def test_history_cannot_replace_trusted_root(tmp_path):
    store = FileTrustedRootStore(tmp_path / "trusted-root.json")
    d1 = hashlib.sha256(b"history-1").hexdigest()
    d2 = hashlib.sha256(b"history-2").hexdigest()
    r1 = TrustedRootRecord("CACC-TR-001","sha256","seed-main",d1,"2026-11-24T00:00:00+00:00",1,"ACTIVE",{"source":"test"})
    store.put(r1)
    r2 = TrustedRootRecord("CACC-TR-001","sha256","seed-main",d2,"2026-11-24T00:01:00+00:00",1,"ACTIVE",{"source":"tamper"})
    try:
        store.put(r2)
        assert False, "expected rotation rejection"
    except TrustedRootError as exc:
        assert str(exc) == "TRUST_ROOT_ROTATION_INVALID"


def test_missing_root_fails_closed(tmp_path):
    store = FileTrustedRootStore(tmp_path / "trusted-root.json")
    digest = hashlib.sha256(b"history").hexdigest()
    try:
        store.verify({}, "seed-main", 1, digest)
        assert False, "expected missing-root rejection"
    except TrustedRootError as exc:
        assert str(exc) == "TRUST_ROOT_NOT_FOUND"
