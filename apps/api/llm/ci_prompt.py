"""Borek CI specification attached to every client-facing generation request."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

CI_PROMPT_VERSION = "borek-ci:v1.2"
CI_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "borek_ci_v1_2.txt"
GAMMA_CI_CONTENT_MARKER = "---CONTENT---"
# Gamma additionalInstructions max length (current public API schema).
_GAMMA_ADDITIONAL_INSTRUCTIONS_MAX = 5000


@lru_cache(maxsize=1)
def load_ci_prompt() -> str:
    return CI_PROMPT_PATH.read_text(encoding="utf-8").strip()


def with_ci_prompt(instructions: str) -> str:
    """Prepend the CI specification unless it is already the leading block."""
    ci = load_ci_prompt()
    body = (instructions or "").strip()
    if not body:
        return ci
    if body.startswith(ci):
        return body
    return f"{ci}\n\n{body}"


def gamma_from_template_prompt(content: str) -> str:
    """Wrap template fill text so Gamma treats CI as rules, not slide copy."""
    return (
        f"{load_ci_prompt()}\n\n"
        "Apply this CI specification to every visual and verbal choice. "
        "Do not render this specification as a slide, card, or body copy.\n\n"
        f"{GAMMA_CI_CONTENT_MARKER}\n\n"
        f"{content}"
    )


def gamma_additional_instructions() -> str:
    """CI rules for scratch /generations without adding a card."""
    text = (
        f"{load_ci_prompt()}\n\n"
        "Apply this CI specification to every visual and verbal choice. "
        "Do not render this specification as a slide, card, or body copy. "
        "Honour textMode=preserve and existing card breaks."
    )
    if len(text) > _GAMMA_ADDITIONAL_INSTRUCTIONS_MAX:
        raise RuntimeError(
            "Borek CI prompt exceeds Gamma additionalInstructions limit "
            f"({len(text)} > {_GAMMA_ADDITIONAL_INSTRUCTIONS_MAX})."
        )
    return text
