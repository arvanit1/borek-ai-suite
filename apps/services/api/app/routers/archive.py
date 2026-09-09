"""AT-61 owner-scoped in-app archive metadata and downloads."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.auth import get_current_user
from app.dependencies import AuthUserDep, DataStoreDep
from app.schemas.archive import ArchiveArtifactResponse
from app.services.api_errors import not_found
from app.services.artifact_filing import ArtifactFilingError
from app.services.enterprise_repository import build_enterprise_destination

router = APIRouter(dependencies=[Depends(get_current_user)])


def _public_row(row: dict) -> ArchiveArtifactResponse:
    artifact_id = UUID(str(row["id"]))
    backend = str(row.get("storage_backend") or "")
    downloadable = (
        row.get("status") == "filed"
        and backend in {"fixture", "in_app"}
        and bool(row.get("sha256"))
        and row.get("size_bytes") is not None
    )
    return ArchiveArtifactResponse.model_validate(
        {
            **row,
            "file_name": row.get("file_name") or f"presentation.{row['artifact_kind']}",
            "size_bytes": int(row.get("size_bytes") or 0),
            "sha256": str(row.get("sha256") or ""),
            "download_url": f"/archive/artifacts/{artifact_id}/download" if downloadable else None,
        }
    )


def _date_value(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


@router.get("/artifacts", response_model=list[ArchiveArtifactResponse])
def list_archive_artifacts(
    user: AuthUserDep,
    store: DataStoreDep,
    search: str | None = Query(default=None, max_length=200),
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[ArchiveArtifactResponse]:
    rows = store.list_user_filed_artifacts(user_id=user.id)
    needle = (search or "").strip().casefold()
    filtered = []
    for row in rows:
        filed_date = _date_value(row.get("filed_at") or row.get("approved_at"))
        searchable = f"{row.get('client_name', '')} {row.get('opportunity_name', '')}".casefold()
        if needle and needle not in searchable:
            continue
        if from_date and (filed_date is None or filed_date < from_date):
            continue
        if to_date and (filed_date is None or filed_date > to_date):
            continue
        filtered.append(_public_row(row))
    return filtered


@router.get("/artifacts/{artifact_id}", response_model=ArchiveArtifactResponse)
def get_archive_artifact(
    artifact_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> ArchiveArtifactResponse:
    return _public_row(store.get_user_filed_artifact(artifact_id=artifact_id, user_id=user.id))


@router.get("/artifacts/{artifact_id}/download")
def download_archive_artifact(
    artifact_id: UUID,
    user: AuthUserDep,
    store: DataStoreDep,
) -> Response:
    row = store.get_user_filed_artifact(artifact_id=artifact_id, user_id=user.id)
    if row.get("status") != "filed":
        raise not_found("FILED_ARTIFACT_NOT_FOUND", "The filed artifact is not available")
    backend = str(row.get("storage_backend") or "")
    if backend not in {"fixture", "in_app"}:
        raise not_found("FILED_ARTIFACT_NOT_FOUND", "The filed artifact is not available in-app")
    try:
        content = build_enterprise_destination(backend).get(
            destination_path=str(row["destination_path"])
        )
    except ArtifactFilingError as exc:
        raise not_found("FILED_ARTIFACT_NOT_FOUND", "The filed artifact is no longer available") from exc
    expected_size = row.get("size_bytes")
    expected_hash = str(row.get("sha256") or "")
    if expected_size is None or len(content) != int(expected_size):
        raise not_found("FILED_ARTIFACT_INTEGRITY_FAILED", "The filed artifact failed integrity checks")
    if not expected_hash or hashlib.sha256(content).hexdigest() != expected_hash:
        raise not_found("FILED_ARTIFACT_INTEGRITY_FAILED", "The filed artifact failed integrity checks")
    raw_name = Path(str(row.get("file_name") or f"presentation.{row['artifact_kind']}")).name
    safe_name = "".join(character for character in raw_name if ord(character) >= 32).replace('"', "")
    return Response(
        content=content,
        media_type=str(row["content_type"]),
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control": "private, no-store",
        },
    )
