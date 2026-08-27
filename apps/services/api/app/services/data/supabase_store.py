"""Supabase PostgREST data access with caller JWT for RLS (AT-40 / AT-41)."""

from __future__ import annotations

import copy
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from app.config import settings
from app.services.api_errors import bad_request, conflict, not_found
from app.services.data.memory_store import (
    ALLOWED_TRANSCRIPT_EXTENSIONS,
    _build_stub_slide_spec,
    _framework_refs_to_chapter_ids,
)
from app.services.deck_assets import materialize_stub_deck_assets

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[6]
    / "packages"
    / "contracts"
    / "fixtures"
    / "framework_object.minimal.json"
)
_PLAN_FIXTURE_PATH = (
    Path(__file__).resolve().parents[6]
    / "packages"
    / "contracts"
    / "fixtures"
    / "presentation_plan.minimal.json"
)


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


class SupabaseDataStore:
    """PostgREST client scoped to the authenticated user's access token."""

    def __init__(self, access_token: str) -> None:
        self._base_url = settings.SUPABASE_URL.rstrip("/")
        self._headers = {
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> httpx.Response:
        response = httpx.request(
            method,
            f"{self._base_url}/rest/v1/{table}",
            headers=self._headers,
            params=params,
            json=json_body,
            timeout=30.0,
        )
        return response

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
        _ = user_id
        response = self._request(
            "GET",
            "opportunities",
            params={"select": "*", "order": "created_at.desc"},
        )
        if response.status_code != 200:
            raise bad_request("OPPORTUNITY_LIST_FAILED", response.text)
        return [_normalize_opportunity(row) for row in response.json()]

    def get_opportunity(self, *, opportunity_id: UUID, user_id: UUID) -> dict[str, Any]:
        _ = user_id
        response = self._request(
            "GET",
            "opportunities",
            params={"select": "*", "id": f"eq.{opportunity_id}", "limit": "1"},
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
        _ = user_id
        payload = {key: value for key, value in updates.items() if value is not None}
        payload["updated_at"] = datetime.now(UTC).isoformat()
        response = self._request(
            "PATCH",
            "opportunities",
            params={"id": f"eq.{opportunity_id}"},
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
    ) -> dict[str, Any]:
        _ = user_id
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        payload = {
            "opportunity_id": str(opportunity_id),
            "file_name": file_name,
            "mime_type": mime_type,
            "storage_path": storage_path,
            "processing_status": "pending",
        }
        response = self._request("POST", "transcripts", json_body=payload)
        if response.status_code not in (200, 201):
            raise bad_request("TRANSCRIPT_UPLOAD_FAILED", response.text)
        return _normalize_transcript(response.json()[0])

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
        if row["status"] == "confirmed":
            raise conflict("FRAMEWORK_IMMUTABLE", "Confirmed framework versions cannot be edited")
        if row["status"] != "draft":
            raise bad_request(
                "FRAMEWORK_NOT_EDITABLE",
                f"Framework version status {row['status']} cannot be edited",
            )

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

        if row["status"] == "confirmed":
            raise conflict("FRAMEWORK_ALREADY_CONFIRMED", "Framework version is already confirmed")
        if row["status"] != "draft":
            raise bad_request(
                "FRAMEWORK_NOT_CONFIRMABLE",
                f"Framework version status {row['status']} cannot be confirmed",
            )

        framework_json = copy.deepcopy(row["framework_json"])
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
        if row["status"] != "draft":
            raise bad_request(
                "FRAMEWORK_NOT_EDITABLE",
                "Only draft framework versions support chapter regeneration",
            )

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
        payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        payload = copy.deepcopy(payload)
        payload["opportunity_id"] = str(opportunity_id)
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        payload["created_at"] = now
        payload["updated_at"] = now
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

    def generate_presentation_plan_stub(
        self,
        *,
        framework_version_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        plan_json = copy.deepcopy(json.loads(_PLAN_FIXTURE_PATH.read_text(encoding="utf-8")))
        return self.create_presentation_plan(
            framework_version_id=framework_version_id,
            user_id=user_id,
            plan_json=plan_json,
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

        slide_specs: list[dict[str, Any]] = []
        for planned in sorted(plan_json.get("slides", []), key=lambda item: item["order"]):
            layout_id = planned["layoutId"]
            source_chapter_ids = _framework_refs_to_chapter_ids(planned.get("frameworkReferences", []))
            slide_spec = _build_stub_slide_spec(
                order=int(planned["order"]),
                layout_id=layout_id,
                source_chapter_ids=source_chapter_ids,
            )
            slide_payload = {
                "presentation_version_id": str(version_row["id"]),
                "slide_index": int(planned["order"]) - 1,
                "layout_id": layout_id,
                "slide_spec": slide_spec,
                "source_chapter_ids": source_chapter_ids,
            }
            slide_response = self._request("POST", "slides", json_body=slide_payload)
            if slide_response.status_code not in (200, 201):
                raise bad_request("SLIDE_CREATE_FAILED", slide_response.text)
            slide_specs.append(slide_spec)

        patch_response = self._request(
            "PATCH",
            "presentation_versions",
            params={"id": f"eq.{version_row['id']}"},
            json_body={"slides_json": slide_specs, "status": "ready"},
        )
        if patch_response.status_code not in (200, 204) or not patch_response.json():
            raise bad_request("PRESENTATION_VERSION_UPDATE_FAILED", patch_response.text)
        version_row = _normalize_presentation_version(patch_response.json()[0])
        assets = materialize_stub_deck_assets(
            version_id=version_row["id"],
            slide_count=len(slide_specs),
        )
        asset_patch = self._request(
            "PATCH",
            "presentation_versions",
            params={"id": f"eq.{version_row['id']}"},
            json_body={
                "pptx_storage_path": assets["pptx_storage_path"],
                "pdf_storage_path": assets["pdf_storage_path"],
            },
        )
        if asset_patch.status_code in (200, 204) and asset_patch.json():
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
        row = self.get_slide(
            presentation_id=presentation_id,
            slide_id=slide_id,
            user_id=user_id,
        )
        return row

    def change_slide_layout(
        self,
        *,
        presentation_id: UUID,
        slide_id: UUID,
        user_id: UUID,
        layout_id: str,
    ) -> dict[str, Any]:
        row = self.get_slide(
            presentation_id=presentation_id,
            slide_id=slide_id,
            user_id=user_id,
        )
        slide_spec = copy.deepcopy(row["slide_spec"])
        slide_spec["layoutId"] = layout_id
        response = self._request(
            "PATCH",
            "slides",
            params={"id": f"eq.{slide_id}"},
            json_body={"layout_id": layout_id, "slide_spec": slide_spec},
        )
        if response.status_code not in (200, 204) or not response.json():
            raise bad_request("SLIDE_LAYOUT_CHANGE_FAILED", response.text)
        return _normalize_slide(response.json()[0])

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
        preview_dir_assets = materialize_stub_deck_assets(
            version_id=version["id"],
            slide_count=max(len(version.get("slides_json") or []), 1),
        )
        if not version.get("pptx_storage_path"):
            version["pptx_storage_path"] = preview_dir_assets["pptx_storage_path"]
        if not version.get("pdf_storage_path"):
            version["pdf_storage_path"] = preview_dir_assets["pdf_storage_path"]
        version["preview_image_paths"] = preview_dir_assets["preview_image_paths"]
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
