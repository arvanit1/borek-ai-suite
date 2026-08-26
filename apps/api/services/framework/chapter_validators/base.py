from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ChapterIssue:
    chapter_id: str
    code: str
    message: str
    hard: bool = True


class ChapterValidationError(ValueError):
    def __init__(self, issues: list[ChapterIssue]) -> None:
        self.issues = issues
        hard = [issue for issue in issues if issue.hard]
        message = "; ".join(f"ch.{issue.chapter_id} {issue.code}: {issue.message}" for issue in hard or issues)
        super().__init__(message)
        self.user_message = message


def chapter_by_id(framework: dict[str, Any], chapter_id: str) -> dict[str, Any]:
    for chapter in framework.get("chapters") or []:
        if str(chapter.get("chapter_id")) == chapter_id:
            return chapter
    raise ChapterValidationError(
        [ChapterIssue(chapter_id, "missing_chapter", f"Chapter {chapter_id} is missing.")]
    )


def chapter_blob(chapter: dict[str, Any]) -> str:
    return str(chapter.get("body") or "").lower()


def blocks_of(chapter: dict[str, Any], block_type: str) -> list[dict[str, Any]]:
    body = chapter.get("body")
    if not isinstance(body, list):
        return []
    return [block for block in body if isinstance(block, dict) and block.get("block") == block_type]
