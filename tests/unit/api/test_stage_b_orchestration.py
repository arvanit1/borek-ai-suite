"""Focused regression coverage for the post-PR-35 BT Stage B integration."""

from __future__ import annotations

import copy
import inspect
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from app.services import stage_b_orchestration as stage_b
from app.services.data.memory_store import MemoryDataStore
from app.services.data import supabase_store as supabase_store_module
from app.services.data.supabase_store import SupabaseDataStore
from services.presentation.planner import (
    FrameworkObjectValidationError,
    PresentationPlanningCallError,
)
from services.slides.content_generation.group_a.common import (
    GroupAContentGenerationError,
)
from services.validation.compression_retry import CompressionResult

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
GROUP_A_FIXTURE_DIR = (
    ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a"
)
GROUP_A_CASES = (
    ("COVER_01", "cover_01.realistic.json", ["chapter_1"]),
    ("CONTEXT_01", "context_01.realistic.json", ["chapter_1", "chapter_2"]),
    (
        "PROBLEM_SOLUTION_01",
        "problem_solution_01.realistic.json",
        ["chapter_2", "chapter_4"],
    ),
    ("SCOPE_01", "scope_01.realistic.json", ["chapter_3", "chapter_5"]),
    ("REQUIREMENTS_MATRIX_01", "requirements_matrix_01.realistic.json", ["chapter_5"]),
)
GROUP_A_PLAN = {
    "schema_version": "1.0",
    "title": "Group A test plan",
    "slides": [
        {
            "order": index,
            "purpose": f"group-a-{index}",
            "layoutId": layout_id,
            "frameworkReferences": references,
        }
        for index, (layout_id, _filename, references) in enumerate(GROUP_A_CASES, start=1)
    ],
}

_UNPATCHED_LIVE_PLANNER = stage_b.get_live_planning_client
_UNPATCHED_LIVE_STRUCTURED = stage_b.get_live_structured_generator
_UNPATCHED_LIVE_COMPRESSION = stage_b.get_live_compression_fields


def _framework() -> dict[str, Any]:
    return json.loads(FRAMEWORK_FIXTURE.read_text(encoding="utf-8"))


def _fixture_for_layout(layout_id: str) -> dict[str, Any]:
    filename = next(filename for current, filename, _refs in GROUP_A_CASES if current == layout_id)
    return json.loads((GROUP_A_FIXTURE_DIR / filename).read_text(encoding="utf-8"))


def _structured_fixture(request: Any) -> dict[str, Any]:
    return _fixture_for_layout(request.layout_id)


def _identity_compression(
    offending: dict[str, str],
    _violations: list[Any],
) -> dict[str, str]:
    return copy.deepcopy(offending)


class SpyPlanner:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = copy.deepcopy(response or GROUP_A_PLAN)
        self.calls: list[dict[str, Any] | None] = []

    def complete_planning(
        self,
        *,
        planning_input: dict[str, Any] | None = None,
        prompt_version: str = "v1",
        retry_count: int = 0,
    ) -> dict[str, Any]:
        assert prompt_version == "presentation_planner_v2"
        assert retry_count == 0
        self.calls.append(copy.deepcopy(planning_input))
        return copy.deepcopy(self.response)


class FailingPlanner:
    def complete_planning(self, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("provider unavailable")


def _memory_store_with_framework() -> tuple[MemoryDataStore, UUID, UUID, dict[str, Any]]:
    user_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    store = MemoryDataStore()
    opportunity = store.create_opportunity(
        user_id=user_id,
        client_name="Acme",
        opportunity_name="Invoice automation",
        department="Finance",
        language="en",
    )
    framework_json = _framework()
    framework_json["opportunity_id"] = str(opportunity["id"])
    framework = store.create_framework_version(
        opportunity_id=opportunity["id"],
        user_id=user_id,
        framework_json=framework_json,
        status="confirmed",
    )
    return store, user_id, framework["id"], framework_json


def test_live_provider_factories_fail_clearly_until_shared_providers_exist() -> None:
    for factory in (
        _UNPATCHED_LIVE_PLANNER,
        _UNPATCHED_LIVE_STRUCTURED,
        _UNPATCHED_LIVE_COMPRESSION,
    ):
        with pytest.raises(stage_b.StageBProviderUnavailableError):
            factory()


def test_confirmed_framework_reaches_injected_bt1_planner_exactly_once() -> None:
    framework = _framework()
    original = copy.deepcopy(framework)
    planner = SpyPlanner()

    result = stage_b.plan_json_from_confirmed_framework(framework, planner=planner)

    assert result == GROUP_A_PLAN
    assert len(planner.calls) == 1
    assert planner.calls[0] is not None
    assert planner.calls[0]["frameworkObject"] == framework
    assert framework == original


def test_planner_failure_does_not_fall_back_or_persist() -> None:
    with pytest.raises(PresentationPlanningCallError, match="provider unavailable"):
        stage_b.plan_json_from_confirmed_framework(_framework(), planner=FailingPlanner())

    store, user_id, framework_id, _framework_json = _memory_store_with_framework()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(stage_b, "get_live_planning_client", lambda: FailingPlanner())
        with pytest.raises(PresentationPlanningCallError, match="provider unavailable"):
            store.generate_presentation_plan(
                framework_version_id=framework_id,
                user_id=user_id,
            )
    assert store.presentation_plans == {}


def test_invalid_framework_fails_before_the_planner_call() -> None:
    planner = SpyPlanner()
    with pytest.raises(FrameworkObjectValidationError):
        stage_b.plan_json_from_confirmed_framework({}, planner=planner)
    assert planner.calls == []


@pytest.mark.parametrize("layout_id,fixture_name,references", GROUP_A_CASES)
def test_all_group_a_layouts_route_through_real_generators_without_mutation(
    layout_id: str,
    fixture_name: str,
    references: list[str],
) -> None:
    generated = json.loads((GROUP_A_FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    generated_original = copy.deepcopy(generated)
    requests: list[Any] = []

    def structured_generate(request: Any) -> dict[str, Any]:
        requests.append(request)
        return generated

    result = stage_b.build_slide_spec_for_planned_slide(
        planned={
            "order": 9,
            "purpose": "test",
            "layoutId": layout_id,
            "frameworkReferences": references,
        },
        framework_json=_framework(),
        structured_generate=structured_generate,
        compress_fields=_identity_compression,
    )

    assert len(requests) == 1
    assert requests[0].layout_id == layout_id
    assert result["layoutId"] == layout_id
    assert result["slideId"] == "slide_09"
    assert result["sourceChapterIds"] == generated_original["sourceChapterIds"]
    assert result["fieldProvenance"] == generated_original["fieldProvenance"]
    assert generated == generated_original


def test_real_compression_callback_is_invoked_for_overflow() -> None:
    generated = _fixture_for_layout("COVER_01")
    generated["title"] = "X" * 61
    calls: list[tuple[dict[str, str], list[Any]]] = []

    def compress(offending: dict[str, str], violations: list[Any]) -> dict[str, str]:
        calls.append((copy.deepcopy(offending), list(violations)))
        return {
            violation.path: offending[violation.path][: violation.limit]
            for violation in violations
        }

    result = stage_b.build_slide_spec_for_planned_slide(
        planned=GROUP_A_PLAN["slides"][0],
        framework_json=_framework(),
        structured_generate=lambda _request: generated,
        compress_fields=compress,
    )

    assert len(calls) == 1
    assert calls[0][0] == {"title": "X" * 61}
    assert len(result["title"]) == 60


def test_validation_failed_stops_generation_without_fixture_fallback() -> None:
    generated = _fixture_for_layout("COVER_01")
    generated["title"] = "X" * 61

    with pytest.raises(stage_b.GroupASlideGenerationError, match="failed validation"):
        stage_b.build_slide_spec_for_planned_slide(
            planned=GROUP_A_PLAN["slides"][0],
            framework_json=_framework(),
            structured_generate=lambda _request: generated,
            compress_fields=_identity_compression,
        )


def test_group_a_generation_error_stops_without_fixture_fallback() -> None:
    def fail(_request: Any) -> dict[str, Any]:
        raise RuntimeError("structured provider failed")

    with pytest.raises(GroupAContentGenerationError, match="structured provider failed"):
        stage_b.build_slide_spec_for_planned_slide(
            planned=GROUP_A_PLAN["slides"][0],
            framework_json=_framework(),
            structured_generate=fail,
            compress_fields=_identity_compression,
        )


def test_valid_without_slide_spec_stops_without_fixture_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def empty_result(*_args: Any, **_kwargs: Any) -> CompressionResult:
        return CompressionResult(status="VALID", slide_spec=None, compression_attempts=0)

    monkeypatch.setitem(stage_b._GROUP_A_LAYOUTS, "COVER_01", empty_result)
    with pytest.raises(stage_b.GroupASlideGenerationError, match="without a SlideSpec"):
        stage_b.build_slide_spec_for_planned_slide(
            planned=GROUP_A_PLAN["slides"][0],
            framework_json=_framework(),
            structured_generate=_structured_fixture,
            compress_fields=_identity_compression,
        )


@pytest.mark.parametrize(
    "layout_id",
    ["EXECUTIVE_SUMMARY_01"],
)
def test_unowned_layouts_fail_clearly(layout_id: str) -> None:
    with pytest.raises(stage_b.UnsupportedSlideGeneratorError, match=layout_id):
        stage_b.build_slide_spec_for_planned_slide(
            planned={
                "order": 1,
                "purpose": "unsupported",
                "layoutId": layout_id,
                "frameworkReferences": ["chapter_1"],
            },
            framework_json=_framework(),
            structured_generate=_structured_fixture,
            compress_fields=_identity_compression,
        )


def test_memory_persistence_uses_validated_slide_spec_provenance() -> None:
    store, user_id, framework_id, _framework_json = _memory_store_with_framework()
    cover_plan = copy.deepcopy(GROUP_A_PLAN)
    cover_plan["slides"] = [copy.deepcopy(cover_plan["slides"][0])]
    cover_plan["slides"][0]["frameworkReferences"] = ["opportunity"]
    plan = store.create_presentation_plan(
        framework_version_id=framework_id,
        user_id=user_id,
        plan_json=cover_plan,
    )
    presentation = store.create_presentation(
        presentation_plan_id=plan["id"],
        user_id=user_id,
        name="Provenance regression",
    )

    version = store.create_presentation_version_with_slides(
        presentation_id=presentation["id"],
        user_id=user_id,
        plan_json=cover_plan,
    )
    slide = store.list_slides(presentation_id=presentation["id"], user_id=user_id)[0]

    assert version["status"] == "ready"
    assert slide["layout_id"] == slide["slide_spec"]["layoutId"] == "COVER_01"
    assert slide["source_chapter_ids"] == slide["slide_spec"]["sourceChapterIds"] == ["1"]
    assert version["slides_json"][0] == slide["slide_spec"]


def test_presentation_version_is_not_ready_when_group_a_generation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, user_id, framework_id, _framework_json = _memory_store_with_framework()
    cover_plan = {
        **copy.deepcopy(GROUP_A_PLAN),
        "slides": [copy.deepcopy(GROUP_A_PLAN["slides"][0])],
    }
    plan = store.create_presentation_plan(
        framework_version_id=framework_id,
        user_id=user_id,
        plan_json=cover_plan,
    )
    presentation = store.create_presentation(
        presentation_plan_id=plan["id"],
        user_id=user_id,
        name="Failure regression",
    )
    overflowing = _fixture_for_layout("COVER_01")
    overflowing["title"] = "X" * 61
    monkeypatch.setattr(
        stage_b,
        "get_live_structured_generator",
        lambda: lambda _request: overflowing,
    )
    monkeypatch.setattr(stage_b, "get_live_compression_fields", lambda: _identity_compression)

    with pytest.raises(stage_b.GroupASlideGenerationError):
        store.create_presentation_version_with_slides(
            presentation_id=presentation["id"],
            user_id=user_id,
            plan_json=cover_plan,
        )

    version = next(iter(store.presentation_versions.values()))
    assert version["status"] == "generating"
    assert store.slides == {}


def test_supabase_persistence_uses_validated_slide_spec_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SupabaseDataStore("test-access-token")
    user_id = uuid.uuid4()
    framework_id = uuid.uuid4()
    presentation_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    cover_plan = copy.deepcopy(GROUP_A_PLAN)
    cover_plan["slides"] = [copy.deepcopy(cover_plan["slides"][0])]
    cover_plan["slides"][0]["frameworkReferences"] = ["opportunity"]
    captured_slide_payloads: list[dict[str, Any]] = []

    monkeypatch.setattr(
        store,
        "get_presentation",
        lambda **_kwargs: {
            "id": presentation_id,
            "presentation_plan_id": plan_id,
        },
    )
    monkeypatch.setattr(
        store,
        "get_presentation_plan",
        lambda **_kwargs: {
            "id": plan_id,
            "framework_version_id": framework_id,
        },
    )
    monkeypatch.setattr(
        store,
        "get_framework_version",
        lambda **_kwargs: {
            "id": framework_id,
            "framework_json": _framework(),
        },
    )
    monkeypatch.setattr(
        supabase_store_module,
        "materialize_fixture_deck_assets",
        lambda **_kwargs: {
            "pptx_storage_path": "test.pptx",
            "pdf_storage_path": "test.pdf",
            "preview_image_paths": [],
        },
    )

    def response(status_code: int, payload: list[dict[str, Any]]) -> MagicMock:
        result = MagicMock()
        result.status_code = status_code
        result.json.return_value = payload
        result.text = ""
        return result

    version_row = {
        "id": str(version_id),
        "presentation_id": str(presentation_id),
        "version_number": 1,
        "slides_json": [],
        "status": "generating",
        "created_at": now,
    }

    def fake_request(
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> MagicMock:
        _ = params
        if method == "GET" and table == "presentation_versions":
            return response(200, [])
        if method == "POST" and table == "presentation_versions":
            return response(201, [version_row])
        if method == "POST" and table == "slides":
            assert isinstance(json_body, dict)
            captured_slide_payloads.append(copy.deepcopy(json_body))
            return response(201, [{"id": str(uuid.uuid4())}])
        if method == "PATCH" and table == "presentation_versions":
            assert isinstance(json_body, dict)
            return response(200, [{**version_row, **json_body}])
        raise AssertionError(f"unexpected request: {method} {table}")

    monkeypatch.setattr(store, "_request", fake_request)

    version = store.create_presentation_version_with_slides(
        presentation_id=presentation_id,
        user_id=user_id,
        plan_json=cover_plan,
    )

    assert version["status"] == "ready"
    assert len(captured_slide_payloads) == 1
    slide_payload = captured_slide_payloads[0]
    assert (
        slide_payload["layout_id"]
        == slide_payload["slide_spec"]["layoutId"]
        == "COVER_01"
    )
    assert (
        slide_payload["source_chapter_ids"]
        == slide_payload["slide_spec"]["sourceChapterIds"]
        == ["1"]
    )


def test_supabase_version_is_not_marked_ready_when_group_a_generation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SupabaseDataStore("test-access-token")
    user_id = uuid.uuid4()
    framework_id = uuid.uuid4()
    presentation_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    cover_plan = {
        **copy.deepcopy(GROUP_A_PLAN),
        "slides": [copy.deepcopy(GROUP_A_PLAN["slides"][0])],
    }
    version_patches: list[dict[str, Any]] = []

    monkeypatch.setattr(
        store,
        "get_presentation",
        lambda **_kwargs: {
            "id": presentation_id,
            "presentation_plan_id": plan_id,
        },
    )
    monkeypatch.setattr(
        store,
        "get_presentation_plan",
        lambda **_kwargs: {
            "id": plan_id,
            "framework_version_id": framework_id,
        },
    )
    monkeypatch.setattr(
        store,
        "get_framework_version",
        lambda **_kwargs: {
            "id": framework_id,
            "framework_json": _framework(),
        },
    )

    def response(status_code: int, payload: list[dict[str, Any]]) -> MagicMock:
        result = MagicMock()
        result.status_code = status_code
        result.json.return_value = payload
        result.text = ""
        return result

    def fake_request(
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | list[dict[str, Any]] | None = None,
    ) -> MagicMock:
        _ = params
        if method == "GET" and table == "presentation_versions":
            return response(200, [])
        if method == "POST" and table == "presentation_versions":
            return response(
                201,
                [
                    {
                        "id": str(version_id),
                        "presentation_id": str(presentation_id),
                        "version_number": 1,
                        "slides_json": [],
                        "status": "generating",
                        "created_at": now,
                    }
                ],
            )
        if method == "PATCH" and table == "presentation_versions":
            assert isinstance(json_body, dict)
            version_patches.append(copy.deepcopy(json_body))
            return response(200, [])
        raise AssertionError(f"unexpected request: {method} {table}")

    monkeypatch.setattr(store, "_request", fake_request)
    def fail_generation(**_kwargs: Any) -> dict[str, Any]:
        raise stage_b.GroupASlideGenerationError("VALIDATION_FAILED")

    monkeypatch.setattr(
        supabase_store_module,
        "build_slide_spec_for_planned_slide",
        fail_generation,
    )

    with pytest.raises(stage_b.GroupASlideGenerationError, match="VALIDATION_FAILED"):
        store.create_presentation_version_with_slides(
            presentation_id=presentation_id,
            user_id=user_id,
            plan_json=cover_plan,
        )

    assert version_patches == []


def test_production_orchestration_contains_no_fixture_fallback() -> None:
    source = Path(stage_b.__file__).read_text(encoding="utf-8")
    assert "FixturePlanningClient" not in source
    assert "presentation_plan.minimal.json" not in source
    assert ".realistic.json" not in source
    assert "build_stub_slide_spec" not in source


def test_stage_b_boundaries_have_no_transcript_claude_or_network_inputs() -> None:
    parameter_names = {
        *inspect.signature(stage_b.plan_json_from_confirmed_framework).parameters,
        *inspect.signature(stage_b.build_slide_spec_for_planned_slide).parameters,
    }
    assert not {"transcript", "claude", "api_key"} & parameter_names

    production_source = Path(stage_b.__file__).read_text(encoding="utf-8").lower()
    for forbidden in ("openai_api_key", "anthropic", "httpx", "requests"):
        assert forbidden not in production_source

    provider_source = (
        ROOT / "tests" / "fixtures" / "stage_b_test_providers.py"
    ).read_text(encoding="utf-8").lower()
    for forbidden in ("openai_api_key", "anthropic", "httpx", "requests"):
        assert forbidden not in provider_source


def test_fixture_mode_stub_grounds_group_a_realistic_fixtures() -> None:
    """AT-54 fixture mode must use the Invoice 3-Way Match chapters, not empty stubs.

    Group A realistic SlideSpecs (including COVER_01 title "Invoice 3-Way Match")
    are rejected unless those numbers exist in the attributed chapters.
    """
    from app.services.framework_stub_template import load_framework_stub_template

    framework = load_framework_stub_template(UUID("11111111-1111-4111-8111-111111111111"))
    framework["status"] = "confirmed"
    chapter_1 = next(
        chapter for chapter in framework["chapters"] if str(chapter["chapter_id"]) == "1"
    )
    assert "3-Way Match" in json.dumps(chapter_1)

    for index, (layout_id, _filename, references) in enumerate(GROUP_A_CASES, start=1):
        spec = stage_b.build_slide_spec_for_planned_slide(
            planned={
                "order": index,
                "purpose": f"fixture-mode-{layout_id}",
                "layoutId": layout_id,
                "frameworkReferences": references,
            },
            framework_json=framework,
            structured_generate=_structured_fixture,
            compress_fields=_identity_compression,
        )
        assert spec["layoutId"] == layout_id


@pytest.mark.parametrize(
    ("layout_id", "references", "required_field"),
    [
        ("PROCESS_FLOW_01", ["chapter_2", "chapter_4"], "phases"),
        ("TIMELINE_01", ["chapter_10"], "phases"),
        ("ARCHITECTURE_01", ["chapter_6", "chapter_7"], "components"),
        ("COMPLIANCE_01", ["chapter_8"], "items"),
        ("SUCCESS_METRICS_01", ["chapter_3", "chapter_9"], "criteria"),
        ("OPEN_QUESTIONS_01", ["chapter_11"], "left"),
        ("NEXT_STEPS_01", ["chapter_13"], "steps"),
    ],
)
def test_group_b_and_c_layouts_route_to_owner_generators(
    layout_id: str,
    references: list[str],
    required_field: str,
) -> None:
    from app.services.framework_stub_template import load_framework_stub_template
    from tests.fixtures.stage_b_test_providers import deterministic_structured_generate

    framework = load_framework_stub_template(UUID("11111111-1111-4111-8111-111111111111"))
    framework["status"] = "confirmed"
    spec = stage_b.build_slide_spec_for_planned_slide(
        planned={
            "order": 6,
            "purpose": "owner-routed",
            "layoutId": layout_id,
            "frameworkReferences": references,
        },
        framework_json=framework,
        structured_generate=deterministic_structured_generate,
        compress_fields=_identity_compression,
    )

    assert spec["layoutId"] == layout_id
    assert spec["slideId"] == "slide_06"
    assert spec[required_field]
