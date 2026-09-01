"""In-memory data store for unit tests and local development (AT-40 / AT-41)."""

from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.config import settings
from app.services.api_errors import bad_request, conflict, not_found
from app.services.deck_assets import materialize_fixture_deck_assets
from app.services.framework_status import require_reviewable_framework
from app.services.framework_stub_template import load_framework_stub_template
from app.services.stage_b_orchestration import (
    build_slide_spec_for_planned_slide,
    plan_json_from_confirmed_framework,
    planned_slides_with_generators,
)

ALLOWED_TRANSCRIPT_EXTENSIONS = {".txt", ".vtt", ".srt", ".docx"}
ALLOWED_TRANSCRIPT_MIME_TYPES = {
    "text/plain",
    "text/vtt",
    "application/x-subrip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[6]
    / "packages"
    / "contracts"
    / "fixtures"
    / "framework_object.minimal.json"
)
_RICH_FIXTURE_PATH = (
    Path(__file__).resolve().parents[6]
    / "tests"
    / "fixtures"
    / "framework_object.confirmed.group_a.json"
)


def _now() -> datetime:
    return datetime.now(UTC)


def _optional_uuid(value: Any) -> UUID | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


def _llm_call_row(record: Any) -> dict[str, Any]:
    payload = (
        {key: getattr(record, key) for key in getattr(record, "__dataclass_fields__", {})}
        if getattr(record, "__dataclass_fields__", None)
        else dict(record)
    )
    created = payload.get("created_at") or payload.get("timestamp") or _now()
    return {
        "id": _optional_uuid(payload.get("id")) or uuid.uuid4(),
        "request_id": str(payload.get("request_id") or uuid.uuid4()),
        "job_id": _optional_uuid(payload.get("job_id")),
        "opportunity_id": _optional_uuid(payload.get("opportunity_id")),
        "stage": str(payload.get("stage") or ""),
        "provider": str(payload.get("provider") or "unknown"),
        "model": str(payload.get("model") or ""),
        "prompt_version": str(payload.get("prompt_version") or ""),
        "input_tokens": int(payload.get("input_tokens") or 0),
        "output_tokens": int(payload.get("output_tokens") or 0),
        "total_tokens": int(
            payload.get("total_tokens")
            or (int(payload.get("input_tokens") or 0) + int(payload.get("output_tokens") or 0))
        ),
        "latency_ms": int(round(float(payload.get("latency_ms") or 0))),
        "retry_count": int(payload.get("retry_count") or 0),
        "status": str(payload.get("status") or "success"),
        "error_category": payload.get("error_category"),
        "estimated_cost_eur": float(payload.get("estimated_cost_eur") or 0),
        "created_at": created,
    }


def _load_framework_template(opportunity_id: UUID) -> dict[str, Any]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    payload = copy.deepcopy(payload)
    if _RICH_FIXTURE_PATH.is_file():
        rich = json.loads(_RICH_FIXTURE_PATH.read_text(encoding="utf-8"))
        for index, chapter in enumerate(payload.get("chapters", [])):
            rich_chapter = rich.get("chapters", [])[index] if index < len(rich.get("chapters", [])) else None
            if rich_chapter and rich_chapter.get("source_refs"):
                chapter["body"] = copy.deepcopy(rich_chapter.get("body", chapter.get("body")))
                chapter["source_refs"] = copy.deepcopy(rich_chapter.get("source_refs", []))
        payload["quality_scores"] = copy.deepcopy(rich.get("quality_scores", payload["quality_scores"]))
        payload["kpis"] = copy.deepcopy(rich.get("kpis", payload["kpis"]))
        payload["rules"] = copy.deepcopy(rich.get("rules", payload["rules"]))
    payload["opportunity_id"] = str(opportunity_id)
    payload["updated_at"] = _now().isoformat().replace("+00:00", "Z")
    payload["created_at"] = payload["updated_at"]
    return payload


@dataclass
class MemoryDataStore:
    opportunities: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    transcripts: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    framework_versions: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    presentation_plans: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    presentations: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    presentation_versions: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    slides: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    generation_jobs: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    audit_logs: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    llm_calls: dict[UUID, dict[str, Any]] = field(default_factory=dict)

    def create_generation_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = copy.deepcopy(payload)
        row.setdefault("id", uuid.uuid4())
        row.setdefault("created_at", _now())
        self.generation_jobs[row["id"]] = row
        return copy.deepcopy(row)

    def get_generation_job(self, job_id: UUID) -> dict[str, Any] | None:
        row = self.generation_jobs.get(job_id)
        return copy.deepcopy(row) if row is not None else None

    def update_generation_job(
        self,
        job_id: UUID,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        row = self.generation_jobs.get(job_id)
        if row is None:
            raise not_found("JOB_NOT_FOUND", f"No job found with id {job_id}")
        row.update(copy.deepcopy(updates))
        return copy.deepcopy(row)

    def get_active_job_for_opportunity(
        self,
        opportunity_id: str | UUID,
        stage_group: str | None = None,
        *,
        job_type: str | None = None,
    ) -> dict[str, Any] | None:
        from app.services.job_service import select_reconnect_job

        target = UUID(str(opportunity_id))
        rows = [
            copy.deepcopy(row)
            for row in self.generation_jobs.values()
            if row.get("opportunity_id") == target
            and (job_type is None or str(row.get("job_type") or "") == job_type)
        ]
        return select_reconnect_job(rows, stage_group=stage_group)

    def create_opportunity(
        self,
        *,
        user_id: UUID,
        client_name: str,
        opportunity_name: str,
        department: str,
        language: str,
        pii_redaction_enabled: bool = True,
    ) -> dict[str, Any]:
        opportunity_id = uuid.uuid4()
        now = _now()
        row = {
            "id": opportunity_id,
            "client_name": client_name,
            "opportunity_name": opportunity_name,
            "department": department,
            "language": language,
            "status": "active",
            "pii_redaction_enabled": bool(pii_redaction_enabled),
            "created_by": user_id,
            "created_at": now,
            "updated_at": now,
        }
        self.opportunities[opportunity_id] = row
        return row

    def list_opportunities(self, *, user_id: UUID) -> list[dict[str, Any]]:
        rows = [row for row in self.opportunities.values() if row["created_by"] == user_id]
        return sorted(rows, key=lambda row: row["created_at"], reverse=True)

    def get_opportunity(self, *, opportunity_id: UUID, user_id: UUID) -> dict[str, Any]:
        row = self.opportunities.get(opportunity_id)
        if row is None or row["created_by"] != user_id:
            raise not_found("OPPORTUNITY_NOT_FOUND", f"Opportunity {opportunity_id} was not found")
        return row

    def update_opportunity(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        row = self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        for key, value in updates.items():
            if value is not None:
                row[key] = value
        row["updated_at"] = _now()
        return row

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
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        transcript_id = uuid.uuid4()
        row = {
            "id": transcript_id,
            "opportunity_id": opportunity_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "storage_path": storage_path,
            "conversation_id": conversation_id,
            "content": bytes(content),
            "sections": copy.deepcopy(sections),
            "processing_status": "pending",
            "created_at": _now(),
        }
        self.transcripts[transcript_id] = row
        return row

    def list_transcripts(self, *, opportunity_id: UUID, user_id: UUID) -> list[dict[str, Any]]:
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        rows = [
            row for row in self.transcripts.values() if row["opportunity_id"] == opportunity_id
        ]
        return sorted(rows, key=lambda row: row["created_at"])

    def list_transcript_sources(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return persisted speaker turns for Stage A without reparsing uploads."""
        return [
            {
                "id": row["id"],
                "file_name": row["file_name"],
                "conversation_id": row["conversation_id"],
                "sections": copy.deepcopy(row["sections"]),
            }
            for row in self.list_transcripts(
                opportunity_id=opportunity_id,
                user_id=user_id,
            )
        ]

    def update_transcript_processing_status(
        self,
        *,
        opportunity_id: UUID,
        transcript_id: UUID,
        user_id: UUID,
        processing_status: str,
    ) -> None:
        row = self.get_transcript(
            opportunity_id=opportunity_id,
            transcript_id=transcript_id,
            user_id=user_id,
        )
        row["processing_status"] = processing_status

    def get_transcript(
        self,
        *,
        opportunity_id: UUID,
        transcript_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        row = self.transcripts.get(transcript_id)
        if row is None or row["opportunity_id"] != opportunity_id:
            raise not_found("TRANSCRIPT_NOT_FOUND", f"Transcript {transcript_id} was not found")
        return row

    def regenerate_transcript(
        self,
        *,
        opportunity_id: UUID,
        transcript_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        row = self.get_transcript(
            opportunity_id=opportunity_id,
            transcript_id=transcript_id,
            user_id=user_id,
        )
        row["processing_status"] = "pending"
        return row

    def delete_transcript(
        self,
        *,
        opportunity_id: UUID,
        transcript_id: UUID,
        user_id: UUID,
    ) -> None:
        self.get_transcript(
            opportunity_id=opportunity_id,
            transcript_id=transcript_id,
            user_id=user_id,
        )
        del self.transcripts[transcript_id]

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
        existing = [
            row
            for row in self.framework_versions.values()
            if row["opportunity_id"] == opportunity_id
        ]
        version_number = len(existing) + 1
        framework_version_id = framework_version_id or uuid.uuid4()
        row = {
            "id": framework_version_id,
            "opportunity_id": opportunity_id,
            "version_number": version_number,
            "status": status,
            "framework_json": framework_json,
            "created_by": user_id,
            "created_at": _now(),
        }
        self.framework_versions[framework_version_id] = row
        return row

    def get_latest_framework(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        rows = [
            row
            for row in self.framework_versions.values()
            if row["opportunity_id"] == opportunity_id
        ]
        if not rows:
            raise not_found(
                "FRAMEWORK_NOT_FOUND",
                f"No framework version exists for opportunity {opportunity_id}",
            )
        return max(rows, key=lambda row: row["version_number"])

    def get_framework_version(
        self,
        *,
        framework_version_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        row = self.framework_versions.get(framework_version_id)
        if row is None:
            raise not_found(
                "FRAMEWORK_NOT_FOUND",
                f"Framework version {framework_version_id} was not found",
            )
        self.get_opportunity(opportunity_id=row["opportunity_id"], user_id=user_id)
        return row

    def confirm_framework(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
        framework_version_id: UUID | None,
        confirmed_framework_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if confirmed_framework_json is not None:
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
        elif framework_version_id is not None:
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

        row["status"] = "confirmed"
        framework_json = confirmed_framework_json if confirmed_framework_json is not None else row["framework_json"]
        framework_json["status"] = "confirmed"
        row["framework_json"] = framework_json
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
        updated["updated_at"] = _now().isoformat().replace("+00:00", "Z")
        change_log = updated.setdefault("change_log", [])
        change_log.append("Manual edit via framework review UI")
        row["framework_json"] = updated
        return row

    def regenerate_chapter(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
        chapter_id: str,
    ) -> dict[str, Any]:
        row = self.get_latest_framework(opportunity_id=opportunity_id, user_id=user_id)
        require_reviewable_framework(row["status"], action="regenerate")

        chapters = row["framework_json"].get("chapters", [])
        if not any(str(chapter.get("chapter_id")) == chapter_id for chapter in chapters):
            raise bad_request("INVALID_CHAPTER_ID", f"Chapter {chapter_id} was not found")

        change_log = row["framework_json"].setdefault("change_log", [])
        change_log.append(f"Regenerated chapter {chapter_id}")
        return row

    def generate_framework_stub(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        framework_json = load_framework_stub_template(opportunity_id)
        return self.create_framework_version(
            opportunity_id=opportunity_id,
            user_id=user_id,
            framework_json=framework_json,
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
        presentation_plan_id = presentation_plan_id or uuid.uuid4()
        row = {
            "id": presentation_plan_id,
            "framework_version_id": framework_version_id,
            "plan_json": plan_json,
            "created_at": _now(),
        }
        self.presentation_plans[presentation_plan_id] = row
        return row

    def get_presentation_plan(
        self,
        *,
        presentation_plan_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        row = self.presentation_plans.get(presentation_plan_id)
        if row is None:
            raise not_found(
                "PRESENTATION_PLAN_NOT_FOUND",
                f"Presentation plan {presentation_plan_id} was not found",
            )
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
        self.get_framework_version(
            framework_version_id=framework_version_id,
            user_id=user_id,
        )
        rows = [
            row
            for row in self.presentation_plans.values()
            if row["framework_version_id"] == framework_version_id
        ]
        if not rows:
            return None
        return max(rows, key=lambda row: row["created_at"])

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
        plan = self.get_presentation_plan(
            presentation_plan_id=presentation_plan_id,
            user_id=user_id,
        )
        presentation_id = uuid.uuid4()
        row = {
            "id": presentation_id,
            "presentation_plan_id": presentation_plan_id,
            "name": name,
            "status": "draft",
            "created_at": _now(),
        }
        self.presentations[presentation_id] = row
        _ = plan
        return row

    def list_presentations(self, *, user_id: UUID) -> list[dict[str, Any]]:
        accessible_plan_ids = {
            plan_id
            for plan_id, plan in self.presentation_plans.items()
            if self._user_can_access_plan(plan_id=plan_id, user_id=user_id)
        }
        rows = [
            row
            for row in self.presentations.values()
            if row["presentation_plan_id"] in accessible_plan_ids
        ]
        return sorted(rows, key=lambda row: row["created_at"], reverse=True)

    def get_presentation(
        self,
        *,
        presentation_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        row = self.presentations.get(presentation_id)
        if row is None:
            raise not_found(
                "PRESENTATION_NOT_FOUND",
                f"Presentation {presentation_id} was not found",
            )
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
        presentation = self.get_presentation(presentation_id=presentation_id, user_id=user_id)
        plan = self.get_presentation_plan(
            presentation_plan_id=presentation["presentation_plan_id"],
            user_id=user_id,
        )
        existing = [
            row
            for row in self.presentation_versions.values()
            if row["presentation_id"] == presentation_id
        ]
        version_number = len(existing) + 1
        presentation_version_id = uuid.uuid4()
        version_row = {
            "id": presentation_version_id,
            "presentation_id": presentation_id,
            "version_number": version_number,
            "slides_json": [],
            "pptx_storage_path": None,
            "pdf_storage_path": None,
            "status": "generating",
            "created_at": _now(),
        }
        self.presentation_versions[presentation_version_id] = version_row

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
            slide_id = uuid.uuid4()
            slide_row = {
                "id": slide_id,
                "presentation_version_id": presentation_version_id,
                "slide_index": int(planned["order"]) - 1,
                "layout_id": persisted_slide_spec["layoutId"],
                "slide_spec": persisted_slide_spec,
                "source_chapter_ids": copy.deepcopy(
                    persisted_slide_spec["sourceChapterIds"]
                ),
                "created_at": _now(),
            }
            self.slides[slide_id] = slide_row
            slide_specs.append(copy.deepcopy(persisted_slide_spec))

        version_row["slides_json"] = slide_specs
        if settings.RENDERER_EXECUTION_MODE == "fixture":
            assets = materialize_fixture_deck_assets(
                version_id=presentation_version_id,
                slide_count=len(slide_specs),
            )
            self.update_presentation_version_assets(
                presentation_version_id=presentation_version_id,
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
        row = self.presentation_versions.get(presentation_version_id)
        if row is None:
            raise not_found(
                "PRESENTATION_VERSION_NOT_FOUND",
                f"Presentation version {presentation_version_id} was not found",
            )
        row["pptx_storage_path"] = assets.get("pptx_storage_path")
        row["pdf_storage_path"] = assets.get("pdf_storage_path")
        row["preview_image_paths"] = list(assets.get("preview_image_paths") or [])
        row["status"] = status
        return copy.deepcopy(row)

    def get_latest_presentation_version(
        self,
        *,
        presentation_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        self.get_presentation(presentation_id=presentation_id, user_id=user_id)
        rows = [
            row
            for row in self.presentation_versions.values()
            if row["presentation_id"] == presentation_id
        ]
        if not rows:
            raise not_found(
                "PRESENTATION_VERSION_NOT_FOUND",
                f"No presentation version exists for presentation {presentation_id}",
            )
        return max(rows, key=lambda row: row["version_number"])

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
        row = self.slides.get(slide_id)
        if row is None or row["presentation_version_id"] != version["id"]:
            raise not_found("SLIDE_NOT_FOUND", f"Slide {slide_id} was not found")
        return row

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
        presentation = self.get_presentation(presentation_id=presentation_id, user_id=user_id)
        plan = self.get_presentation_plan(
            presentation_plan_id=presentation["presentation_plan_id"],
            user_id=user_id,
        )
        framework = self.get_framework_version(
            framework_version_id=plan["framework_version_id"],
            user_id=user_id,
        )
        old_slides = [
            row
            for row in self.slides.values()
            if row["presentation_version_id"] == previous["id"]
        ]
        old_slides.sort(key=lambda row: row["slide_index"])
        version_id = uuid.uuid4()
        version = {
            "id": version_id,
            "presentation_id": presentation_id,
            "version_number": int(previous["version_number"]) + 1,
            "slides_json": [],
            "pptx_storage_path": None,
            "pdf_storage_path": None,
            "status": "generating",
            "created_at": _now(),
        }
        self.presentation_versions[version_id] = version

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
            new_slide_id = uuid.uuid4()
            new_slide = {
                "id": new_slide_id,
                "presentation_version_id": version_id,
                "slide_index": old_slide["slide_index"],
                "layout_id": next_layout,
                "slide_spec": spec,
                "source_chapter_ids": list(spec["sourceChapterIds"]),
                "created_at": _now(),
            }
            self.slides[new_slide_id] = new_slide
            specs.append(spec)
            if old_slide["id"] == target["id"]:
                edited = new_slide
        version["slides_json"] = specs
        if settings.RENDERER_EXECUTION_MODE == "fixture":
            assets = materialize_fixture_deck_assets(
                version_id=version_id,
                slide_count=len(specs),
            )
            self.update_presentation_version_assets(
                presentation_version_id=version_id,
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
        rows = [
            row
            for row in self.slides.values()
            if row["presentation_version_id"] == version["id"]
        ]
        return sorted(rows, key=lambda row: row["slide_index"])

    def get_latest_presentation_for_opportunity(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        accessible_plan_ids = {
            plan_id
            for plan_id, plan in self.presentation_plans.items()
            if self._user_can_access_plan(plan_id=plan_id, user_id=user_id)
            and self.framework_versions.get(plan["framework_version_id"], {}).get("opportunity_id")
            == opportunity_id
        }
        rows = [
            row
            for row in self.presentations.values()
            if row["presentation_plan_id"] in accessible_plan_ids
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
        return version

    def _user_can_access_plan(self, *, plan_id: UUID, user_id: UUID) -> bool:
        plan = self.presentation_plans.get(plan_id)
        if plan is None:
            return False
        framework = self.framework_versions.get(plan["framework_version_id"])
        if framework is None:
            return False
        opportunity = self.opportunities.get(framework["opportunity_id"])
        return opportunity is not None and opportunity["created_by"] == user_id

    def append_audit_log(
        self,
        *,
        actor_id: UUID,
        action: str,
        object_type: str,
        object_id: UUID,
    ) -> dict[str, Any]:
        entry_id = uuid.uuid4()
        now = _now()
        row = {
            "id": entry_id,
            "actor_id": actor_id,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "timestamp": now,
        }
        self.audit_logs[entry_id] = row
        return row

    def list_audit_logs(self, *, actor_id: UUID | None = None) -> list[dict[str, Any]]:
        rows = list(self.audit_logs.values())
        if actor_id is not None:
            rows = [row for row in rows if row["actor_id"] == actor_id]
        return sorted(rows, key=lambda row: row["timestamp"])

    def append_llm_call(self, record: Any) -> dict[str, Any]:
        row = _llm_call_row(record)
        self.llm_calls[row["id"]] = row
        return copy.deepcopy(row)

    def get_llm_calls_for_job(self, job_id: str) -> list[dict[str, Any]]:
        target = UUID(str(job_id))
        rows = [row for row in self.llm_calls.values() if row.get("job_id") == target]
        return [copy.deepcopy(row) for row in sorted(rows, key=lambda item: item["created_at"])]


_memory_store = MemoryDataStore()


def get_memory_store() -> MemoryDataStore:
    return _memory_store


def reset_memory_store() -> None:
    global _memory_store
    _memory_store = MemoryDataStore()
