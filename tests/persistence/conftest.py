"""Canonical Ψ-SEED persistence contract test harness.

These tests intentionally do not provide a fake persistence implementation.
The production adapter must expose the test backend fixture described below.

Expected fixture:
    persistence_backend

The fixture object is expected to provide the minimal contract exercised by
these tests. Missing capabilities fail loudly rather than being skipped.
"""

import pytest


@pytest.fixture
def backend():
    """Load the real Ψ-SEED persistence test backend.

    The test suite intentionally fails during collection if the implementation
    has not exposed the expected integration fixture.
    """
    try:
        from psi_seed.persistence.testing import create_test_backend
    except Exception as exc:
        pytest.fail(
            "Ψ-SEED persistence backend is not available. "
            "Install/expose psi_seed.persistence.testing.create_test_backend "
            "before running the persistence contract suite. "
            f"Import error: {exc!r}",
            pytrace=False,
        )

    backend = create_test_backend()
    if backend is None:
        pytest.fail(
            "create_test_backend() returned None. "
            "The persistence contract suite requires a real backend.",
            pytrace=False,
        )
    return backend


def require_method(backend, name):
    method = getattr(backend, name, None)
    if not callable(method):
        pytest.fail(
            f"PERSISTENCE CONTRACT HARNESS ERROR: backend is missing required "
            f"method {name}(). The test cannot establish the invariant.",
            pytrace=False,
        )
    return method
