"""Exercise production generation/repair/compression with offline injected executors."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from llm.client import LlmClient, LlmUsageResult
from llm.live_slide_repair import wrap_live_structured_generator
from services.slides.content_generation.group_a.common import (
    ContentPolicyValidationError,
)
from services.slides.content_generation.group_a.context_01 import generate_context_01
from services.validation.slide_content_policy import current_compression_language

ROOT = Path(__file__).resolve().parents[3]
GERMAN = "Der Prozess wird manuell bearbeitet. Die Automatisierung ist geplant."
UNSUPPORTED = "Die Automatisierung ist implementiert."
ENGLISH = "Every invoice needs review before booking."


@pytest.fixture(autouse=True)
def forbid_live_localization(monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("Offline fixtures must already contain German customer chapters")

    monkeypatch.setattr("services.framework.localization.make_localize_fn", forbidden)


def framework(language="de"):
    value = json.loads(
        (ROOT / "tests/fixtures/framework_object.confirmed.group_a.json").read_text()
    )
    if language == "de":
        chapters = copy.deepcopy(value["chapters"])
        for chapter in chapters:
            chapter["title"] = "Prozess"
            chapter["body"] = [{"block": "prose", "text": GERMAN}]
        value["customer_view"] = {"render_language": "de", "chapters": chapters}
    return value


def slide(language="de"):
    value = json.loads(
        (
            ROOT
            / "packages/contracts/fixtures/slide_spec/group_a/context_01.minimal.json"
        ).read_text()
    )
    if language == "de":
        value["title"] = "Prozessübersicht"
        for field in ("problem", "solution", "currentState", "targetState"):
            value[field] = {"title": "Prozess", "description": GERMAN}
    return value


def run(outputs, *, language="de", compress=None, live_repair=False):
    requests = []

    def generate(request):
        requests.append(request)
        return copy.deepcopy(outputs[min(len(requests) - 1, len(outputs) - 1)])

    generator = wrap_live_structured_generator(generate) if live_repair else generate
    original = framework(language)
    before = copy.deepcopy(original)
    result = generate_context_01(
        original,
        structured_generate=generator,
        compress_fields=compress or (lambda values, violations: values),
    )
    assert original == before
    return result, requests


@pytest.mark.parametrize("bad_text", [UNSUPPORTED, ENGLISH])
@pytest.mark.parametrize("live_repair", [False, True])
def test_invalid_status_or_language_is_regenerated_with_original_language(
    bad_text, live_repair
):
    bad = slide()
    bad["solution"]["description"] = bad_text
    before = copy.deepcopy(bad)
    result, requests = run([bad, slide()], live_repair=live_repair)
    assert result.status == "VALID"
    assert result.slide_spec["solution"]["description"] == GERMAN
    assert bad == before  # Never silently rewrite an unsupported assertion.
    assert len(requests) == 2
    for request in requests:
        assert request.render_language == "de"
        assert "German (Deutsch)" in request.instructions
        assert "SOURCE STATUS" in request.instructions
    assert "rejected" in requests[-1].instructions.lower()


@pytest.mark.parametrize("bad_text", [UNSUPPORTED, ENGLISH])
def test_retry_exhaustion_does_not_return_a_persistable_spec(bad_text):
    bad = slide()
    bad["solution"]["description"] = bad_text
    calls = []

    def generate(request):
        calls.append(request)
        return copy.deepcopy(bad)

    with pytest.raises(ContentPolicyValidationError):
        generate_context_01(
            framework(),
            structured_generate=generate,
            compress_fields=lambda *_: pytest.fail(
                "Invalid candidate reached compression"
            ),
        )
    assert len(calls) == 3


@pytest.mark.parametrize("bad_text", [UNSUPPORTED, ENGLISH])
def test_post_compression_policy_failure_retries_before_returning(bad_text):
    long = slide()
    long["solution"]["description"] = GERMAN * 6
    calls = []

    def compress(values, violations):
        calls.append(values)
        assert current_compression_language() == "de"
        return {"solution.description": bad_text}

    result, requests = run([long, slide()], compress=compress)
    assert result.status == "VALID"
    assert len(calls) == 1
    assert len(requests) == 2
    assert result.slide_spec["solution"]["description"] == GERMAN
    assert current_compression_language() is None


@pytest.mark.parametrize("bad_text", [UNSUPPORTED, ENGLISH])
def test_repeated_post_compression_policy_failure_is_terminal(bad_text):
    long = slide()
    long["solution"]["description"] = GERMAN * 6
    calls = []

    def compress(values, violations):
        calls.append(values)
        return {"solution.description": bad_text}

    with pytest.raises(ContentPolicyValidationError):
        run([long], compress=compress)
    assert len(calls) == 3
    assert current_compression_language() is None


def test_english_generation_keeps_english_behavior():
    result, requests = run([slide("en")], language="en")
    assert result.status == "VALID"
    assert len(requests) == 1
    assert requests[0].render_language == "en"
    assert "Required output language: English" in requests[0].instructions


def test_real_client_compression_payload_preserves_language_and_source_status():
    calls = []

    def executor(stage, operation, prompt_version, retry_count, request=None):
        calls.append(request)
        return LlmUsageResult({"solution.description": GERMAN}, 0, 0)

    client = LlmClient(executor=executor)
    long = slide()
    long["solution"]["description"] = GERMAN * 6
    result, _ = run([long], compress=client.compression_fields_fn())
    assert result.status == "VALID"
    assert len(calls) == 1
    assert calls[0]["renderLanguage"] == "de"
    assert "German (Deutsch)" in calls[0]["instructions"]
    assert "SOURCE STATUS" in calls[0]["instructions"]
    assert "NUMBERS" in calls[0]["instructions"]
    assert current_compression_language() is None


def test_real_client_structured_payload_carries_language():
    _, requests = run([slide()])
    calls = []

    def executor(stage, operation, prompt_version, retry_count, request=None):
        calls.append(request)
        return LlmUsageResult(slide(), 0, 0)

    LlmClient(executor=executor).structured_generator()(requests[0])
    assert calls[0]["renderLanguage"] == "de"
    assert "German (Deutsch)" in calls[0]["instructions"]


@pytest.mark.parametrize("repaired_text", [ENGLISH, UNSUPPORTED])
def test_numeric_field_repair_is_rechecked_for_language_and_status(repaired_text):
    bad = slide()
    bad["solution"]["description"] = "Der Prozess bearbeitet 1000000 Rechnungen."
    repaired = slide()
    repaired["solution"]["description"] = repaired_text
    result, requests = run([bad, repaired, slide()], live_repair=True)
    assert len(requests) == 3
    assert "solution.description" in requests[1].instructions
    assert all(
        r.render_language == "de" and "German (Deutsch)" in r.instructions
        for r in requests
    )
    assert result.slide_spec["solution"]["description"] == GERMAN


def test_retry_request_language_is_preserved_in_every_layout_group():
    from services.slides.content_generation.group_a import common as a
    from services.slides.content_generation.group_b import common as b
    from services.slides.content_generation.group_c import common as c

    for module in (a, b, c):
        request = module.StructuredGenerationRequest("TEST", (), {}, "German", "de")
        retry = module._with_at8_rejection(request, "policy rejection")
        assert retry.render_language == "de"
        assert retry.chapters == request.chapters


@pytest.mark.parametrize("bad_text", [UNSUPPORTED, ENGLISH])
def test_production_orchestrator_cannot_return_invalid_content_for_persistence(
    bad_text,
):
    from app.services.stage_b_orchestration import build_slide_spec_for_planned_slide

    bad = slide()
    bad["solution"]["description"] = bad_text
    with pytest.raises(ContentPolicyValidationError):
        build_slide_spec_for_planned_slide(
            planned={"layoutId": "CONTEXT_01", "order": 3},
            framework_json=framework(),
            structured_generate=lambda request: copy.deepcopy(bad),
            compress_fields=lambda *_: pytest.fail(
                "Invalid candidate reached compression"
            ),
        )


@pytest.mark.parametrize("group", ["b", "c"])
def test_other_group_generators_derive_language_from_framework(group):
    from services.slides.content_generation.group_b.process_flow_01 import (
        generate_process_flow_01,
    )
    from services.slides.content_generation.group_b.common import (
        StructuredGenerationFailure as BFailure,
    )
    from services.slides.content_generation.group_c.architecture_01 import (
        generate_architecture_01,
    )
    from services.slides.content_generation.group_c.common import (
        StructuredGenerationFailure as CFailure,
    )

    value = json.loads(
        (
            ROOT / f"tests/fixtures/framework_object.confirmed.group_{group}.json"
        ).read_text()
    )
    localized = copy.deepcopy(value["chapters"])
    for chapter in localized:
        chapter["title"] = "Prozess"
        chapter["body"] = [{"block": "prose", "text": GERMAN}]
    value["customer_view"] = {"render_language": "de", "chapters": localized}
    captured = []

    def capture(request):
        captured.append(request)
        raise RuntimeError("offline capture")

    generate = generate_process_flow_01 if group == "b" else generate_architecture_01
    with pytest.raises((BFailure, CFailure), match="offline capture"):
        generate(
            value,
            structured_generate=capture,
            compress_fields=lambda values, violations: values,
        )
    assert captured[0].render_language == "de"
    assert "German (Deutsch)" in captured[0].instructions
    assert "SOURCE STATUS" in captured[0].instructions
