"""Test-facing persistence backend contract interface."""

from .backend_protocol import (
    BackendNotConfiguredError,
    PersistenceBackendError,
    PersistenceTestBackend,
    create_test_backend,
)

__all__ = [
    "BackendNotConfiguredError",
    "PersistenceBackendError",
    "PersistenceTestBackend",
    "create_test_backend",
]
