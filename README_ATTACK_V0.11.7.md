# Ψ-SEED Semantic Authority Transition Red-Team v0.11.7

This package attacks the *rules that classify semantic-authority transitions*, rather than merely attacking hashes or signatures.

The red-team target is a proposed SMA-002 transition policy. The attack harness intentionally contains a reference classifier with common failure modes so the tests can demonstrate why those rules cannot be allowed to self-authorize their own changes.

## Core finding

A transition can be:

- correctly hashed,
- correctly signed,
- approved by the currently trusted authority,
- internally consistent,
- and still semantically invalid,

if the machinery deciding whether the transition is "safe" can itself be changed, bypassed, weakened, or ambiguously interpreted by the transition.

## Attacks

- RT-201: self-declared SAFE classification
- RT-202: unknown semantic path silently ignored
- RT-203: nested semantic change hidden behind an unclassified container
- RT-204: approval-threshold downgrade bundled with semantic change
- RT-205: classifier-policy weakening staged across two individually "safe" rotations
- RT-206: rollback reactivates a generation that the forward classifier would reject
- RT-207: classifier-version substitution lets a transition choose the evaluator
- RT-208: rename/alias bypass changes meaning without changing a recognized path

## Required architectural rule

The evaluator of constitutional/semantic transitions must be constitutionally prior to the transition it evaluates.

> The rules that decide whether a constitutional change is admissible cannot be changed by the change they are deciding whether to admit.

Unknown semantic differences fail closed. Rollback is evaluated as a semantic transition. Evaluator identity/version is itself protected constitutional state.
