from datetime import datetime, timezone

from psi_seed.persistence.sqlite.backend import SQLitePersistenceBackend
from contracts.semantic_convergence import compare_meaning, mutate_nonsemantic_projection, mutate_semantic_history


def ts():
    return datetime.now(timezone.utc).isoformat()


def make(db):
    e = db.create_record({
        "id": "e1", "entity_type": "belief", "status": "active",
        "created_at": ts(), "provenance": {"source": "test"},
        "payload": {"value": "A"},
    })
    db.revise_entity(e["id"], {"value": "B"})
    return db.export_authoritative_history()


def test_nonsemantic_current_projection_converges(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    history = make(db)
    attacked = mutate_nonsemantic_projection(history)
    result = compare_meaning(history, attacked)
    assert result["equivalent"] is True
    db.close()


def test_semantic_revision_change_cannot_converge(tmp_path):
    db = SQLitePersistenceBackend(tmp_path / "seed.sqlite3")
    history = make(db)
    attacked = mutate_semantic_history(history)
    result = compare_meaning(history, attacked)
    assert result["equivalent"] is False
    db.close()


def test_same_current_state_different_revision_path_cannot_converge(tmp_path):
    db1 = SQLitePersistenceBackend(tmp_path / "a.sqlite3")
    h1 = make(db1)

    db2 = SQLitePersistenceBackend(tmp_path / "b.sqlite3")
    e = db2.create_record({
        "id": "e1", "entity_type": "belief", "status": "active",
        "created_at": ts(), "provenance": {"source": "test"},
        "payload": {"value": "A"},
    })
    db2.revise_entity(e["id"], {"value": "X"})
    db2.revise_entity(e["id"], {"value": "B"})
    h2 = db2.export_authoritative_history()

    result = compare_meaning(h1, h2)
    assert result["equivalent"] is False
    db1.close(); db2.close()
