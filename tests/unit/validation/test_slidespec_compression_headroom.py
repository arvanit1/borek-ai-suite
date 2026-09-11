"""Live internal SlideSpec compression: generic headroom, no clipping."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from llm.client import LlmClient, LlmUsageResult, _apply_compression_number_forms
from services.slides.group_a_compression import validate_and_compress_group_a_slide_spec
from services.slides.group_c_compression import validate_and_compress_group_c_slide_spec
from services.validation.compression_retry import (
    CONTENT_CONSTRAINT_EXCEEDED,
    MAX_COMPRESSION_ATTEMPTS,
    compression_target_length,
)

ROOT = Path(__file__).resolve().parents[3]
CONTEXT_FIXTURE = (
    ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a" / "context_01.minimal.json"
)
ARCHITECTURE_FIXTURE = (
    ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "architecture_01.minimal.json"
)

CONTEXT_TITLE_39 = "Invoice matching still needs exceptions"
CONTEXT_TITLE_REWRITE = "Invoice match exceptions"
CONTEXT_TITLE_OVERSHOOT = "Manual invoice match exceptions"
ARCHITECTURE_DESCRIPTION_102 = (
    "ERP keeps purchase orders, goods receipts and invoice postings used when "
    "matching mailbox files daily."
)
ARCHITECTURE_DESCRIPTION_REWRITE = (
    "ERP stores purchase orders, goods receipts and invoice postings for "
    "matching against mailbox files."
)
NUMBERED_TITLE_39 = "Manual matching of 1.200 invoices today"
NUMBERED_FIRST_REWRITE = "Manual 1200 invoice match review"
NUMBERED_SECOND_REWRITE = "Match 1.200 invoices"


def _context_spec(title: str) -> dict[str, Any]:
    payload = json.loads(CONTEXT_FIXTURE.read_text(encoding="utf-8"))
    payload["problem"]["title"] = title
    return payload


def _architecture_spec(description: str) -> dict[str, Any]:
    payload = json.loads(ARCHITECTURE_FIXTURE.read_text(encoding="utf-8"))
    payload["components"][1]["description"] = description
    return payload


def _parse_target(instructions: str) -> int:
    match = re.search(r"compression target (\d+) characters", instructions)
    assert match is not None, instructions
    return int(match.group(1))


def _parse_contract(instructions: str) -> int:
    match = re.search(r"at most (\d+) characters", instructions)
    assert match is not None, instructions
    return int(match.group(1))


class RecordingExecutor:
    def __init__(self, payloads: list[dict[str, str]]) -> None:
        self._payloads = list(payloads)
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        stage: Any,
        operation: str,
        prompt_version: str,
        retry_count: int,
        request: dict[str, Any] | None = None,
    ) -> LlmUsageResult:
        assert request is not None
        index = min(len(self.calls), len(self._payloads) - 1)
        self.calls.append(
            {
                "request": copy.deepcopy(request),
                "retry_count": retry_count,
                "instructions": request["instructions"],
            }
        )
        return LlmUsageResult(
            payload=copy.deepcopy(self._payloads[index]),
            input_tokens=8,
            output_tokens=4,
        )


def _compress_with(payloads: list[dict[str, str]]) -> tuple[Any, RecordingExecutor]:
    executor = RecordingExecutor(payloads)
    client = LlmClient(model="gpt-4.1-mini", executor=executor)
    return client.compression_fields_fn(prompt_version="compression_v1"), executor


def test_live_strings_match_reported_failure_shapes() -> None:
    assert len(CONTEXT_TITLE_39) == 39
    assert len(CONTEXT_TITLE_REWRITE) <= 32
    assert CONTEXT_TITLE_REWRITE != CONTEXT_TITLE_39[:32]
    assert CONTEXT_TITLE_REWRITE != CONTEXT_TITLE_39[: len(CONTEXT_TITLE_REWRITE)]
    assert len(ARCHITECTURE_DESCRIPTION_102) == 102
    assert len(ARCHITECTURE_DESCRIPTION_REWRITE) <= 100
    assert ARCHITECTURE_DESCRIPTION_REWRITE != ARCHITECTURE_DESCRIPTION_102[:100]
    assert MAX_COMPRESSION_ATTEMPTS == 2


def test_context_01_problem_title_live_shape_compresses_without_clipping() -> None:
    original = _context_spec(CONTEXT_TITLE_39)
    provenance = copy.deepcopy(original["fieldProvenance"])
    sources = copy.deepcopy(original["sourceChapterIds"])
    compress, executor = _compress_with([{"problem.title": CONTEXT_TITLE_REWRITE}])

    result = validate_and_compress_group_a_slide_spec(original, compress_fields=compress)

    assert result.status == "VALID"
    assert result.compression_attempts == 1
    assert result.slide_spec is not None
    accepted = result.slide_spec["problem"]["title"]
    assert accepted == CONTEXT_TITLE_REWRITE
    assert len(accepted) <= 32
    assert accepted != CONTEXT_TITLE_39[:32]
    assert "…" not in accepted and "..." not in accepted
    assert result.slide_spec["fieldProvenance"] == provenance
    assert result.slide_spec["sourceChapterIds"] == sources
    instructions = executor.calls[0]["instructions"]
    assert _parse_contract(instructions) == 32
    assert _parse_target(instructions) == compression_target_length(32, 39, 1)
    assert _parse_target(instructions) < 32
    schema = executor.calls[0]["request"]["targetSchema"]["properties"]["problem.title"]
    assert schema["maxLength"] == 32
    assert executor.calls[0]["request"]["violations"][0]["limit"] == 32


def test_architecture_01_component_description_uses_same_shared_compressor() -> None:
    original = _architecture_spec(ARCHITECTURE_DESCRIPTION_102)
    provenance = copy.deepcopy(original["fieldProvenance"])
    sources = copy.deepcopy(original["sourceChapterIds"])
    compress, executor = _compress_with(
        [{"components[1].description": ARCHITECTURE_DESCRIPTION_REWRITE}]
    )

    result = validate_and_compress_group_c_slide_spec(original, compress_fields=compress)

    assert result.status == "VALID"
    assert result.compression_attempts == 1
    assert result.slide_spec is not None
    accepted = result.slide_spec["components"][1]["description"]
    assert accepted == ARCHITECTURE_DESCRIPTION_REWRITE
    assert len(accepted) <= 100
    assert accepted != ARCHITECTURE_DESCRIPTION_102[:100]
    assert result.slide_spec["fieldProvenance"] == provenance
    assert result.slide_spec["sourceChapterIds"] == sources
    instructions = executor.calls[0]["instructions"]
    assert _parse_contract(instructions) == 100
    assert _parse_target(instructions) == compression_target_length(100, 102, 1)
    assert _parse_target(instructions) < 100
    schema = executor.calls[0]["request"]["targetSchema"]["properties"][
        "components[1].description"
    ]
    assert schema["maxLength"] == 100


def test_live_overshoot_still_passes_when_prompt_targets_below_contract() -> None:
    """Model that overshoots the asked number by the live CONTEXT_01 delta."""
    target = compression_target_length(32, 39, 1)
    assert len(CONTEXT_TITLE_OVERSHOOT) == target + 7
    assert len(CONTEXT_TITLE_OVERSHOOT) <= 32
    original = _context_spec(CONTEXT_TITLE_39)
    compress, _executor = _compress_with([{"problem.title": CONTEXT_TITLE_OVERSHOOT}])

    result = validate_and_compress_group_a_slide_spec(original, compress_fields=compress)

    assert result.status == "VALID"
    assert result.slide_spec is not None
    assert result.slide_spec["problem"]["title"] == CONTEXT_TITLE_OVERSHOOT
    assert result.slide_spec["problem"]["title"] != CONTEXT_TITLE_39[:32]


def test_second_attempt_asks_for_a_stricter_target() -> None:
    compress, executor = _compress_with(
        [
            {"problem.title": CONTEXT_TITLE_39},
            {"problem.title": CONTEXT_TITLE_REWRITE},
        ]
    )

    result = validate_and_compress_group_a_slide_spec(
        _context_spec(CONTEXT_TITLE_39),
        compress_fields=compress,
    )

    assert result.status == "VALID"
    assert result.compression_attempts == 2
    assert len(executor.calls) == 2
    first_target = _parse_target(executor.calls[0]["instructions"])
    second_target = _parse_target(executor.calls[1]["instructions"])
    assert first_target < 32
    assert second_target < first_target
    assert "previous rewrite still exceeded the contract" in executor.calls[1][
        "instructions"
    ]
    assert "previous rewrite still exceeded the contract" not in executor.calls[0][
        "instructions"
    ]
    assert executor.calls[0]["retry_count"] == 0
    assert executor.calls[1]["retry_count"] == 1
    assert _parse_contract(executor.calls[1]["instructions"]) == 32
    assert result.slide_spec is not None
    assert result.slide_spec["problem"]["title"] == CONTEXT_TITLE_REWRITE


def test_two_failed_semantic_rewrites_still_fail_closed() -> None:
    compress, executor = _compress_with(
        [
            {"problem.title": CONTEXT_TITLE_39},
            {"problem.title": CONTEXT_TITLE_39},
        ]
    )

    result = validate_and_compress_group_a_slide_spec(
        _context_spec(CONTEXT_TITLE_39),
        compress_fields=compress,
    )

    assert result.status == "VALIDATION_FAILED"
    assert result.compression_attempts == MAX_COMPRESSION_ATTEMPTS
    assert result.slide_spec is None
    assert result.error_code == CONTENT_CONSTRAINT_EXCEEDED
    assert result.message is not None
    assert "after 2 compression attempts" in result.message
    assert len(executor.calls) == 2


def test_number_form_restoration_does_not_clip_and_can_retry() -> None:
    assert len(NUMBERED_TITLE_39) == 39
    assert len(NUMBERED_FIRST_REWRITE) == 32
    restored = _apply_compression_number_forms(NUMBERED_TITLE_39, NUMBERED_FIRST_REWRITE, 32)
    assert restored == "Manual 1.200 invoice match review"
    assert len(restored) == 33
    original = _context_spec(NUMBERED_TITLE_39)
    provenance = copy.deepcopy(original["fieldProvenance"])
    sources = copy.deepcopy(original["sourceChapterIds"])
    compress, executor = _compress_with(
        [
            {"problem.title": NUMBERED_FIRST_REWRITE},
            {"problem.title": NUMBERED_SECOND_REWRITE},
        ]
    )

    result = validate_and_compress_group_a_slide_spec(original, compress_fields=compress)

    assert result.status == "VALID"
    assert result.compression_attempts == 2
    assert result.slide_spec is not None
    assert result.slide_spec["problem"]["title"] == NUMBERED_SECOND_REWRITE
    assert "1.200" in result.slide_spec["problem"]["title"]
    assert "1200" not in result.slide_spec["problem"]["title"]
    assert result.slide_spec["fieldProvenance"] == provenance
    assert result.slide_spec["sourceChapterIds"] == sources
    assert result.slide_spec["problem"]["title"] != NUMBERED_TITLE_39[:32]
    assert len(executor.calls) == 2


def test_invented_digits_remain_sanitized_on_shared_compressor() -> None:
    compress, _executor = _compress_with(
        [{"problem.title": "3-way match exceptions"}]
    )

    result = validate_and_compress_group_a_slide_spec(
        _context_spec(CONTEXT_TITLE_39),
        compress_fields=compress,
    )

    assert result.status == "VALID"
    assert result.slide_spec is not None
    accepted = result.slide_spec["problem"]["title"]
    assert "3" not in accepted
    assert "three" in accepted
    assert len(accepted) <= 32


def test_shared_compressor_has_no_slice_clipping() -> None:
    from llm import client as client_module

    source = Path(client_module.__file__).read_text(encoding="utf-8")
    assert "value[:limit]" not in source
    assert "rewritten[:limit]" not in source
    assert "text[:limit]" not in source
    assert "current_value[: violation.limit]" not in source
