# CACC Root Rotation & Rollback Attack — v0.8

## Question attacked

Can trusted-root rotation and rollback change the current trust state without
rewriting the history of what happened?

## Result

[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m                                                                 [100%][0m
[32m[32m[1m8 passed[0m[32m in 0.07s[0m[0m

## Contract

**TR-002: Rollback may change which trusted generation is current, but it must
not rewrite the generations that existed before the rollback.**

R1 and R2 remain immutable records. Rollback changes only the externally stored
active-generation pointer and appends a rollback audit record.

## Attacks performed

1. Rotate R1 -> R2 and verify R1 remains retrievable.
2. Roll back R2 -> R1 and verify R2 remains retrievable.
3. Attempt rollback to nonexistent generation; rejected.
4. Tamper R1 after R2 exists; rollback does not make the tampered root valid.
5. Repeat rollback/rotation and verify generations are retained rather than
   collapsed into a single current record.

## Important boundary

This tests the **trusted-root state**. It does not silently equate a trust-root
rollback with rolling back Ψ-SEED's entire current domain state.

If Ψ-SEED's actual state must roll back from the state represented by R2 to the
state represented by R1, that is a separate Transition/Rollback operation and
must itself be persisted as history. The trust-root pointer cannot erase those
later events.

## Security conclusion

Rollback changes state. It does not change history.
