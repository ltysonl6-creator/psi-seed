# Ψ-SEED Constitutional Change Policy v1.0

The v1.0 constitution is frozen.

## Implementation changes allowed without constitutional revision

- bug fixes that preserve invariant meaning;
- stronger validation of an existing invariant;
- additional corruption/red-team tests;
- deterministic performance improvements;
- storage and adapter changes;
- refactoring that preserves observable contract behavior;
- additional diagnostics and audit evidence.

## Constitutional revision required

A new constitutional version is required if a change:

- changes the meaning of C-001 through C-012;
- weakens an existing invariant;
- makes a previously invalid path constitutionally valid;
- makes a previously valid path constitutionally invalid for a reason not already covered by an existing invariant;
- changes the trust boundary;
- changes what counts as authoritative history;
- changes the definition of legitimate becoming.

## Required process for a constitutional revision

1. Preserve v1.0 unchanged.
2. Define the proposed new invariant or semantic change.
3. Add an explicit constitutional transition record.
4. Define migration and compatibility behavior.
5. Add adversarial tests for the old and new boundaries.
6. Establish a new trusted constitutional root.
7. Publish a new constitutional version.

No implementation update may silently redefine the constitution.
