"""Supabase PostgREST data access with caller JWT for RLS (AT-40 / AT-41)."""

from __future__ import annotations

import copy
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from app.config import settings
from app.services.api_errors import bad_request, conflict, not_found, service_unavailable
from app.services.data.memory_store import ALLOWED_TRANSCRIPT_EXTENSIONS
from app.services.stage_b_orchestration import (
    build_slide_spec_for_planned_slide,
    plan_json_from_confirmed_framework,
    planned_slides_with_generators,
)
from app.services.deck_assets import (
    materialize_fixture_deck_assets,
    resolve_pdf_path,
    resolve_pptx_path,
    resolve_preview_image_path,
)
from app.services.framework_status import require_reviewable_framework
from app.services.framework_stub_template import load_framework_stub_template

logger = logging.getLogger(__name__)
_HTTP_CLIENT: httpx.Client | None = None
_TRANSIENT_ERRORS = (httpx.TimeoutException, httpx.NetworkError)
_MAX_ATTEMPTS = 3

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[6]
    / "packages"
    / "contracts"
    / "fixtures"
    / "framework_object.minimal.json"
)


def _shared_client() -> httpx.Client:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None or _HTTP_CLIENT.is_closed:
        _HTTP_CLIENT = httpx.Client(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _HTTP_CLIENT


def _request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str] | None = None,
    json: dict[str, Any] | list[dict[str, Any]] | None = None,
    content: bytes | None = None,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            kwargs: dict[str, Any] = {
                "method": method,
                "url": url,
                "headers": headers,
                "params": params,
            }
            if content is not None:
                kwargs["content"] = content
            elif json is not None:
                kwargs["json"] = json
            return _shared_client().request(**kwargs)
        except _TRANSIENT_ERRORS as exc:
            last_error = exc
            logger.warning(
                "Supabase request %s %s failed (attempt %s/%s): %s",
                method,
                url,
                attempt + 1,
                _MAX_ATTEMPTS,
                exc,
            )
            if attempt + 1 < _MAX_ATTEMPTS:
                time.sleep(0.4 * (attempt + 1))
    raise service_unavailable(
        "SUPABASE_UNAVAILABLE",
        "Supabase timed out. Retry the action.",
    ) from last_error


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _normalize_opportunity(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": UUID(str(row["id"])),
        "created_by": UUID(str(row["created_by"])),
        "created_at": _parse_timestamp(row["created_at"]),
        "updated_at": _parse_timestamp(row["updated_at"]),
    }


def _normalize_transcript(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": UUID(str(row["id"])),
        "opportunity_id": UUID(str(row["opportunity_id"])),
        "created_at": _parse_timestamp(row["created_at"]),
    }


def _normalize_framework(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": UUID(str(row["id"])),
        "opportunity_id": UUID(str(row["opportunity_id"])),
        "created_by": UUID(str(row["created_by"])),
        "created_at": _parse_timestamp(row["created_at"]),
    }


def _normalize_presentation_plan(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": UUID(str(row["id"])),
        "framework_version_id": UUID(str(row["framework_version_id"])),
        "created_at": _parse_timestamp(row["created_at"]),
    }


def _normalize_presentation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": UUID(str(row["id"])),
        "presentation_plan_id": UUID(str(row["presentation_plan_id"])),
        "created_at": _parse_timestamp(row["created_at"]),
    }


def _normalize_presentation_version(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": UUID(str(row["id"])),
        "presentation_id": UUID(str(row["presentation_id"])),
        "created_at": _parse_timestamp(row["created_at"]),
    }


def _normalize_slide(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": UUID(str(row["id"])),
        "presentation_version_id": UUID(str(row["presentation_version_id"])),
        "created_at": _parse_timestamp(row["created_at"]),
    }


def _normalize_generation_job(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        **row,
        "id": UUID(str(row["id"])),
        "opportunity_id": UUID(str(row["opportunity_id"])),
        "presentation_id": (
            UUID(str(row["presentation_id"])) if row.get("presentation_id") else None
        ),
    }
    for field in ("started_at", "completed_at", "created_at"):
        if normalized.get(field):
            normalized[field] = _parse_timestamp(normalized[field])
    return normalized


class SupabaseDataStore:
    """PostgREST client scoped to the authenticated user's access token."""

    def __init__(self, access_token: str) -> None:
        self._base_url = settings.SUPABASE_URL.rstrip("/")
        api_key = (
            settings.SUPABASE_SERVICE_ROLE_KEY
            if access_token == settings.SUPABASE_SERVICE_ROLE_KEY
            else settings.SUPABASE_ANON_KEY
        )
        self._headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def create_generation_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = copy.deepcopy(payload)
        for key, value in list(body.items()):
            if isinstance(value, (UUID, datetime)):
                body[key] = value.isoformat() if isinstance(value, datetime) else str(value)
        response = self._request("POST", "generation_jobs", json_body=body)
        if response.status_code not in (200, 201):
            raise bad_request("JOB_CREATE_FAILED", response.text)
        return _normalize_generation_job(response.json()[0])

    def get_generation_job(self, job_id: UUID) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            "generation_jobs",
            params={"id": f"eq.{job_id}", "select": "*", "limit": "1"},
        )
        if response.status_code != 200:
            raise bad_request("JOB_READ_FAILED", response.text)
        rows = response.json()
        return _normalize_generation_job(rows[0]) if rows else None

    def update_generation_job(
        self,
        job_id: UUID,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        body = copy.deepcopy(updates)
        for key, value in list(body.items()):
            if isinstance(value, (UUID, datetime)):
                body[key] = value.isoformat() if isinstance(value, datetime) else str(value)
        response = self._request(
            "PATCH",
            "generation_jobs",
            params={"id": f"eq.{job_id}"},
            json_body=body,
        )
        if response.status_code != 200 or not response.json():
            raise not_found("JOB_NOT_FOUND", f"No job found with id {job_id}")
        return _normalize_generation_job(response.json()[0])

    def _request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> httpx.Response:
        return _request_with_retry(
            method,
            f"{self._base_url}/rest/v1/{table}",
            headers=self._headers,
            params=params,
            json=json_body,
        )

    def _upload_transcript_content(
        self,
        *,
        storage_path: str,
        mime_type: str,
        content: bytes,
    ) -> None:
        headers = {
            "apikey": self._headers["apikey"],
            "Authorization": self._headers["Authorization"],
            "Content-Type": mime_type,
            "x-upsert": "false",
        }
        response = _request_with_retry(
            "POST",
            f"{self._base_url}/storage/v1/object/transcripts/{storage_path}",
            headers=headers,
            content=content,
        )
        if response.status_code not in (200, 201):
            raise bad_request("TRANSCRIPT_STORAGE_FAILED", response.text)

    def create_opportunity(
        self,
        *,
        user_id: UUID,
        client_name: str,
        opportunity_name: str,
        department: str,
        language: str,
    ) -> dict[str, Any]:
        payload = {
            "client_name": client_name,
            "opportunity_name": opportunity_name,
            "department": department,
            "language": language,
            "status": "active",
            "created_by": str(user_id),
        }
        response = self._request("POST", "opportunities", json_body=payload)
        if response.status_code not in (200, 201):
            raise bad_request("OPPORTUNITY_CREATE_FAILED", response.text)
        row = response.json()[0]
        return _normalize_opportunity(row)

    def list_opportunities(self, *, user_id: UUID) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "opportunities",
            params={
                "select": "*",
                "created_by": f"eq.{user_id}",
                "order": "created_at.desc",
            },
        )
        if response.status_code != 200:
            raise bad_request("OPPORTUNITY_LIST_FAILED", response.text)
        return [_normalize_opportunity(row) for row in response.json()]

    def get_opportunity(self, *, opportunity_id: UUID, user_id: UUID) -> dict[str, Any]:
        response = self._request(
            "GET",
            "opportunities",
            params={
                "select": "*",
                "id": f"eq.{opportunity_id}",
                "created_by": f"eq.{user_id}",
                "limit": "1",
            },
        )
        if response.status_code != 200 or not response.json():
            raise not_found("OPPORTUNITY_NOT_FOUND", f"Opportunity {opportunity_id} was not found")
        return _normalize_opportunity(response.json()[0])

    def update_opportunity(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {key: value for key, value in updates.items() if value is not None}
        payload["updated_at"] = datetime.now(UTC).isoformat()
        response = self._request(
            "PATCH",
            "opportunities",
            params={
                "id": f"eq.{opportunity_id}",
                "created_by": f"eq.{user_id}",
            },
            json_body=payload,
        )
        if response.status_code not in (200, 204) or not response.json():
            raise not_found("OPPORTUNITY_NOT_FOUND", f"Opportunity {opportunity_id} was not found")
        return _normalize_opportunity(response.json()[0])

    def create_transcript(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
        file_name: str,
        mime_type: str,
        storage_path: str,
        conversation_id: str,
        content: bytes,
        sections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _ = user_id
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        self._upload_transcript_content(
            storage_path=storage_path,
            mime_type=mime_type,
            content=content,
        )
        payload = {
            "opportunity_id": str(opportunity_id),
            "file_name": file_name,
            "mime_type": mime_type,
            "storage_path": storage_path,
            "conversation_id": conversation_id,
            "processing_status": "pending",
        }
        response = self._request("POST", "transcripts", json_body=payload)
        if response.status_code not in (200, 201):
            raise bad_request("TRANSCRIPT_UPLOAD_FAILED", response.text)
        transcript = _normalize_transcript(response.json()[0])
        section_payloads = [
            {
                "transcript_id": str(transcript["id"]),
                "section_index": int(section["section_index"]),
                "speaker_role": section.get("speaker_role"),
                "content": str(section["content"]),
                "metadata": copy.deepcopy(section.get("metadata") or {}),
            }
            for section in sections
        ]
        section_response = self._request(
            "POST",
            "transcript_sections",
            json_body=section_payloads,
        )
        if section_response.status_code not in (200, 201):
            raise bad_request("TRANSCRIPT_SECTIONS_CREATE_FAILED", section_response.text)
        return transcript

    def list_transcripts(self, *, opportunity_id: UUID, user_id: UUID) -> list[dict[str, Any]]:
        _ = user_id
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        response = self._request(
            "GET",
            "transcripts",
            params={
                "select": "*",
                "opportunity_id": f"eq.{opportunity_id}",
                "order": "created_at.asc",
            },
        )
        if response.status_code != 200:
            raise bad_request("TRANSCRIPT_LIST_FAILED", response.text)
        return [_normalize_transcript(row) for row in response.json()]

    def list_transcript_sources(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return persisted speaker turns for Stage A under caller RLS."""
        transcripts = self.list_transcripts(
            opportunity_id=opportunity_id,
            user_id=user_id,
        )
        sources: list[dict[str, Any]] = []
        for transcript in transcripts:
            response = self._request(
                "GET",
                "transcript_sections",
                params={
                    "select": "section_index,speaker_role,content,metadata",
                    "transcript_id": f"eq.{transcript['id']}",
                    "order": "section_index.asc",
                },
            )
            if response.status_code != 200:
                raise bad_request("TRANSCRIPT_SECTIONS_LIST_FAILED", response.text)
            sources.append(
                {
                    "id": transcript["id"],
                    "file_name": transcript["file_name"],
                    "conversation_id": transcript["conversation_id"],
                    "sections": response.json(),
                }
            )
        return sources

    def update_transcript_processing_status(
        self,
        *,
        opportunity_id: UUID,
        transcript_id: UUID,
        user_id: UUID,
        processing_status: str,
    ) -> None:
        self.get_transcript(
            opportunity_id=opportunity_id,
            transcript_id=transcript_id,
            user_id=user_id,
        )
        response = self._request(
            "PATCH",
            "transcripts",
            params={"id": f"eq.{transcript_id}"},
            json_body={"processing_status": processing_status},
        )
        if response.status_code not in (200, 204):
            raise bad_request("TRANSCRIPT_STATUS_UPDATE_FAILED", response.text)

    def get_transcript(
        self,
        *,
        opportunity_id: UUID,
        transcript_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        _ = user_id
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        response = self._request(
            "GET",
            "transcripts",
            params={
                "select": "*",
                "id": f"eq.{transcript_id}",
                "opportunity_id": f"eq.{opportunity_id}",
                "limit": "1",
            },
        )
        if response.status_code != 200 or not response.json():
            raise not_found("TRANSCRIPT_NOT_FOUND", f"Transcript {transcript_id} was not found")
        return _normalize_transcript(response.json()[0])

    def regenerate_transcript(
        self,
        *,
        opportunity_id: UUID,
        transcript_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        _ = user_id
        self.get_transcript(
            opportunity_id=opportunity_id,
            transcript_id=transcript_id,
            user_id=user_id,
        )
        response = self._request(
            "PATCH",
            "transcripts",
            params={"id": f"eq.{transcript_id}"},
            json_body={"processing_status": "pending"},
        )
        if response.status_code not in (200, 204) or not response.json():
            raise not_found("TRANSCRIPT_NOT_FOUND", f"Transcript {transcript_id} was not found")
        return _normalize_transcript(response.json()[0])

    def create_framework_version(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
        framework_json: dict[str, Any],
        status: str = "draft",
        framework_version_id: UUID | None = None,
    ) -> dict[str, Any]:
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        latest = self._request(
            "GET",
            "framework_versions",
            params={
                "select": "version_number",
                "opportunity_id": f"eq.{opportunity_id}",
                "order": "version_number.desc",
                "limit": "1",
            },
        )
        version_number = 1
        if latest.status_code == 200 and latest.json():
            version_number = int(latest.json()[0]["version_number"]) + 1

        payload = {
            "opportunity_id": str(opportunity_id),
            "version_number": version_number,
            "status": status,
            "framework_json": framework_json,
            "created_by": str(user_id),
        }
        if framework_version_id is not None:
            payload["id"] = str(framework_version_id)
        response = self._request("POST", "framework_versions", json_body=payload)
        if response.status_code not in (200, 201):
            raise bad_request("FRAMEWORK_CREATE_FAILED", response.text)
        return _normalize_framework(response.json()[0])

    def get_latest_framework(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        _ = user_id
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        response = self._request(
            "GET",
            "framework_versions",
            params={
                "select": "*",
                "opportunity_id": f"eq.{opportunity_id}",
                "order": "version_number.desc",
                "limit": "1",
            },
        )
        if response.status_code != 200 or not response.json():
            raise not_found(
                "FRAMEWORK_NOT_FOUND",
                f"No framework version exists for opportunity {opportunity_id}",
            )
        return _normalize_framework(response.json()[0])

    def get_framework_version(
        self,
        *,
        framework_version_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        response = self._request(
            "GET",
            "framework_versions",
            params={"select": "*", "id": f"eq.{framework_version_id}", "limit": "1"},
        )
        if response.status_code != 200 or not response.json():
            raise not_found(
                "FRAMEWORK_NOT_FOUND",
                f"Framework version {framework_version_id} was not found",
            )
        row = _normalize_framework(response.json()[0])
        self.get_opportunity(opportunity_id=row["opportunity_id"], user_id=user_id)
        return row

    def update_latest_framework(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
        framework_json: dict[str, Any],
    ) -> dict[str, Any]:
        row = self.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)
        require_reviewable_framework(row["status"], action="edit")

        updated = copy.deepcopy(framework_json)
        updated["opportunity_id"] = str(opportunity_id)
        updated["updated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        change_log = updated.setdefault("change_log", [])
        change_log.append("Manual edit via framework review UI")

        response = self._request(
            "PATCH",
            "framework_versions",
            params={"id": f"eq.{row['id']}"},
            json_body={"framework_json": updated},
        )
        if response.status_code not in (200, 204) or not response.json():
            raise bad_request("FRAMEWORK_UPDATE_FAILED", response.text)
        return _normalize_framework(response.json()[0])

    def confirm_framework(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
        framework_version_id: UUID | None,
        confirmed_framework_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if framework_version_id is not None:
            row = self.get_framework_version(
                framework_version_id=framework_version_id,
                user_id=user_id,
            )
            if row["opportunity_id"] != opportunity_id:
                raise not_found(
                    "FRAMEWORK_NOT_FOUND",
                    f"Framework version {framework_version_id} was not found",
                )
        else:
            row = self.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)

        require_reviewable_framework(row["status"], action="confirm")

        framework_json = copy.deepcopy(
            confirmed_framework_json if confirmed_framework_json is not None else row["framework_json"]
        )
        framework_json["status"] = "confirmed"
        response = self._request(
            "PATCH",
            "framework_versions",
            params={"id": f"eq.{row['id']}"},
            json_body={"status": "confirmed", "framework_json": framework_json},
        )
        if response.status_code not in (200, 204) or not response.json():
            raise bad_request("FRAMEWORK_CONFIRM_FAILED", response.text)
        return _normalize_framework(response.json()[0])

    def regenerate_chapter(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
        chapter_id: str,
    ) -> dict[str, Any]:
        row = self.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)
        require_reviewable_framework(row["status"], action="regenerate")

        framework_json = copy.deepcopy(row["framework_json"])
        chapters = framework_json.get("chapters", [])
        if not any(str(chapter.get("chapter_id")) == chapter_id for chapter in chapters):
            raise bad_request("INVALID_CHAPTER_ID", f"Chapter {chapter_id} was not found")

        change_log = framework_json.setdefault("change_log", [])
        change_log.append(f"Regenerated chapter {chapter_id}")
        response = self._request(
            "PATCH",
            "framework_versions",
            params={"id": f"eq.{row['id']}"},
            json_body={"framework_json": framework_json},
        )
        if response.status_code not in (200, 204) or not response.json():
            raise bad_request("FRAMEWORK_REGENERATE_FAILED", response.text)
        return _normalize_framework(response.json()[0])

    def generate_framework_stub(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        payload = load_framework_stub_template(opportunity_id)
        return self.create_framework_version(
            opportunity_id=opportunity_id,
            user_id=user_id,
            framework_json=payload,
            status="draft",
        )

    def create_presentation_plan(
        self,
        *,
        framework_version_id: UUID,
        user_id: UUID,
        plan_json: dict[str, Any],
        presentation_plan_id: UUID | None = None,
    ) -> dict[str, Any]:
        framework = self.get_framework_version(
            framework_version_id=framework_version_id,
            user_id=user_id,
        )
        if framework["status"] != "confirmed":
            raise bad_request(
                "FRAMEWORK_NOT_CONFIRMED",
                "Framework must be confirmed before creating a presentation plan",
            )
        payload = {
            "framework_version_id": str(framework_version_id),
            "plan_json": plan_json,
        }
        if presentation_plan_id is not None:
            payload["id"] = str(presentation_plan_id)
        response = self._request("POST", "presentation_plans", json_body=payload)
        if response.status_code not in (200, 201):
            raise bad_request("PRESENTATION_PLAN_CREATE_FAILED", response.text)
        return _normalize_presentation_plan(response.json()[0])

    def get_presentation_plan(
        self,
        *,
        presentation_plan_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        response = self._request(
            "GET",
            "presentation_plans",
            params={"select": "*", "id": f"eq.{presentation_plan_id}", "limit": "1"},
        )
        if response.status_code != 200 or not response.json():
            raise not_found(
                "PRESENTATION_PLAN_NOT_FOUND",
                f"Presentation plan {presentation_plan_id} was not found",
            )
        row = _normalize_presentation_plan(response.json()[0])
        self.get_framework_version(
            framework_version_id=row["framework_version_id"],
            user_id=user_id,
        )
        return row

    def get_latest_presentation_plan(
        self,
        *,
        framework_version_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any] | None:
        _ = user_id
        self.get_framework_version(
            framework_version_id=framework_version_id,
            user_id=user_id,
        )
        response = self._request(
            "GET",
            "presentation_plans",
            params={
                "select": "*",
                "framework_version_id": f"eq.{framework_version_id}",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        if response.status_code != 200 or not response.json():
            return None
        return _normalize_presentation_plan(response.json()[0])

    def get_latest_presentation_plan_for_opportunity(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        framework = self.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)
        plan = self.get_latest_presentation_plan(
            framework_version_id=framework["id"],
            user_id=user_id,
        )
        if plan is None:
            raise not_found(
                "PRESENTATION_PLAN_NOT_FOUND",
                f"No presentation plan exists for opportunity {opportunity_id}",
            )
        return plan

    def generate_presentation_plan(
        self,
        *,
        framework_version_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        framework = self.get_framework_version(
            framework_version_id=framework_version_id,
            user_id=user_id,
        )
        return self.create_presentation_plan(
            framework_version_id=framework_version_id,
            user_id=user_id,
            plan_json=plan_json_from_confirmed_framework(framework["framework_json"]),
        )

    def create_presentation(
        self,
        *,
        presentation_plan_id: UUID,
        user_id: UUID,
        name: str,
    ) -> dict[str, Any]:
        _ = user_id
        self.get_presentation_plan(
            presentation_plan_id=presentation_plan_id,
            user_id=user_id,
        )
        payload = {
            "presentation_plan_id": str(presentation_plan_id),
            "name": name,
            "status": "draft",
        }
        response = self._request("POST", "presentations", json_body=payload)
        if response.status_code not in (200, 201):
            raise bad_request("PRESENTATION_CREATE_FAILED", response.text)
        return _normalize_presentation(response.json()[0])

    def list_presentations(self, *, user_id: UUID) -> list[dict[str, Any]]:
        _ = user_id
        response = self._request(
            "GET",
            "presentations",
            params={"select": "*", "order": "created_at.desc"},
        )
        if response.status_code != 200:
            raise bad_request("PRESENTATION_LIST_FAILED", response.text)
        return [_normalize_presentation(row) for row in response.json()]

    def get_presentation(
        self,
        *,
        presentation_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        response = self._request(
            "GET",
            "presentations",
            params={"select": "*", "id": f"eq.{presentation_id}", "limit": "1"},
        )
        if response.status_code != 200 or not response.json():
            raise not_found(
                "PRESENTATION_NOT_FOUND",
                f"Presentation {presentation_id} was not found",
            )
        row = _normalize_presentation(response.json()[0])
        self.get_presentation_plan(
            presentation_plan_id=row["presentation_plan_id"],
            user_id=user_id,
        )
        return row

    def get_presentation_opportunity_id(
        self,
        *,
        presentation_id: UUID,
        user_id: UUID,
    ) -> UUID:
        presentation = self.get_presentation(presentation_id=presentation_id, user_id=user_id)
        plan = self.get_presentation_plan(
            presentation_plan_id=presentation["presentation_plan_id"],
            user_id=user_id,
        )
        framework = self.get_framework_version(
            framework_version_id=plan["framework_version_id"],
            user_id=user_id,
        )
        return framework["opportunity_id"]

    def create_presentation_version_with_slides(
        self,
        *,
        presentation_id: UUID,
        user_id: UUID,
        plan_json: dict[str, Any],
    ) -> dict[str, Any]:
        self.get_presentation(presentation_id=presentation_id, user_id=user_id)
        latest = self._request(
            "GET",
            "presentation_versions",
            params={
                "select": "version_number",
                "presentation_id": f"eq.{presentation_id}",
                "order": "version_number.desc",
                "limit": "1",
            },
        )
        version_number = 1
        if latest.status_code == 200 and latest.json():
            version_number = int(latest.json()[0]["version_number"]) + 1

        version_payload = {
            "presentation_id": str(presentation_id),
            "version_number": version_number,
            "slides_json": [],
            "status": "generating",
        }
        version_response = self._request(
            "POST",
            "presentation_versions",
            json_body=version_payload,
        )
        if version_response.status_code not in (200, 201):
            raise bad_request("PRESENTATION_VERSION_CREATE_FAILED", version_response.text)
        version_row = _normalize_presentation_version(version_response.json()[0])

        presentation = self.get_presentation(presentation_id=presentation_id, user_id=user_id)
        plan = self.get_presentation_plan(
            presentation_plan_id=presentation["presentation_plan_id"],
            user_id=user_id,
        )
        framework = self.get_framework_version(
            framework_version_id=plan["framework_version_id"],
            user_id=user_id,
        )
        slide_specs: list[dict[str, Any]] = []
        for planned in planned_slides_with_generators(plan_json):
            slide_spec = build_slide_spec_for_planned_slide(
                planned=planned,
                framework_json=framework["framework_json"],
            )
            persisted_slide_spec = copy.deepcopy(slide_spec)
            slide_payload = {
                "presentation_version_id": str(version_row["id"]),
                "slide_index": int(planned["order"]) - 1,
                "layout_id": persisted_slide_spec["layoutId"],
                "slide_spec": persisted_slide_spec,
                "source_chapter_ids": copy.deepcopy(
                    persisted_slide_spec["sourceChapterIds"]
                ),
            }
            slide_response = self._request("POST", "slides", json_body=slide_payload)
            if slide_response.status_code not in (200, 201):
                raise bad_request("SLIDE_CREATE_FAILED", slide_response.text)
            slide_specs.append(copy.deepcopy(persisted_slide_spec))

        patch_response = self._request(
            "PATCH",
            "presentation_versions",
            params={"id": f"eq.{version_row['id']}"},
            json_body={"slides_json": slide_specs, "status": "generating"},
        )
        if patch_response.status_code not in (200, 204) or not patch_response.json():
            raise bad_request("PRESENTATION_VERSION_UPDATE_FAILED", patch_response.text)
        version_row = _normalize_presentation_version(patch_response.json()[0])
        if settings.RENDERER_EXECUTION_MODE == "fixture":
            assets = materialize_fixture_deck_assets(
                version_id=version_row["id"],
                slide_count=len(slide_specs),
            )
            version_row = self.update_presentation_version_assets(
                presentation_version_id=version_row["id"],
                assets=assets,
                status="ready",
            )
        return version_row

    def update_presentation_version_assets(
        self,
        *,
        presentation_version_id: UUID,
        assets: dict[str, object],
        status: str,
    ) -> dict[str, Any]:
        asset_patch = self._request(
            "PATCH",
            "presentation_versions",
            params={"id": f"eq.{presentation_version_id}"},
            json_body={
                "pptx_storage_path": assets["pptx_storage_path"],
                "pdf_storage_path": assets["pdf_storage_path"],
                "status": status,
            },
        )
        if asset_patch.status_code not in (200, 204) or not asset_patch.json():
            raise bad_request("PRESENTATION_VERSION_UPDATE_FAILED", asset_patch.text)
        version_row = _normalize_presentation_version(asset_patch.json()[0])
        version_row["preview_image_paths"] = assets["preview_image_paths"]
        return version_row

    def get_latest_presentation_version(
        self,
        *,
        presentation_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        _ = user_id
        self.get_presentation(presentation_id=presentation_id, user_id=user_id)
        response = self._request(
            "GET",
            "presentation_versions",
            params={
                "select": "*",
                "presentation_id": f"eq.{presentation_id}",
                "order": "version_number.desc",
                "limit": "1",
            },
        )
        if response.status_code != 200 or not response.json():
            raise not_found(
                "PRESENTATION_VERSION_NOT_FOUND",
                f"No presentation version exists for presentation {presentation_id}",
            )
        return _normalize_presentation_version(response.json()[0])

    def get_slide(
        self,
        *,
        presentation_id: UUID,
        slide_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        version = self.get_latest_presentation_version(
            presentation_id=presentation_id,
            user_id=user_id,
        )
        response = self._request(
            "GET",
            "slides",
            params={
                "select": "*",
                "id": f"eq.{slide_id}",
                "presentation_version_id": f"eq.{version['id']}",
                "limit": "1",
            },
        )
        if response.status_code != 200 or not response.json():
            raise not_found("SLIDE_NOT_FOUND", f"Slide {slide_id} was not found")
        return _normalize_slide(response.json()[0])

    def regenerate_slide(
        self,
        *,
        presentation_id: UUID,
        slide_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        return self._create_edited_presentation_version(
            presentation_id=presentation_id,
            slide_id=slide_id,
            user_id=user_id,
            layout_id=None,
        )

    def change_slide_layout(
        self,
        *,
        presentation_id: UUID,
        slide_id: UUID,
        user_id: UUID,
        layout_id: str,
    ) -> dict[str, Any]:
        return self._create_edited_presentation_version(
            presentation_id=presentation_id,
            slide_id=slide_id,
            user_id=user_id,
            layout_id=layout_id,
        )

    def _create_edited_presentation_version(
        self,
        *,
        presentation_id: UUID,
        slide_id: UUID,
        user_id: UUID,
        layout_id: str | None,
    ) -> dict[str, Any]:
        target = self.get_slide(
            presentation_id=presentation_id,
            slide_id=slide_id,
            user_id=user_id,
        )
        previous = self.get_latest_presentation_version(
            presentation_id=presentation_id,
            user_id=user_id,
        )
        old_slides = self.list_slides(presentation_id=presentation_id, user_id=user_id)
        presentation = self.get_presentation(presentation_id=presentation_id, user_id=user_id)
        plan = self.get_presentation_plan(
            presentation_plan_id=presentation["presentation_plan_id"],
            user_id=user_id,
        )
        framework = self.get_framework_version(
            framework_version_id=plan["framework_version_id"],
            user_id=user_id,
        )
        version_response = self._request(
            "POST",
            "presentation_versions",
            json_body={
                "presentation_id": str(presentation_id),
                "version_number": int(previous["version_number"]) + 1,
                "slides_json": [],
                "status": "generating",
            },
        )
        if version_response.status_code not in (200, 201):
            raise bad_request("PRESENTATION_VERSION_CREATE_FAILED", version_response.text)
        version = _normalize_presentation_version(version_response.json()[0])

        edited: dict[str, Any] | None = None
        specs: list[dict[str, Any]] = []
        for old_slide in old_slides:
            next_layout = layout_id if old_slide["id"] == target["id"] and layout_id else old_slide["layout_id"]
            if old_slide["id"] == target["id"]:
                references = [
                    "opportunity" if chapter_id == "0" else f"chapter_{chapter_id}"
                    for chapter_id in old_slide["source_chapter_ids"]
                ]
                spec = build_slide_spec_for_planned_slide(
                    planned={
                        "order": int(old_slide["slide_index"]) + 1,
                        "layoutId": next_layout,
                        "frameworkReferences": references,
                    },
                    framework_json=framework["framework_json"],
                )
            else:
                spec = copy.deepcopy(old_slide["slide_spec"])
            slide_response = self._request(
                "POST",
                "slides",
                json_body={
                    "presentation_version_id": str(version["id"]),
                    "slide_index": old_slide["slide_index"],
                    "layout_id": next_layout,
                    "slide_spec": spec,
                    "source_chapter_ids": spec["sourceChapterIds"],
                },
            )
            if slide_response.status_code not in (200, 201):
                raise bad_request("SLIDE_CREATE_FAILED", slide_response.text)
            new_slide = _normalize_slide(slide_response.json()[0])
            specs.append(spec)
            if old_slide["id"] == target["id"]:
                edited = new_slide

        patch = self._request(
            "PATCH",
            "presentation_versions",
            params={"id": f"eq.{version['id']}"},
            json_body={"slides_json": specs},
        )
        if patch.status_code not in (200, 204) or not patch.json():
            raise bad_request("PRESENTATION_VERSION_UPDATE_FAILED", patch.text)
        if settings.RENDERER_EXECUTION_MODE == "fixture":
            assets = materialize_fixture_deck_assets(
                version_id=version["id"],
                slide_count=len(specs),
            )
            self.update_presentation_version_assets(
                presentation_version_id=version["id"],
                assets=assets,
                status="ready",
            )
        if edited is None:
            raise not_found("SLIDE_NOT_FOUND", f"Slide {slide_id} was not found")
        return edited

    def list_slides(
        self,
        *,
        presentation_id: UUID,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        version = self.get_latest_presentation_version(
            presentation_id=presentation_id,
            user_id=user_id,
        )
        response = self._request(
            "GET",
            "slides",
            params={
                "select": "*",
                "presentation_version_id": f"eq.{version['id']}",
                "order": "slide_index.asc",
            },
        )
        if response.status_code != 200:
            raise bad_request("SLIDE_LIST_FAILED", response.text)
        return [_normalize_slide(row) for row in response.json()]

    def get_latest_presentation_for_opportunity(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        rows = [
            row
            for row in self.list_presentations(user_id=user_id)
            if self.get_presentation_opportunity_id(
                presentation_id=row["id"],
                user_id=user_id,
            )
            == opportunity_id
        ]
        if not rows:
            raise not_found(
                "PRESENTATION_NOT_FOUND",
                f"No presentation exists for opportunity {opportunity_id}",
            )
        return max(rows, key=lambda row: row["created_at"])

    def get_presentation_version_assets(
        self,
        *,
        presentation_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        version = self.get_latest_presentation_version(
            presentation_id=presentation_id,
            user_id=user_id,
        )
        if version.get("status") != "ready":
            raise bad_request(
                "PRESENTATION_NOT_READY",
                "Presentation version is not ready for preview or download",
            )
        version_id = version["id"]
        slide_count = max(len(version.get("slides_json") or []), 1)
        if not version.get("pptx_storage_path"):
            version["pptx_storage_path"] = str(resolve_pptx_path(version_id=version_id).resolve())
        if not version.get("pdf_storage_path"):
            version["pdf_storage_path"] = str(resolve_pdf_path(version_id=version_id).resolve())
        version["preview_image_paths"] = [
            str(resolve_preview_image_path(version_id=version_id, slide_index=index).resolve())
            for index in range(slide_count)
        ]
        return version

    def append_audit_log(
        self,
        *,
        actor_id: UUID,
        action: str,
        object_type: str,
        object_id: UUID,
    ) -> dict[str, Any]:
        payload = {
            "actor_id": str(actor_id),
            "action": action,
            "object_type": object_type,
            "object_id": str(object_id),
        }
        response = self._request("POST", "audit_log", json_body=payload)
        if response.status_code not in (200, 201):
            raise bad_request("AUDIT_LOG_WRITE_FAILED", response.text)
        row = response.json()[0]
        return {
            "id": UUID(str(row["id"])),
            "actor_id": UUID(str(row["actor_id"])),
            "action": row["action"],
            "object_type": row["object_type"],
            "object_id": UUID(str(row["object_id"])),
            "timestamp": _parse_timestamp(row["timestamp"]),
        }


def validate_transcript_upload(file_name: str, mime_type: str | None) -> None:
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED_TRANSCRIPT_EXTENSIONS:
        raise bad_request(
            "INVALID_TRANSCRIPT_FORMAT",
            f"Unsupported transcript extension {extension or '(none)'}",
        )
    if mime_type and mime_type not in {
        "text/plain",
        "text/vtt",
        "application/x-subrip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    }:
        raise bad_request("INVALID_TRANSCRIPT_FORMAT", f"Unsupported transcript mime type {mime_type}")
