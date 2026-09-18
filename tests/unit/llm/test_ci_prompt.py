"""CI v1.2 is prepended to every client-facing generation request."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from llm.ci_prompt import (
    CI_PROMPT_VERSION,
    GAMMA_CI_CONTENT_MARKER,
    gamma_additional_instructions,
    gamma_from_template_prompt,
    load_ci_prompt,
    with_ci_prompt,
)
from services.framework.synthesis import build_synthesis_system_prompt
from services.gamma.contract import GammaContentSlot
from services.gamma.live_client import LiveGammaClient
from services.presentation.planner import plan_presentation
from tests.unit.gamma.test_at60_gamma_adapter import _request as _gamma_request
from tests.unit.gamma.test_jj29_signed_logo_url import OWNED_BASE, _mint
from services.gamma import live_client

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORK_FIXTURE = ROOT / "tests" / "fixtures" / "framework_object.confirmed.group_a.json"
PLAN_FIXTURE = ROOT / "packages" / "contracts" / "fixtures" / "presentation_plan.minimal.json"


def test_ci_prompt_identity_and_idempotent_wrap() -> None:
    ci = load_ci_prompt()
    assert CI_PROMPT_VERSION == "borek-ci:v1.2"
    assert ci.startswith("BOREK SOLUTIONS GROUP — CI PROMPT v1.2")
    assert "#0D1240" in ci
    assert "leverage" in ci
    wrapped = with_ci_prompt("Write one grounded headline.")
    assert wrapped.startswith(ci)
    assert wrapped.endswith("Write one grounded headline.")
    assert with_ci_prompt(wrapped) == wrapped


def test_gamma_from_template_prompt_keeps_content_after_marker() -> None:
    prompt = gamma_from_template_prompt("cover.title: Invoice match")
    assert prompt.startswith(load_ci_prompt())
    assert GAMMA_CI_CONTENT_MARKER in prompt
    assert prompt.rsplit(GAMMA_CI_CONTENT_MARKER, 1)[-1].strip() == "cover.title: Invoice match"


def test_gamma_additional_instructions_fit_public_api_limit() -> None:
    text = gamma_additional_instructions()
    assert text.startswith(load_ci_prompt())
    assert len(text) <= 5000
    assert "Do not render this specification as a slide" in text


def test_from_template_payload_attaches_ci_before_slot_copy() -> None:
    client = LiveGammaClient(api_key="k", theme_id="theme-1", template_id="tpl-1")
    payload = client._generation_payload(  # noqa: SLF001
        _gamma_request(slots=(GammaContentSlot("cover.title", "Invoice 3-way Match"),))
    )
    assert payload["prompt"].startswith(load_ci_prompt())
    assert GAMMA_CI_CONTENT_MARKER in payload["prompt"]
    assert "cover.title: Invoice 3-way Match" in payload["prompt"].split(GAMMA_CI_CONTENT_MARKER, 1)[1]


def test_scratch_payload_sends_ci_as_additional_instructions_not_a_card(
    monkeypatch,
) -> None:
    monkeypatch.setattr(live_client, "owned_https_prefixes", lambda: (f"{OWNED_BASE}/",))
    signed = _mint()
    assert signed is not None
    client = LiveGammaClient(api_key="k", theme_id="theme-1", template_id="tpl-1")
    payload = client._generation_payload(  # noqa: SLF001
        _gamma_request(client_logo_ref=signed)
    )
    assert payload["additionalInstructions"] == gamma_additional_instructions()
    assert not payload["inputText"].startswith("BOREK SOLUTIONS GROUP")
    assert payload["numCards"] == payload["inputText"].count("\n---\n") + 1


def test_synthesis_system_prompt_starts_with_ci() -> None:
    prompt = build_synthesis_system_prompt()
    assert prompt.startswith(load_ci_prompt())
    assert "CUSTOMER Framework Report" in prompt


def test_planner_instructions_start_with_ci() -> None:
    framework = json.loads(FRAMEWORK_FIXTURE.read_text(encoding="utf-8"))
    plan = json.loads(PLAN_FIXTURE.read_text(encoding="utf-8"))

    class _Planner:
        def complete_planning(self, *, planning_input=None, prompt_version="v1", retry_count=0):
            self.instructions = planning_input["instructions"]
            return copy.deepcopy(plan)

    planner = _Planner()
    plan_presentation(framework, planner=planner)
    assert planner.instructions.startswith(load_ci_prompt())
