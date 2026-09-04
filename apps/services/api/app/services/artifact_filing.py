"""Idempotent filing of generated artifacts into an enterprise repository.

The destination adapter is deliberately separate from Pitch Factory metadata:
SharePoint (or another approved repository) owns the bytes, while Pitch Factory
owns workflow, approval, provenance, status, and retry state.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from uuid import UUID


class EnterpriseArtifactStore(Protocol):
    def put(
        self,
        *,
        destination_path: str,
        content: bytes,
        content_type: str,
    ) -> str: ...


class FilingMetadataStore(Protocol):
    def get_filing_record(self, idempotency_key: str) -> dict[str, Any] | None: ...

    def save_filing_record(
        self,
        idempotency_key: str,
        record: dict[str, Any],
    ) -> dict[str, Any]: ...

    def list_filed_artifacts(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class ArtifactFilingRequest:
    opportunity_id: UUID
    presentation_id: UUID
    presentation_version_id: UUID
    artifact_kind: str
    source_path: Path
    content_type: str
    approved_by: UUID
    approved_at: datetime
    framework_version_id: UUID
    corpus_versions: tuple[str, ...] = ()
    provider: str = "internal"


class ArtifactFilingError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def filing_idempotency_key(request: ArtifactFilingRequest) -> str:
    identity = ":".join(
        (
            str(request.presentation_version_id),
            request.artifact_kind.strip().lower(),
            request.provider.strip().lower(),
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _safe_filename(request: ArtifactFilingRequest) -> str:
    suffix = request.source_path.suffix.lower()
    kind = "".join(
        character
        for character in request.artifact_kind.strip().lower()
        if character.isalnum() or character in {"-", "_"}
    )
    if not kind:
        raise ArtifactFilingError(
            "INVALID_ARTIFACT_KIND",
            "Artifact kind must contain a safe filename character",
            retryable=False,
        )
    return f"{kind}{suffix}"


def destination_path(request: ArtifactFilingRequest) -> str:
    path = PurePosixPath(
        "opportunities",
        str(request.opportunity_id),
        "presentations",
        str(request.presentation_id),
        "versions",
        str(request.presentation_version_id),
        _safe_filename(request),
    )
    return str(path)


def file_artifact(
    request: ArtifactFilingRequest,
    *,
    destination: EnterpriseArtifactStore,
    metadata: FilingMetadataStore,
) -> dict[str, Any]:
    """File once and retain enough metadata to audit or retry the operation."""
    key = filing_idempotency_key(request)
    existing = metadata.get_filing_record(key)
    if existing and existing.get("status") == "filed":
        return existing

    if not request.source_path.is_file():
        raise ArtifactFilingError(
            "ARTIFACT_NOT_FOUND",
            f"Artifact does not exist: {request.source_path}",
            retryable=False,
        )

    target = destination_path(request)
    base_record: dict[str, Any] = {
        "idempotency_key": key,
        "opportunity_id": str(request.opportunity_id),
        "presentation_id": str(request.presentation_id),
        "presentation_version_id": str(request.presentation_version_id),
        "framework_version_id": str(request.framework_version_id),
        "artifact_kind": request.artifact_kind,
        "content_type": request.content_type,
        "destination_path": target,
        "approved_by": str(request.approved_by),
        "approved_at": request.approved_at.astimezone(UTC).isoformat(),
        "corpus_versions": list(request.corpus_versions),
        "provider": request.provider,
    }

    metadata.save_filing_record(
        key,
        {**base_record, "status": "filing", "updated_at": datetime.now(UTC).isoformat()},
    )
    try:
        repository_ref = destination.put(
            destination_path=target,
            content=request.source_path.read_bytes(),
            content_type=request.content_type,
        )
    except Exception as exc:
        failed = {
            **base_record,
            "status": "failed",
            "error_code": getattr(exc, "code", "ENTERPRISE_REPOSITORY_UNAVAILABLE"),
            "error_retryable": bool(getattr(exc, "retryable", True)),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        metadata.save_filing_record(key, failed)
        raise ArtifactFilingError(
            str(failed["error_code"]),
            f"Enterprise filing failed: {exc}",
            retryable=bool(failed["error_retryable"]),
        ) from exc

    return metadata.save_filing_record(
        key,
        {
            **base_record,
            "status": "filed",
            "repository_ref": repository_ref,
            "filed_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )


class MemoryFilingMetadataStore:
    """Deterministic test/spike store; production uses durable database rows."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def get_filing_record(self, idempotency_key: str) -> dict[str, Any] | None:
        record = self.records.get(idempotency_key)
        return dict(record) if record else None

    def save_filing_record(
        self,
        idempotency_key: str,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        row = dict(record)
        row["idempotency_key"] = idempotency_key
        self.records[idempotency_key] = row
        return dict(row)

    def list_filed_artifacts(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        del user_id
        target = str(opportunity_id)
        return [
            dict(row)
            for row in self.records.values()
            if str(row.get("opportunity_id")) == target
        ]
