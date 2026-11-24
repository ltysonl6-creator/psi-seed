from copy import deepcopy
from datetime import datetime, timezone

from psi_seed.persistence.sqlite.backend import SQLitePersistenceBackend
from contracts.semantic_manifest_authority import (
    TrustedSemanticManifestAuthority,
    manifest_digest,
    validate_manifest_authority,
)
from contracts.semantic_relevance_manifest import semantic_relevance_manifest
from contracts.semantic_replay import semantic_interpretation, authorized_semantic_interpretation


def ts():
    return datetime.now(timezone.utc).isoformat()


def make_history(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    e = db.create_record({
        "id": "e1", "entity_type": "belief", "status": "active",
        "created_at": ts(), "provenance": {}, "payload": {"value": "A"},
    })
    db.revise_entity(e["id"], {"value": "B"})
    return db.export_authoritative_history()


def test_manifest_digest_is_deterministic():
    m = semantic_relevance_manifest()
    assert manifest_digest(m) == manifest_digest(deepcopy(m))


def test_authority_installs_and_verifies_active_manifest(tmp_path):
    authority = TrustedSemanticManifestAuthority()
    record = authority.install_initial(semantic_relevance_manifest())
    assert authority.verify(record) is True
    report = validate_manifest_authority(make_history(tmp_path), authority, record)
    assert report["valid"] is True


def test_manifest_mutation_is_detected(tmp_path):
    authority = TrustedSemanticManifestAuthority()
    record = authority.install_initial(semantic_relevance_manifest())
    tampered = deepcopy(record)
    tampered["manifest"]["sections"]["revisions"]["payload"] = "non_semantic"
    assert authority.verify(tampered) is False
    report = validate_manifest_authority(make_history(tmp_path), authority, tampered)
    assert report["valid"] is False
    assert report["issues"][0]["code"] == "SMA-003"


def test_manifest_downgrade_is_detected():
    authority = TrustedSemanticManifestAuthority()
    m1 = semantic_relevance_manifest()
    r1 = authority.install_initial(m1)
    m2 = deepcopy(m1)
    m2["manifest_version"] = "0.11.3"
    r2 = authority.rotate(m2)
    assert authority.verify(r2) is True
    assert authority.verify(r1) is False
    assert authority.records[1]["manifest"] == m1


def test_rotation_preserves_old_generation_and_changes_active_pointer():
    authority = TrustedSemanticManifestAuthority()
    r1 = authority.install_initial(semantic_relevance_manifest())
    m2 = deepcopy(r1["manifest"])
    m2["manifest_version"] = "0.11.5"
    r2 = authority.rotate(m2)
    assert authority.active_generation == 2
    assert authority.records[1]["manifest_digest"] == r1["manifest_digest"]
    assert authority.records[1]["status"] == "RETIRED"
    assert authority.records[2]["status"] == "ACTIVE"
    assert authority.verify(r2) is True


def test_rollback_changes_pointer_not_manifest_history():
    authority = TrustedSemanticManifestAuthority()
    r1 = authority.install_initial(semantic_relevance_manifest())
    m2 = deepcopy(r1["manifest"])
    m2["manifest_version"] = "0.11.5"
    authority.rotate(m2)
    rolled = authority.rollback(1)
    assert authority.active_generation == 1
    assert authority.records[2]["manifest"] == m2
    assert authority.verify(rolled) is True
    assert authority.verify(authority.records[2]) is False


def test_history_cannot_authorize_its_own_changed_manifest(tmp_path):
    authority = TrustedSemanticManifestAuthority()
    record = authority.install_initial(semantic_relevance_manifest())
    history = make_history(tmp_path)
    history["manifest"] = deepcopy(record["manifest"])
    history["manifest"]["sections"]["events"]["payload"] = "non_semantic"
    # The history's embedded copy is not a trust source.
    report = validate_manifest_authority(history, authority, record)
    assert report["valid"] is False
    assert report["issues"][0]["code"] == "SMA-004"


def test_missing_manifest_fails_closed(tmp_path):
    authority = TrustedSemanticManifestAuthority()
    authority.install_initial(semantic_relevance_manifest())
    report = validate_manifest_authority(make_history(tmp_path), authority, None)
    assert report["valid"] is False
    assert report["issues"][0]["code"] == "SMA-002"


def test_two_instances_with_different_manifest_generations_cannot_claim_same_authority():
    m1 = semantic_relevance_manifest()
    a = TrustedSemanticManifestAuthority()
    r1 = a.install_initial(m1)
    m2 = deepcopy(m1)
    m2["manifest_version"] = "0.11.5"
    r2 = a.rotate(m2)
    assert a.verify(r1) is False
    assert a.verify(r2) is True


def test_semantic_interpretation_records_manifest_identity(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    history = make_history(tmp_path)
    interpretation = semantic_interpretation(history)
    assert interpretation["manifest_id"] == "SRM-001"
    assert interpretation["manifest_version"] == "0.11.4"
    db.close()


def test_authorized_semantic_interpretation_fails_closed_on_tampered_manifest(tmp_path):
    authority = TrustedSemanticManifestAuthority()
    record = authority.install_initial(semantic_relevance_manifest())
    history = make_history(tmp_path)
    tampered = deepcopy(record)
    tampered["manifest"]["sections"]["events"]["payload"] = "non_semantic"
    result = authorized_semantic_interpretation(history, authority, tampered)
    assert result["semantic_integrity_valid"] is False
    assert result["issues"][0]["code"] == "SMA-003"


def test_authorized_semantic_interpretation_accepts_trusted_manifest(tmp_path):
    authority = TrustedSemanticManifestAuthority()
    record = authority.install_initial(semantic_relevance_manifest())
    history = make_history(tmp_path)
    result = authorized_semantic_interpretation(history, authority, record)
    assert result["semantic_integrity_valid"] is True
