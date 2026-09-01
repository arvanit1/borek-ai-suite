"""Celery worker application (AT-35)."""

from __future__ import annotations

from celery import Celery

from app.config import settings
from app.services.job_retry import run_with_transient_retry

celery_app = Celery(
    "borek_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_always_eager = settings.API_DATA_BACKEND == "memory"
celery_app.conf.task_eager_propagates = False


def _llm_observability_scope(store, job_id, opportunity_id=None):
    from services.observability.llm_logger import llm_observability_scope
    from app.services import job_service

    parsed_opportunity = opportunity_id
    if parsed_opportunity is None:
        job = job_service.get_job(job_id, repository=store)
        parsed_opportunity = job.opportunity_id if job is not None else None
    return llm_observability_scope(
        job_id=job_id,
        opportunity_id=parsed_opportunity,
        store=store,
    )


@celery_app.task(name="tasks.health_check")
def health_check_task() -> dict[str, str]:
    """Wiring test task — replaced by real jobs in AT-36+."""
    return {"status": "ok", "worker": "alive"}


@celery_app.task(name="tasks.advance_job_stage")
def advance_job_stage_task(job_id: str, next_stage: str) -> dict[str, str]:
    """Advance a generation job to the next pipeline stage (AT-36)."""
    from uuid import UUID

    from app.schemas.jobs import JobStage
    from app.services import job_service

    job = job_service.advance_stage(UUID(job_id), JobStage(next_stage))
    return {"job_id": str(job.id), "current_stage": job.current_stage.value}


@celery_app.task(name="tasks.run_presentation_planning")
def run_presentation_planning_task(
    job_id: str,
    framework_version_id: str,
    user_id: str,
    presentation_plan_id: str,
) -> dict[str, str]:
    from uuid import UUID

    from app.schemas.jobs import JobStage
    from app.services import job_service, presentation_generation
    from app.services.data import build_worker_data_store

    store = build_worker_data_store()
    parsed_job_id = UUID(job_id)
    stage = JobStage.PRESENTATION_PLANNING
    try:
        def _run() -> dict[str, str]:
            with _llm_observability_scope(store, parsed_job_id):
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                plan = presentation_generation.execute_presentation_planning(
                    store,
                    framework_version_id=UUID(framework_version_id),
                    user_id=UUID(user_id),
                    presentation_plan_id=UUID(presentation_plan_id),
                )
                job_service.complete_job(
                    parsed_job_id,
                    repository=store,
                    result_json={"presentation_plan_id": str(plan["id"])},
                )
                return {"job_id": job_id, "presentation_plan_id": str(plan["id"])}

        return run_with_transient_retry(_run)
    except Exception as exc:
        job_service.fail_job(
            parsed_job_id,
            getattr(exc, "code", "PRESENTATION_PLANNING_FAILED"),
            str(exc),
            stage,
            bool(getattr(exc, "retryable", True)),
            repository=store,
        )
        raise


@celery_app.task(name="tasks.run_framework_generation")
def run_framework_generation_task(
    job_id: str,
    opportunity_id: str,
    user_id: str,
    framework_version_id: str,
) -> dict[str, str]:
    from uuid import UUID

    from app.schemas.jobs import JobStage
    from app.services import framework_generation, job_service
    from app.services.data import build_worker_data_store

    store = build_worker_data_store()
    parsed_job_id = UUID(job_id)
    stage = JobStage.TRANSCRIPT_PROCESSING
    try:
        def _run() -> dict[str, str]:
            nonlocal stage
            with _llm_observability_scope(store, parsed_job_id, UUID(opportunity_id)):
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                stage = JobStage.KNOWLEDGE_EXTRACTING
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                stage = JobStage.FRAMEWORK_SYNTHESIZING
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                framework = framework_generation.execute_framework_generate(
                    store,
                    opportunity_id=UUID(opportunity_id),
                    user_id=UUID(user_id),
                    framework_version_id=UUID(framework_version_id),
                )
                stage = JobStage.FRAMEWORK_VALIDATING
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                loaded_job = job_service.get_job(parsed_job_id, repository=store)
                if loaded_job is None:
                    raise RuntimeError(f"Job not found: {job_id}")
                observability = framework_generation.persist_framework_generation_observability(
                    loaded_job,
                    framework_json=framework["framework_json"],
                    opportunity_id=UUID(opportunity_id),
                    framework_version_id=UUID(framework_version_id),
                )
                job_service.complete_job(
                    parsed_job_id,
                    repository=store,
                    result_json=observability,
                )
                return {"job_id": job_id, "framework_version_id": str(framework["id"])}

        return run_with_transient_retry(_run)
    except Exception as exc:
        job_service.fail_job(
            parsed_job_id,
            getattr(exc, "code", "FRAMEWORK_GENERATION_FAILED"),
            str(exc),
            stage,
            bool(getattr(exc, "retryable", True)),
            repository=store,
        )
        raise


@celery_app.task(name="tasks.run_framework_render")
def run_framework_render_task(
    job_id: str,
    framework_version_id: str,
    user_id: str,
) -> dict[str, str]:
    from uuid import UUID

    from app.schemas.jobs import JobStage
    from app.services import framework_generation, job_service
    from app.services.data import build_worker_data_store

    store = build_worker_data_store()
    parsed_job_id = UUID(job_id)
    stage = JobStage.PREVIEW_RENDERING
    try:
        def _run() -> dict[str, str]:
            job_service.ensure_stage(parsed_job_id, stage, repository=store)
            path = framework_generation.execute_framework_render(
                store,
                framework_version_id=UUID(framework_version_id),
                user_id=UUID(user_id),
            )
            job_service.record_metrics(
                parsed_job_id,
                repository=store,
                storage_size_bytes=path.stat().st_size,
            )
            job_service.complete_job(
                parsed_job_id,
                repository=store,
                result_json={
                    "framework_version_id": framework_version_id,
                    "pdf_download_url": (
                        f"/frameworks/{framework_version_id}/render?format=pdf"
                    ),
                },
            )
            return {"job_id": job_id, "framework_version_id": framework_version_id}

        return run_with_transient_retry(_run)
    except Exception as exc:
        job_service.fail_job(
            parsed_job_id,
            "FRAMEWORK_RENDER_FAILED",
            str(exc),
            stage,
            True,
            repository=store,
        )
        raise


@celery_app.task(name="tasks.run_framework_regenerate_chapter")
def run_framework_regenerate_chapter_task(
    job_id: str,
    framework_version_id: str,
    chapter_id: str,
) -> dict[str, str]:
    from uuid import UUID

    from app.schemas.jobs import JobStage
    from app.services import job_service
    from app.services.data import build_worker_data_store

    store = build_worker_data_store()
    parsed_job_id = UUID(job_id)
    stage = JobStage.TRANSCRIPT_PROCESSING
    try:
        def _run() -> dict[str, str]:
            nonlocal stage
            job_service.ensure_stage(parsed_job_id, stage, repository=store)
            stage = JobStage.KNOWLEDGE_EXTRACTING
            job_service.ensure_stage(parsed_job_id, stage, repository=store)
            stage = JobStage.FRAMEWORK_SYNTHESIZING
            job_service.ensure_stage(parsed_job_id, stage, repository=store)
            stage = JobStage.FRAMEWORK_VALIDATING
            job_service.ensure_stage(parsed_job_id, stage, repository=store)
            job_service.complete_job(
                parsed_job_id,
                repository=store,
                result_json={
                    "framework_version_id": framework_version_id,
                    "chapter_id": chapter_id,
                },
            )
            return {
                "job_id": job_id,
                "framework_version_id": framework_version_id,
                "chapter_id": chapter_id,
            }

        return run_with_transient_retry(_run)
    except Exception as exc:
        job_service.fail_job(
            parsed_job_id,
            getattr(exc, "code", "FRAMEWORK_REGENERATE_FAILED"),
            str(exc),
            stage,
            bool(getattr(exc, "retryable", True)),
            repository=store,
        )
        raise


@celery_app.task(name="tasks.run_presentation_generation")
def run_presentation_generation_task(
    job_id: str,
    presentation_id: str,
    user_id: str,
) -> dict[str, str]:
    from uuid import UUID
    from time import monotonic

    from app.schemas.jobs import JobStage
    from app.services import job_service, presentation_generation
    from app.services.data import build_worker_data_store

    store = build_worker_data_store()
    parsed_job_id = UUID(job_id)
    stage = JobStage.SLIDE_GENERATING
    try:
        def _run() -> dict[str, str]:
            nonlocal stage
            with _llm_observability_scope(store, parsed_job_id):
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                version, plan = presentation_generation.execute_presentation_generation(
                    store,
                    presentation_id=UUID(presentation_id),
                    user_id=UUID(user_id),
                )
                stage = JobStage.SLIDE_VALIDATING
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                stage = JobStage.PPTX_RENDERING
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                render_started = monotonic()
                version = presentation_generation.render_presentation_version(
                    store,
                    version=version,
                    plan=plan,
                )
                job_service.record_metrics(
                    parsed_job_id,
                    repository=store,
                    render_duration_ms=int((monotonic() - render_started) * 1000),
                    storage_size_bytes=int(version.get("storage_size_bytes") or 0),
                )
                stage = JobStage.PREVIEW_RENDERING
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                job_service.complete_job(
                    parsed_job_id,
                    repository=store,
                    result_json={
                        "presentation_id": presentation_id,
                        "presentation_version_id": str(version["id"]),
                    },
                )
                return {
                    "job_id": job_id,
                    "presentation_id": presentation_id,
                    "presentation_version_id": str(version["id"]),
                }

        return run_with_transient_retry(_run)
    except Exception as exc:
        job_service.fail_job(
            parsed_job_id,
            getattr(exc, "code", "PRESENTATION_GENERATION_FAILED"),
            str(exc),
            stage,
            bool(getattr(exc, "retryable", True)),
            repository=store,
        )
        raise


def _run_slide_task(
    *,
    job_id: str,
    presentation_id: str,
    slide_id: str,
    user_id: str,
    layout_id: str | None,
) -> dict[str, str]:
    from uuid import UUID

    from app.schemas.jobs import JobStage
    from app.services import job_service, presentation_generation
    from app.services.data import build_worker_data_store

    store = build_worker_data_store()
    parsed_job_id = UUID(job_id)
    stage = JobStage.SLIDE_GENERATING
    try:
        def _run() -> dict[str, str]:
            nonlocal stage
            with _llm_observability_scope(store, parsed_job_id):
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                if layout_id is None:
                    slide = presentation_generation.execute_slide_regenerate(
                        store,
                        presentation_id=UUID(presentation_id),
                        slide_id=UUID(slide_id),
                        user_id=UUID(user_id),
                    )
                else:
                    slide = presentation_generation.execute_slide_change_layout(
                        store,
                        presentation_id=UUID(presentation_id),
                        slide_id=UUID(slide_id),
                        user_id=UUID(user_id),
                        layout_id=layout_id,
                    )
                stage = JobStage.SLIDE_VALIDATING
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                version = store.get_latest_presentation_version(
                    presentation_id=UUID(presentation_id),
                    user_id=UUID(user_id),
                )
                presentation = store.get_presentation(
                    presentation_id=UUID(presentation_id),
                    user_id=UUID(user_id),
                )
                plan = store.get_presentation_plan(
                    presentation_plan_id=presentation["presentation_plan_id"],
                    user_id=UUID(user_id),
                )
                stage = JobStage.PPTX_RENDERING
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                version = presentation_generation.render_presentation_version(
                    store,
                    version=version,
                    plan=plan,
                )
                stage = JobStage.PREVIEW_RENDERING
                job_service.ensure_stage(parsed_job_id, stage, repository=store)
                job_service.complete_job(
                    parsed_job_id,
                    repository=store,
                    result_json={
                        "presentation_id": presentation_id,
                        "presentation_version_id": str(version["id"]),
                        "slide_id": str(slide["id"]),
                    },
                )
                return {"job_id": job_id, "slide_id": str(slide["id"])}

        return run_with_transient_retry(_run)
    except Exception as exc:
        job_service.fail_job(
            parsed_job_id,
            getattr(exc, "code", "SLIDE_GENERATION_FAILED"),
            str(exc),
            stage,
            bool(getattr(exc, "retryable", True)),
            repository=store,
        )
        raise


@celery_app.task(name="tasks.run_slide_regenerate")
def run_slide_regenerate_task(
    job_id: str,
    presentation_id: str,
    slide_id: str,
    user_id: str,
) -> dict[str, str]:
    return _run_slide_task(
        job_id=job_id,
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user_id,
        layout_id=None,
    )


@celery_app.task(name="tasks.run_slide_change_layout")
def run_slide_change_layout_task(
    job_id: str,
    presentation_id: str,
    slide_id: str,
    user_id: str,
    layout_id: str,
) -> dict[str, str]:
    return _run_slide_task(
        job_id=job_id,
        presentation_id=presentation_id,
        slide_id=slide_id,
        user_id=user_id,
        layout_id=layout_id,
    )
