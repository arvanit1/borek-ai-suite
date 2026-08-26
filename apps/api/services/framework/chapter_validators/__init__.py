"""ES-14..ES-27 — run every chapter acceptance check."""

from __future__ import annotations

from typing import Any, Callable

from services.framework.chapter_validators.base import (
    ChapterIssue,
    ChapterValidationError,
    chapter_by_id,
)
from . import ch00_about
from . import ch01_management_summary
from . import ch02_process_today
from . import ch03_aim_success
from . import ch04_solution_tobe
from . import ch05_how_it_works
from . import ch06_how_built
from . import ch07_client_needs
from . import ch08_security
from . import ch09_business_case
from . import ch10_complexity_timeline
from . import ch11_trustworthiness
from . import ch12_evolution_stages
from . import ch13_next_steps_glossary

Validator = Callable[[dict[str, Any], dict[str, Any]], list[ChapterIssue]]

_VALIDATORS: list[Validator] = [
    ch00_about.validate,
    ch01_management_summary.validate,
    ch02_process_today.validate,
    ch03_aim_success.validate,
    ch04_solution_tobe.validate,
    ch05_how_it_works.validate,
    ch06_how_built.validate,
    ch07_client_needs.validate,
    ch08_security.validate,
    ch09_business_case.validate,
    ch10_complexity_timeline.validate,
    ch11_trustworthiness.validate,
    ch12_evolution_stages.validate,
    ch13_next_steps_glossary.validate,
]


def validate_all_chapters(framework: dict[str, Any]) -> list[ChapterIssue]:
    issues: list[ChapterIssue] = []
    for validator in _VALIDATORS:
        issues.extend(validator(framework, chapter_by_id(framework, _chapter_id_of(validator))))
    hard = [issue for issue in issues if issue.hard]
    if hard:
        raise ChapterValidationError(issues)
    return issues


def _chapter_id_of(validator: Validator) -> str:
    module = validator.__module__.rsplit(".", 1)[-1]
    return module[2:4].lstrip("0") or "0"
