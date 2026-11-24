# Semantic Authority Transition Red-Team v0.11.7

## Result

The classifier itself is an authority boundary. If its classification rules are mutable by the transition being evaluated, the transition can make itself look safe.

The red-team model produced eight attack classes.

### RT-201 — self-declared classification
The transition supplies `transition_classification=SAFE`. If the evaluator trusts that field, the subject being evaluated is effectively allowed to write its own verdict.

### RT-202 — unknown-path omission
A new semantic field not in the classifier's path table is ignored. The change therefore disappears from the semantic diff.

### RT-203 — nested semantic hiding
A semantic rule nested under an unclassified container is missed.

### RT-204 — approval downgrade
A transition changes both meaning and the approval threshold used to judge that meaning. If the new threshold is used for its own admission, the transition can lower the bar while jumping over it.

### RT-205 — staged constitutional drift
Transition A weakens the classifier policy while looking harmless. Transition B then uses the weakened policy to make a semantic change. Neither step is safe merely because each step individually passes a mutable evaluator.

### RT-206 — rollback bypass
Rollback is treated as pointer movement rather than a semantic transition. A generation rejected by the forward path can therefore become active through rollback.

### RT-207 — evaluator substitution
The transition changes the evaluator/classifier version. If the new evaluator is then used to judge the same transition, the transition chooses its own judge.

### RT-208 — alias/rename bypass
A semantic field is renamed so it leaves the classifier's recognized path set. Meaning changes while the classifier sees no protected semantic path change.

## Architectural consequence

SMA-002 cannot merely define a list of transition classifications. The classifier, path grammar, semantic projection, approval thresholds, and evaluator identity must themselves be constitutionally protected.

The evaluation order must be:

```text
TRUSTED CONSTITUTION
        |
        v
TRUSTED EVALUATOR IDENTITY + VERSION
        |
        v
CANONICAL SEMANTIC PROJECTION
        |
        v
DETERMINISTIC DIFF
        |
        v
CLASSIFICATION
        |
        v
APPROVAL REQUIREMENT
        |
        v
TRANSITION ADMISSIBILITY
```

Critically, the candidate transition is NOT allowed to modify any of the first five layers while those layers are being used to evaluate that candidate.

## New invariant candidates

- SMA-002-01: Evaluator Self-Immunity — a transition cannot modify the evaluator that judges it.
- SMA-002-02: Fail-Closed Unknowns — every semantic difference must be classified; unknown differences reject the transition.
- SMA-002-03: Canonical Path Integrity — aliases/renames cannot evade semantic classification.
- SMA-002-04: Approval Monotonicity — a transition cannot reduce the approval level required to admit itself.
- SMA-002-05: Rollback Equivalence — rollback is subject to the same semantic admissibility rules as forward rotation.
- SMA-002-06: Staged-Drift Detection — a sequence of individually admissible transitions cannot bypass a constitutional constraint in aggregate.
- SMA-002-07: Evaluator Version Pinning — evaluator identity/version is trusted independently of candidate manifest content.
- SMA-002-08: Projection Authority — the canonical semantic projection cannot be redefined by the transition it evaluates.

## Core finding

> **A rule that decides whether a change is safe cannot be safely changed by the change it is deciding whether to accept.**

Or, in the project's shorter language:

> **The judge cannot rewrite the rules of the trial while judging itself.**
