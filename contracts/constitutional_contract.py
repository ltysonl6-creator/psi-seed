"""Ψ-SEED constitutional contract v1.0.

This module is intentionally boring: v1.0 is a freeze boundary, not a new
runtime policy engine.  Constitutional identifiers and their meanings are
stable API contracts.  Implementation versions may change; these identifiers
may not be silently repurposed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

CONSTITUTION_VERSION: Final[str] = "1.0"
CONTRACT_ID: Final[str] = "PSI-SEED-CONSTITUTION"
CONSTITUTIONAL_STATUS: Final[str] = "FROZEN"

# Permanent constitutional invariants.
C001_LEGITIMATE_BECOMING: Final[str] = "C-001"
C002_PATH_AUTHORITY: Final[str] = "C-002"
C003_CONVERGENT_STATE_NON_EQUIVALENCE: Final[str] = "C-003"
C004_ROLLBACK_IS_PATH: Final[str] = "C-004"
C005_STATE_VALIDITY: Final[str] = "C-005"
C006_TRANSITION_VALIDITY: Final[str] = "C-006"
C007_COMPOSITIONAL_CLOSURE: Final[str] = "C-007"
C008_PATH_CLOSURE: Final[str] = "C-008"
C009_HISTORY_COMPLETENESS: Final[str] = "C-009"
C010_HISTORY_UNIQUENESS: Final[str] = "C-010"
C011_EXTERNAL_AUTHORITY: Final[str] = "C-011"
C012_REPLAY_DETERMINISM: Final[str] = "C-012"

CONSTITUTIONAL_INVARIANTS: Final[tuple[str, ...]] = (
    C001_LEGITIMATE_BECOMING,
    C002_PATH_AUTHORITY,
    C003_CONVERGENT_STATE_NON_EQUIVALENCE,
    C004_ROLLBACK_IS_PATH,
    C005_STATE_VALIDITY,
    C006_TRANSITION_VALIDITY,
    C007_COMPOSITIONAL_CLOSURE,
    C008_PATH_CLOSURE,
    C009_HISTORY_COMPLETENESS,
    C010_HISTORY_UNIQUENESS,
    C011_EXTERNAL_AUTHORITY,
    C012_REPLAY_DETERMINISM,
)

INVARIANT_TEXT: Final[dict[str, str]] = {
    C001_LEGITIMATE_BECOMING: "A constitutional state is legitimate only if the path by which it was reached is legitimate.",
    C002_PATH_AUTHORITY: "The authoritative path is determined by trusted history authority, not by a mutable history's own declaration.",
    C003_CONVERGENT_STATE_NON_EQUIVALENCE: "Two histories reaching the same state are not constitutionally equivalent when their paths differ in meaningful ways.",
    C004_ROLLBACK_IS_PATH: "Rollback changes current state but remains part of the historical path and cannot erase prior events.",
    C005_STATE_VALIDITY: "Every authoritative state snapshot must satisfy constitutional state rules.",
    C006_TRANSITION_VALIDITY: "Every authoritative transition must connect its declared predecessor and successor states.",
    C007_COMPOSITIONAL_CLOSURE: "Every admitted change must preserve constitutional validity of the resulting effective configuration, including interactions among fields not changed by the current delta.",
    C008_PATH_CLOSURE: "Non-local and deferred path constraints must be evaluated over the complete authoritative path; later repair cannot erase an earlier path violation.",
    C009_HISTORY_COMPLETENESS: "A presented history cannot establish its own completeness; completeness requires an external authority boundary.",
    C010_HISTORY_UNIQUENESS: "An authoritative history must have one canonical ordered lineage; forks, duplicates, and replayed identities cannot be presented as one history.",
    C011_EXTERNAL_AUTHORITY: "The trust used to determine authoritative history must not be derived solely from the mutable history being judged.",
    C012_REPLAY_DETERMINISM: "Fresh reconstruction from authoritative history must deterministically reproduce constitutional interpretation without importing mutable current state.",
}


@dataclass(frozen=True)
class ConstitutionalContract:
    version: str = CONSTITUTION_VERSION
    status: str = CONSTITUTIONAL_STATUS
    invariants: tuple[str, ...] = CONSTITUTIONAL_INVARIANTS

    def assert_frozen(self) -> None:
        if self.version != "1.0" or self.status != "FROZEN":
            raise RuntimeError("constitutional contract is not frozen at v1.0")
        if self.invariants != CONSTITUTIONAL_INVARIANTS:
            raise RuntimeError("constitutional invariant registry has drifted")


CONSTITUTION: Final = ConstitutionalContract()
CONSTITUTION.assert_frozen()
