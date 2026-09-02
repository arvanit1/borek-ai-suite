"""BT-25 backend-owned PresentationPlan-to-presentation continuation tests."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.schemas.jobs import JobStage, JobStatus
from app.services import job_service, presentation_generation
from app.services.data.memory_store import MemoryDataStore
from app.services.presentation_pipeline import continue_after_planning


ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _store_with_confirmed_framework() -> tuple[MemoryDataStore, dict, dict]:
    store = MemoryDataStore()
    opportunity = store.create_opportunity(
        user_id=USER_ID,
        client_name="Acme",
        opportunity_name="Browser-independent build",
        department="Finance",
        language="en",
    )
    framework_json = json.loads(FRAMEWORK_FIXTURE.read_text(encoding="utf-8"))
    framework_json["opportunity_id"] = str(opportunity["id"])
    framework = store.create_framework_version(
        opportunity_id=opportunity["id"],
        user_id=USER_ID,
        framework_json=framework_json,
        status="confirmed",
    )
    return store, opportunity, framework


def _plan_json(title: str = "BT-25 plan") -> dict:
    return {
        "schema_version": "1.0",
        "title": title,
        "slides": [
            {
                "order": 1,
                "purpose": "Cover",
                "layoutId": "COVER_01",
                "frameworkReferences": ["chapter_1"],
            }
        ],
    }


def _persist_plan(store: MemoryDataStore, framework: dict, *, plan_id=None, title="BT-25 plan"):
    return store.create_presentation_plan(
        framework_version_id=framework["id"],
        user_id=USER_ID,
        plan_json=_plan_json(title),
        presentation_plan_id=plan_id,
    )


def _completed_planning_job(
    store: MemoryDataStore,
    opportunity: dict,
    framework: dict,
    plan: dict,
    *,
    auto_continue: bool,
):
    job = job_service.create_job(
        opportunity["id"],
        "presentation_planning",
        auto_continue=auto_continue,
        enqueue={
            "framework_version_id": str(framework["id"]),
            "user_id": str(USER_ID),
            "presentation_plan_id": str(plan["id"]),
        },
        repository=store,
    )
    job_service.ensure_stage(job.id, JobStage.PRESENTATION_PLANNING, repository=store)
    return job_service.complete_job(
        job.id,
        repository=store,
        result_json={"presentation_plan_id": str(plan["id"])},
    )


def _jobs(store: MemoryDataStore, job_type: str) -> list[dict]:
    return [
        row
        for row in store.generation_jobs.values()
        if row["job_type"] == job_type
    ]


def test_auto_continue_enqueues_existing_presentation_generation_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, opportunity, framework = _store_with_confirmed_framework()
    plan = _persist_plan(store, framework)
    planning_job = _completed_planning_job(
        store,
        opportunity,
        framework,
        plan,
        auto_continue=True,
    )
    dispatched: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        presentation_generation,
        "_dispatch_task",
        lambda _task, *args: dispatched.append(args),
    )

    presentation, resolved_plan, generation_job, is_existing = continue_after_planning(
        store,
        planning_job_id=planning_job.id,
    )

    assert is_existing is False
    assert resolved_plan["id"] == plan["id"]
    assert presentation["presentation_plan_id"] == plan["id"]
    assert generation_job.job_type == "presentation_generation"
    assert len(_jobs(store, "presentation_generation")) == 1
    assert dispatched == [
        (str(generation_job.id), str(presentation["id"]), str(USER_ID))
    ]


def test_manual_plan_completion_does_not_start_presentation_generation() -> None:
    store, opportunity, framework = _store_with_confirmed_framework()
    plan = _persist_plan(store, framework)
    planning_job = _completed_planning_job(
        store,
        opportunity,
        framework,
        plan,
        auto_continue=False,
    )

    assert continue_after_planning(store, planning_job_id=planning_job.id) is None
    assert _jobs(store, "presentation_generation") == []
    assert store.presentations == {}


def test_planning_failure_never_enqueues_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    store, opportunity, framework = _store_with_confirmed_framework()
    plan_id = uuid4()
    planning_job = job_service.create_job(
        opportunity["id"],
        "presentation_planning",
        auto_continue=True,
        enqueue={
            "framework_version_id": str(framework["id"]),
            "user_id": str(USER_ID),
            "presentation_plan_id": str(plan_id),
        },
        repository=store,
    )
    monkeypatch.setattr(
        "app.services.data.build_worker_data_store",
        lambda: store,
    )

    def fail_planning(*_args, **_kwargs):
        raise RuntimeError("planning failed")

    monkeypatch.setattr(
        presentation_generation,
        "execute_presentation_planning",
        fail_planning,
    )

    from app.worker import run_presentation_planning_task

    with pytest.raises(RuntimeError, match="planning failed"):
        run_presentation_planning_task.run(
            str(planning_job.id),
            str(framework["id"]),
            str(USER_ID),
            str(plan_id),
        )

    failed = job_service.get_job(planning_job.id, repository=store)
    assert failed is not None
    assert failed.status == JobStatus.FAILED
    assert _jobs(store, "presentation_generation") == []


def test_existing_active_generation_is_reused_via_at56(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, opportunity, framework = _store_with_confirmed_framework()
    plan = _persist_plan(store, framework)
    planning_job = _completed_planning_job(
        store,
        opportunity,
        framework,
        plan,
        auto_continue=True,
    )
    presentation = store.create_presentation(
        presentation_plan_id=plan["id"],
        user_id=USER_ID,
        name="Already generating",
    )
    existing = job_service.create_job(
        opportunity["id"],
        "presentation_generation",
        presentation_id=presentation["id"],
        enqueue={"presentation_id": str(presentation["id"]), "user_id": str(USER_ID)},
        repository=store,
    )
    monkeypatch.setattr(
        presentation_generation,
        "_dispatch_task",
        lambda *_args: pytest.fail("AT-56 reuse must not dispatch a duplicate task"),
    )

    reused_presentation, reused_plan, reused_job, is_existing = continue_after_planning(
        store,
        planning_job_id=planning_job.id,
    )

    assert is_existing is True
    assert reused_job.id == existing.id
    assert reused_presentation["id"] == presentation["id"]
    assert reused_plan["id"] == plan["id"]
    assert len(_jobs(store, "presentation_generation")) == 1


def test_worker_completion_continues_without_any_frontend_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, opportunity, framework = _store_with_confirmed_framework()
    plan_id = uuid4()
    planning_job = job_service.create_job(
        opportunity["id"],
        "presentation_planning",
        auto_continue=True,
        enqueue={
            "framework_version_id": str(framework["id"]),
            "user_id": str(USER_ID),
            "presentation_plan_id": str(plan_id),
        },
        repository=store,
    )
    monkeypatch.setattr("app.services.data.build_worker_data_store", lambda: store)
    monkeypatch.setattr(
        presentation_generation,
        "execute_presentation_planning",
        lambda current_store, **kwargs: _persist_plan(
            current_store,
            framework,
            plan_id=kwargs["presentation_plan_id"],
        ),
    )
    dispatched: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        presentation_generation,
        "_dispatch_task",
        lambda _task, *args: dispatched.append(args),
    )

    from app.worker import run_presentation_planning_task

    result = run_presentation_planning_task.run(
        str(planning_job.id),
        str(framework["id"]),
        str(USER_ID),
        str(plan_id),
    )

    completed = job_service.get_job(planning_job.id, repository=store)
    assert completed is not None and completed.status == JobStatus.COMPLETED
    assert result["presentation_plan_id"] == str(plan_id)
    assert len(_jobs(store, "presentation_generation")) == 1
    assert len(dispatched) == 1


def test_continuation_uses_exact_completed_plan_not_latest_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, opportunity, framework = _store_with_confirmed_framework()
    completed_plan = _persist_plan(store, framework, title="Completed plan")
    _persist_plan(store, framework, title="Different later plan")
    planning_job = _completed_planning_job(
        store,
        opportunity,
        framework,
        completed_plan,
        auto_continue=True,
    )
    monkeypatch.setattr(presentation_generation, "_dispatch_task", lambda *_args: None)

    presentation, resolved_plan, _job, _existing = continue_after_planning(
        store,
        planning_job_id=planning_job.id,
    )

    assert resolved_plan["id"] == completed_plan["id"]
    assert presentation["presentation_plan_id"] == completed_plan["id"]


def test_auto_continue_request_is_additive_and_defaults_off() -> None:
    from app.schemas.presentations import GeneratePresentationPlanRequest

    assert GeneratePresentationPlanRequest().auto_continue is False
    assert GeneratePresentationPlanRequest(auto_continue=True).auto_continue is True


def test_approve_and_build_upgrades_existing_manual_planning_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, opportunity, framework = _store_with_confirmed_framework()
    plan_id = uuid4()
    existing = job_service.create_job(
        opportunity["id"],
        "presentation_planning",
        auto_continue=False,
        enqueue={
            "framework_version_id": str(framework["id"]),
            "user_id": str(USER_ID),
            "presentation_plan_id": str(plan_id),
        },
        repository=store,
    )
    job_service.ensure_stage(
        existing.id,
        JobStage.PRESENTATION_PLANNING,
        repository=store,
    )
    monkeypatch.setattr(
        presentation_generation,
        "_dispatch_task",
        lambda *_args: pytest.fail("an active planning job must be reused"),
    )

    plan, reused, is_existing = presentation_generation.enqueue_presentation_plan_generate(
        store,
        opportunity_id=opportunity["id"],
        user_id=USER_ID,
        framework_version_id=framework["id"],
        auto_continue=True,
    )

    refreshed = job_service.get_job(existing.id, repository=store)
    assert is_existing is True
    assert reused.id == existing.id
    assert plan["id"] == plan_id
    assert refreshed is not None
    assert refreshed.auto_continue is True
    assert job_service.job_to_response(refreshed).result["_enqueue"]["auto_continue"] is True
    assert len(_jobs(store, "presentation_planning")) == 1


def test_upgrade_after_planning_completes_during_reuse_starts_generation_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, opportunity, framework = _store_with_confirmed_framework()
    plan_id = uuid4()
    plan = _persist_plan(store, framework, plan_id=plan_id)
    existing = job_service.create_job(
        opportunity["id"],
        "presentation_planning",
        auto_continue=False,
        enqueue={
            "framework_version_id": str(framework["id"]),
            "user_id": str(USER_ID),
            "presentation_plan_id": str(plan["id"]),
        },
        repository=store,
    )
    job_service.ensure_stage(
        existing.id,
        JobStage.PRESENTATION_PLANNING,
        repository=store,
    )
    real_reuse = job_service.reuse_active_generation_job

    def reuse_then_complete(*args, **kwargs):
        job = real_reuse(*args, **kwargs)
        if job is not None and job.id == existing.id:
            job_service.complete_job(
                job.id,
                repository=store,
                result_json={"presentation_plan_id": str(plan["id"])},
            )
        return job

    monkeypatch.setattr(job_service, "reuse_active_generation_job", reuse_then_complete)
    dispatched: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        presentation_generation,
        "_dispatch_task",
        lambda _task, *args: dispatched.append(args),
    )

    _plan, reused, is_existing = presentation_generation.enqueue_presentation_plan_generate(
        store,
        opportunity_id=opportunity["id"],
        user_id=USER_ID,
        framework_version_id=framework["id"],
        auto_continue=True,
    )
    continue_after_planning(store, planning_job_id=existing.id)

    refreshed = job_service.get_job(existing.id, repository=store)
    assert is_existing is True
    assert reused.id == existing.id
    assert refreshed is not None
    assert refreshed.status == JobStatus.COMPLETED
    assert refreshed.auto_continue is True
    assert len(_jobs(store, "presentation_planning")) == 1
    assert len(_jobs(store, "presentation_generation")) == 1
    assert len(dispatched) == 1


def test_worker_uses_durable_auto_continue_not_stale_complete_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, opportunity, framework = _store_with_confirmed_framework()
    plan_id = uuid4()
    planning_job = job_service.create_job(
        opportunity["id"],
        "presentation_planning",
        auto_continue=False,
        enqueue={
            "framework_version_id": str(framework["id"]),
            "user_id": str(USER_ID),
            "presentation_plan_id": str(plan_id),
        },
        repository=store,
    )
    monkeypatch.setattr("app.services.data.build_worker_data_store", lambda: store)
    monkeypatch.setattr(
        presentation_generation,
        "execute_presentation_planning",
        lambda current_store, **kwargs: _persist_plan(
            current_store,
            framework,
            plan_id=kwargs["presentation_plan_id"],
        ),
    )
    original_complete = job_service.complete_job

    def complete_with_stale_auto_continue_flag(job_id, **kwargs):
        completed = original_complete(job_id, **kwargs)
        job_service.update_job_auto_continue(job_id, True, repository=store)
        completed.auto_continue = False
        return completed

    monkeypatch.setattr(job_service, "complete_job", complete_with_stale_auto_continue_flag)
    dispatched: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        presentation_generation,
        "_dispatch_task",
        lambda _task, *args: dispatched.append(args),
    )

    from app.worker import run_presentation_planning_task

    run_presentation_planning_task.run(
        str(planning_job.id),
        str(framework["id"]),
        str(USER_ID),
        str(plan_id),
    )

    completed = job_service.get_job(planning_job.id, repository=store)
    assert completed is not None
    assert completed.status == JobStatus.COMPLETED
    assert completed.auto_continue is True
    assert len(_jobs(store, "presentation_generation")) == 1
    assert len(dispatched) == 1


def test_upgrade_of_already_completed_planning_job_starts_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, opportunity, framework = _store_with_confirmed_framework()
    plan = _persist_plan(store, framework)
    planning_job = _completed_planning_job(
        store,
        opportunity,
        framework,
        plan,
        auto_continue=False,
    )
    dispatched: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        presentation_generation,
        "_dispatch_task",
        lambda _task, *args: dispatched.append(args),
    )

    updated = presentation_generation._enable_auto_continue_on_reused_job(
        store,
        planning_job,
    )
    presentation_generation._enable_auto_continue_on_reused_job(store, updated)

    refreshed = job_service.get_job(planning_job.id, repository=store)
    assert refreshed is not None
    assert refreshed.auto_continue is True
    assert len(_jobs(store, "presentation_generation")) == 1
    assert len(dispatched) == 1
