import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT
if str(ADAPTER) not in sys.path:
    sys.path.insert(0, str(ADAPTER))

import pytest
from psi_seed.persistence.testing import create_test_backend


@pytest.fixture
def backend():
    db = create_test_backend()
    try:
        yield db
    finally:
        db.close()
