"""AT-61: file every generated artifact after a successful render."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.config import settings
from app.services.artifact_filing import ArtifactFilingError, ArtifactFilingRequest, file_artifact
from app.services.deck_assets import deck_assets_root
from app.services.enterprise_repository import build_enterprise_destination
from app.services.knowledge_access import describe_active_corpus

_PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_PDF_TYPE = "application/pdf"


def _as_uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _as_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if str(value).strip() else None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def resolve_approval_metadata(framework: dict[str, Any], *, user_id: UUID) -> tuple[UUID, datetime]:
    payload = framework.get("framework_json") or {}
    raw_by = payload.get("confirmed_by") or framework.get("confirmed_by")
    raw_at = payload.get("confirmed_at") or framework.get("confirmed_at")
    approved_by = _as_uuid(raw_by) if raw_by else user_id
    approved_at = _parse_datetime(raw_at) or datetime.now(UTC)
    return approved_by, approved_at


def corpus_version_labels(store: Any) -> tuple[str, ...]:
    meta = describe_active_corpus(store)
    key = str(meta.get("corpus_key") or "").strip()
    version = str(meta.get("version") or "").strip()
    if not key or not version:
        return ()
    return (f"{key}@{version}",)


def collect_artifact_candidates(
    version: dict[str, Any],
    gamma_result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    pptx_path = _as_path(version.get("pptx_storage_path"))
    if pptx_path is not None:
        candidates.append(
            {
                "kind": "pptx",
                "path": pptx_path,
                "content_type": _PPTX_TYPE,
                "provider": "internal",
            }
        )
    pdf_path = _as_path(version.get("pdf_storage_path"))
    if pdf_path is not None:
        candidates.append(
            {
                "kind": "pdf",
                "path": pdf_path,
                "content_type": _PDF_TYPE,
                "provider": "internal",
            }
        )
    for artifact in (gamma_result or {}).get("artifacts") or []:
        storage_key = str(artifact.get("storage_key") or "").strip()
        if not storage_key:
            continue
        fmt = str(artifact.get("format") or "pptx").strip().lower()
        configured = Path(settings.ARTIFACT_ROOT).joinpath(*Path(storage_key).parts)
        owned = deck_assets_root().joinpath(*Path(storage_key).parts)
        candidates.append(
            {
                "kind": fmt,
                "path": configured if configured.is_file() or configured.is_absolute() else owned,
                "content_type": str(artifact.get("content_type") or _PPTX_TYPE),
                "provider": "gamma",
            }
        )
    return candidates


def _expected_artifacts_missing(
    version: dict[str, Any],
    gamma_result: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
) -> bool:
    if settings.RENDERER_EXECUTION_MODE == "live" and (
        version.get("pptx_storage_path") or version.get("pdf_storage_path")
    ):
        internal = [item for item in candidates if item["provider"] == "internal"]
        return bool(internal) and not all(item["path"].is_file() for item in internal)
    if gamma_result and not gamma_result.get("skipped") and gamma_result.get("artifacts"):
        gamma = [item for item in candidates if item["provider"] == "gamma"]
        return bool(gamma) and not all(item["path"].is_file() for item in gamma)
    return False


def run_artifact_filing_for_presentation(
    store: Any,
    *,
    presentation_id: UUID | str,
    user_id: UUID | str,
    version: dict[str, Any],
    gamma_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """File produced PPTX/PDF/Gamma bytes. No-ops when fixture generate produced no files."""
    candidates = collect_artifact_candidates(version, gamma_result)
    existing = [item for item in candidates if item["path"].is_file()]
    if not existing:
        if _expected_artifacts_missing(version, gamma_result, candidates):
            raise ArtifactFilingError(
                "ARTIFACT_NOT_FOUND",
                "Generated artifacts were expected but are not on disk",
                retryable=False,
            )
        return {"skipped": True, "reason": "no_generated_artifacts", "filed": []}

    parsed_user = _as_uuid(user_id)
    parsed_presentation = _as_uuid(presentation_id)
    opportunity_id = store.get_presentation_opportunity_id(
        presentation_id=parsed_presentation,
        user_id=parsed_user,
    )
    presentation = store.get_presentation(
        presentation_id=parsed_presentation,
        user_id=parsed_user,
    )
    plan = store.get_presentation_plan(
        presentation_plan_id=presentation["presentation_plan_id"],
        user_id=parsed_user,
    )
    framework = store.get_framework_version(
        framework_version_id=plan["framework_version_id"],
        user_id=parsed_user,
    )
    approved_by, approved_at = resolve_approval_metadata(framework, user_id=parsed_user)
    corpus_versions = corpus_version_labels(store)
    destination = build_enterprise_destination()
    records: list[dict[str, Any]] = []
    for item in existing:
        records.append(
            file_artifact(
                ArtifactFilingRequest(
                    opportunity_id=_as_uuid(opportunity_id),
                    presentation_id=parsed_presentation,
                    presentation_version_id=_as_uuid(version["id"]),
                    artifact_kind=item["kind"],
                    source_path=item["path"],
                    content_type=item["content_type"],
                    approved_by=approved_by,
                    approved_at=approved_at,
                    framework_version_id=_as_uuid(framework["id"]),
                    corpus_versions=corpus_versions,
                    provider=item["provider"],
                ),
                destination=destination,
                metadata=store,
            )
        )
    return {
        "skipped": False,
        "destination": settings.FILING_DESTINATION,
        "filed": records,
    }
