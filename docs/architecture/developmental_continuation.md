# Developmental Continuation Integration

Ψ-SEED continuation is a governed developmental decision, not a survival objective.

The persistence backend records continuation evaluations as immutable historical entities of type `continuation_evaluation`.

The controller distinguishes:

- `ACTIVE`
- `IDLE`
- `DEFERRED`
- `EVALUATING`
- `SHUTDOWN_ELIGIBLE`
- `SHUTDOWN`

The backend exposes `evaluate_continuation()`, `record_continuation_evaluation()`, `get_continuation_history()`, and `shutdown()`.

A missing avenue is not immediately treated as terminal. The evaluation horizon must elapse before developmental exhaustion can make shutdown eligible.
