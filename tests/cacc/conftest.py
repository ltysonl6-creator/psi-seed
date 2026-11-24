import pytest
from psi_seed.persistence.sqlite.backend import SQLitePersistenceBackend

@pytest.fixture
def backend(tmp_path):
    return SQLitePersistenceBackend(tmp_path / "cacc.sqlite3")
