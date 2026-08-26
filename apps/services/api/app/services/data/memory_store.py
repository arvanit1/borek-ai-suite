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

from app.services.api_errors import bad_request, conflict, not_found

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
_PLAN_FIXTURE_PATH = (
    Path(__file__).resolve().parents[6]
    / "packages"
    / "contracts"
    / "fixtures"
    / "presentation_plan.minimal.json"
)


def _now() -> datetime:
    return datetime.now(UTC)


def _load_framework_template(opportunity_id: UUID) -> dict[str, Any]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    payload = copy.deepcopy(payload)
    payload["opportunity_id"] = str(opportunity_id)
    payload["updated_at"] = _now().isoformat().replace("+00:00", "Z")
    payload["created_at"] = payload["updated_at"]
    return payload


def _load_presentation_plan_template() -> dict[str, Any]:
    return copy.deepcopy(json.loads(_PLAN_FIXTURE_PATH.read_text(encoding="utf-8")))


def _framework_refs_to_chapter_ids(refs: list[str]) -> list[str]:
    chapter_ids: list[str] = []
    for ref in refs:
        if ref.startswith("chapter_"):
            chapter_ids.append(ref.removeprefix("chapter_"))
        elif ref == "opportunity":
            chapter_ids.append("0")
    return chapter_ids or ["1"]


def _build_stub_slide_spec(*, order: int, layout_id: str, source_chapter_ids: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "slideId": f"slide_{order:02d}",
        "layoutId": layout_id,
        "title": f"Slide {order}",
        "sourceChapterIds": source_chapter_ids,
    }


@dataclass
class MemoryDataStore:
    opportunities: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    transcripts: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    framework_versions: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    presentation_plans: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    presentations: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    presentation_versions: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    slides: dict[UUID, dict[str, Any]] = field(default_factory=dict)

    def create_opportunity(
        self,
        *,
        user_id: UUID,
        client_name: str,
        opportunity_name: str,
        department: str,
        language: str,
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
    ) -> dict[str, Any]:
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        transcript_id = uuid.uuid4()
        row = {
            "id": transcript_id,
            "opportunity_id": opportunity_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "storage_path": storage_path,
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

    def create_framework_version(
        self,
        *,
        opportunity_id: UUID,
        user_id: UUID,
        framework_json: dict[str, Any],
        status: str = "draft",
    ) -> dict[str, Any]:
        self.get_opportunity(opportunity_id=opportunity_id, user_id=user_id)
        existing = [
            row
            for row in self.framework_versions.values()
            if row["opportunity_id"] == opportunity_id
        ]
        version_number = len(existing) + 1
        framework_version_id = uuid.uuid4()
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

        row["status"] = "confirmed"
        framework_json = row["framework_json"]
        framework_json["status"] = "confirmed"
        return row

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
        framework_json = _load_framework_template(opportunity_id)
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
        presentation_plan_id = uuid.uuid4()
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

    def generate_presentation_plan_stub(
        self,
        *,
        framework_version_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        return self.create_presentation_plan(
            framework_version_id=framework_version_id,
            user_id=user_id,
            plan_json=_load_presentation_plan_template(),
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
        self.get_presentation(presentation_id=presentation_id, user_id=user_id)
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

        slide_specs: list[dict[str, Any]] = []
        for planned in sorted(plan_json.get("slides", []), key=lambda item: item["order"]):
            layout_id = planned["layoutId"]
            source_chapter_ids = _framework_refs_to_chapter_ids(planned.get("frameworkReferences", []))
            slide_spec = _build_stub_slide_spec(
                order=int(planned["order"]),
                layout_id=layout_id,
                source_chapter_ids=source_chapter_ids,
            )
            slide_id = uuid.uuid4()
            slide_row = {
                "id": slide_id,
                "presentation_version_id": presentation_version_id,
                "slide_index": int(planned["order"]) - 1,
                "layout_id": layout_id,
                "slide_spec": slide_spec,
                "source_chapter_ids": source_chapter_ids,
                "created_at": _now(),
            }
            self.slides[slide_id] = slide_row
            slide_specs.append(slide_spec)

        version_row["slides_json"] = slide_specs
        version_row["status"] = "ready"
        return version_row

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
        row = self.get_slide(
            presentation_id=presentation_id,
            slide_id=slide_id,
            user_id=user_id,
        )
        row["slide_spec"] = copy.deepcopy(row["slide_spec"])
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
        row["layout_id"] = layout_id
        row["slide_spec"] = slide_spec
        return row

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

    def _user_can_access_plan(self, *, plan_id: UUID, user_id: UUID) -> bool:
        plan = self.presentation_plans.get(plan_id)
        if plan is None:
            return False
        framework = self.framework_versions.get(plan["framework_version_id"])
        if framework is None:
            return False
        opportunity = self.opportunities.get(framework["opportunity_id"])
        return opportunity is not None and opportunity["created_by"] == user_id


_memory_store = MemoryDataStore()


def get_memory_store() -> MemoryDataStore:
    return _memory_store


def reset_memory_store() -> None:
    global _memory_store
    _memory_store = MemoryDataStore()
