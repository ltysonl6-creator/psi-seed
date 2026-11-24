from __future__ import annotations


def test_viable_development_continues(backend):
    result = backend.evaluate_continuation(
        resources_available=True,
        resources_exhausted=False,
        viable_avenue_known=True,
        material_uncertainty=False,
        pending_material_event=False,
        evaluation_horizon_elapsed=True,
        rule_version="0.1",
    )
    assert result["state"] == "ACTIVE"
    assert result["decision"] == "CONTINUE"


def test_unknown_avenue_does_not_immediately_shutdown(backend):
    result = backend.evaluate_continuation(
        resources_available=True,
        resources_exhausted=False,
        viable_avenue_known=False,
        material_uncertainty=False,
        pending_material_event=False,
        evaluation_horizon_elapsed=False,
        rule_version="0.1",
    )
    assert result["state"] == "EVALUATING"
    assert result["decision"] == "DEFER"


def test_persistent_no_avenue_can_be_shutdown_eligible(backend):
    result = backend.evaluate_continuation(
        resources_available=True,
        resources_exhausted=False,
        viable_avenue_known=False,
        material_uncertainty=False,
        pending_material_event=False,
        evaluation_horizon_elapsed=True,
        rule_version="0.1",
    )
    assert result["state"] == "SHUTDOWN_ELIGIBLE"
    assert result["decision"] == "SHUTDOWN_ELIGIBLE"


def test_resource_exhaustion_allows_shutdown(backend):
    result = backend.evaluate_continuation(
        resources_available=False,
        resources_exhausted=True,
        viable_avenue_known=True,
        material_uncertainty=True,
        pending_material_event=True,
        evaluation_horizon_elapsed=False,
        rule_version="0.1",
    )
    assert result["state"] == "SHUTDOWN_ELIGIBLE"


def test_idle_can_be_persisted(backend):
    result = backend.record_continuation_evaluation(
        state="IDLE",
        decision="IDLE",
        evaluation_horizon={"started_at": "2026-11-14T00:00:00+00:00", "duration_seconds": 3600},
        resources={"available": True, "exhausted": False},
        development={
            "viable_avenue_known": False,
            "material_uncertainty": False,
            "pending_material_event": False,
        },
        rule_version="0.1",
    )
    assert result["state"] == "IDLE"
    assert backend.get_continuation_history()[-1]["id"] == result["id"]


def test_shutdown_preserves_evaluation_history(backend):
    result = backend.evaluate_continuation(
        resources_available=True,
        resources_exhausted=False,
        viable_avenue_known=False,
        material_uncertainty=False,
        pending_material_event=False,
        evaluation_horizon_elapsed=True,
        rule_version="0.1",
    )
    shut = backend.shutdown(result["id"])
    assert shut["status"] == "shutdown"
    history = backend.get_continuation_history()
    assert any(item["id"] == result["id"] for item in history)
    assert history[-1]["decision"] == "SHUTDOWN_ELIGIBLE"


def test_rule_version_is_persisted(backend):
    result = backend.record_continuation_evaluation(
        state="EVALUATING",
        decision="DEFER",
        evaluation_horizon={"started_at": "2026-11-14T00:00:00+00:00", "duration_seconds": 60},
        resources={"available": True, "exhausted": False},
        development={
            "viable_avenue_known": False,
            "material_uncertainty": False,
            "pending_material_event": False,
        },
        rule_version="0.2",
    )
    assert result["rule_version"] == "0.2"
