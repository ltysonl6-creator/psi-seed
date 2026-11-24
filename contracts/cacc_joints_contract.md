# Ψ-SEED CACC Joint Contracts

**Identifier:** CACC-JOINTS-001  
**Status:** Canonical integration contract v0.1  
**Parent contract:** CACC-001 — Choice-and-Consequence Contract

## 1. Purpose

CACC-001 defines the lifecycle:

```text
POSSIBILITY
→ EVALUATION
→ CANDIDATE SELECTION
→ GOVERNANCE
→ CHOICE
→ TRANSITION
→ OUTCOME
→ PERSISTENCE
→ DEVELOPMENT
→ CHANGED FUTURE STATE
→ NEW POSSIBILITIES
```

This contract defines the **joints** between those stages.

The joints are causal contracts. A later object must be able to identify the
earlier object that made its existence meaningful.

> **Every material consequence must remain traceable to the permissible
> choice that caused the transition, and every developmental change must
> remain traceable to the persisted evidence that justified it.**

## 2. Joint model

| Joint | Required causal link |
|---|---|
| J01 | Possibility → Evaluation |
| J02 | Evaluation → Candidate Selection |
| J03 | Candidate Selection → Governance |
| J04 | Governance → Choice |
| J05 | Choice → Transition |
| J06 | Transition → Outcome |
| J07 | Outcome → Persistence |
| J08 | Persistence → Developmental Evidence |
| J09 | Developmental Evidence → Episode |
| J10 | Episode → Developmental Rule |
| J11 | Developmental Change → Future Possibility |
| J12 | Failure/Rollback → Original Choice/Transition |

## 3. Joint invariants

### JI-001 — Source existence
A joint cannot reference a source object that does not exist.

### JI-002 — Target existence
A committed joint cannot reference a target object that does not exist.

### JI-003 — Directionality
Relationships are directional and must not be inferred by reversing arbitrary references.

### JI-004 — Causal identity
A target must retain the identifier of the source that caused or justified it.

### JI-005 — No silent reassignment
A committed causal relationship cannot be silently redirected to another source.

### JI-006 — Governance gate
A Choice must reference a GovernanceDecision whose result is `PERMITTED`.

### JI-007 — Protected boundary precedence
A protected-boundary violation prevents a Choice from becoming executable.
The boundary is not an ordinary candidate that can be traded against continuation value.

### JI-008 — Transition before-state
Every committed Transition must preserve the state snapshot against which the Choice was made.

### JI-009 — Transition consequence
Every committed Transition must produce either an Outcome or an explicit aborted/rolled-back terminal record.

### JI-010 — Outcome provenance
Every Outcome must identify its Transition.

### JI-011 — Developmental evidence provenance
Developmental Evidence must identify the Outcome(s) that support it.

### JI-012 — Episode provenance
A DevelopmentalEpisode that claims a causal developmental event must identify the Transition or Outcome that produced the evidence.

### JI-013 — Rule provenance
A DevelopmentalRule must identify the Episode(s) and evidence supporting it.

### JI-014 — Future-state linkage
A developmental change that changes future behavior should identify the resulting policy/capability/state change and, where represented, the affected Possibility space.

### JI-015 — Failure preservation
Failure and rollback records never sever or erase the original Choice, Transition, or Outcome links.

## 4. Canonical relationship types

```text
possibility_evaluated_by
evaluation_selected_as_candidate
candidate_governed_by
governance_authorizes_choice
choice_executes_transition
transition_produces_outcome
outcome_persisted_as_evidence
evidence_forms_episode
episode_supports_rule
development_changes_possibility_space
failure_from_transition
rollback_of_transition
```

## 5. Lifecycle semantics

### J01 — Possibility → Evaluation
An Evaluation must reference exactly one Possibility as its primary subject.
Evaluation does not imply selection.

### J02 — Evaluation → Candidate Selection
Candidate selection records which evaluated possibilities are eligible for governance review.
Selection is not permission.

### J03 — Candidate Selection → Governance
Governance receives a candidate and evaluates it against protected boundaries,
invariants, permissions, risk constraints, and applicable policies.

### J04 — Governance → Choice
Only a `PERMITTED` governance decision can authorize a committed Choice.

### J05 — Choice → Transition
A Choice selects the action represented by a Transition.

The Transition must preserve:

```text
before_snapshot
proposed_state
evidence_delta
post_state
invariant_results
commit_status
```

### J06 — Transition → Outcome
The Outcome describes what actually occurred after the Transition.

### J07 — Outcome → Persistence
The Outcome becomes durable historical evidence. Persistence preserves the chain,
not merely the current state.

### J08 — Persistence → Developmental Evidence
Persisted Outcomes, Events, Failures, and related evidence can be interpreted
as developmental evidence. Interpretation must not rewrite original evidence.

### J09 — Developmental Evidence → Episode
An Episode groups evidence into a developmental event with explicit provenance.

### J10 — Episode → Rule
A DevelopmentalRule is an interpretation derived from one or more Episodes and
their evidence.

### J11 — Development → Future Possibility
Development changes what Ψ-SEED can consider, rank, govern, or execute later.
The new possibility space is a consequence of development, not a replacement for history.

### J12 — Failure/Rollback → Original Chain
Failure or rollback remains attached to the original Outcome, Transition, and Choice.
Rollback changes current operational state but does not erase history.

## 6. Rejection and non-commit paths

Not every possibility reaches Choice.

Valid paths include:

```text
Possibility → Evaluation → REJECTED
Possibility → Evaluation → DEFERRED
Possibility → Evaluation → SUPPRESSED
Possibility → Evaluation → Candidate → Governance → BLOCKED
Possibility → Evaluation → Candidate → Governance → ESCALATED
```

Material non-commit decisions remain auditable.

## 7. Causation chain

Every material chain should carry a stable `causation_chain_id`.
This supplements explicit references and supports graph traversal.

## 8. Persistence

The existing `relationships` table is the canonical persistence substrate for
the joints. CACC domain objects retain direct references; relationship edges
provide graph traversal and integrity validation.

## 9. Reconstruction

Given authoritative history, Ψ-SEED must be able to reconstruct every committed
chain for which the stages exist:

```text
Possibility
→ Evaluation
→ Candidate
→ Governance
→ Choice
→ Transition
→ Outcome
→ Evidence
→ Episode
→ Rule
```

Optional stages are represented by explicit non-commit states rather than invented.

## 10. Implementation order

```text
1. schemas
2. relationship constants
3. validation helpers
4. persistence service
5. backend integration
6. joint tests
7. reconstruction tests
8. CI verification
```

> **Possibility explains what could happen. Choice explains what was selected.
> Transition explains what changed. Outcome explains what happened. Persistence
> explains what survived. Development explains what Ψ-SEED became because of it.**
