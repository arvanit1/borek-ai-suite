"""AT-35: Celery configuration unit tests (no live Redis)."""

from __future__ import annotations

from app.config import settings
from app.worker import celery_app, health_check_task


def test_celery_broker_url_matches_settings() -> None:
    assert celery_app.conf.broker_url == settings.REDIS_URL


def test_celery_result_backend_matches_settings() -> None:
    assert celery_app.conf.result_backend == settings.REDIS_URL


def test_celery_json_serializers() -> None:
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]


def test_health_check_task_is_registered() -> None:
    assert "tasks.health_check" in celery_app.tasks
    assert health_check_task.name == "tasks.health_check"


def test_advance_job_stage_task_is_registered() -> None:
    assert "tasks.advance_job_stage" in celery_app.tasks


def test_generation_execution_tasks_are_registered() -> None:
    for task_name in (
        "tasks.run_framework_generation",
        "tasks.run_framework_render",
        "tasks.run_presentation_planning",
        "tasks.run_presentation_generation",
        "tasks.run_slide_regenerate",
        "tasks.run_slide_change_layout",
    ):
        assert task_name in celery_app.tasks
