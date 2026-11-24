"""Persistence adapter errors."""

class PersistenceError(RuntimeError):
    pass

class ValidationError(PersistenceError):
    pass

class IdentityConflictError(PersistenceError):
    pass

class VersionConflictError(PersistenceError):
    pass

class ImmutableEventError(PersistenceError):
    pass

class ReferenceIntegrityError(PersistenceError):
    pass

class TransactionError(PersistenceError):
    pass

class ConcurrencyError(PersistenceError):
    pass

class RecoveryRequiredError(PersistenceError):
    pass
