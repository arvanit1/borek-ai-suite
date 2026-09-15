"""BT-33 rollout allow-list — fail closed for unlisted projects."""

from __future__ import annotations

from app.config import settings


class FollowupRolloutError(RuntimeError):
    def __init__(self, project_key: str) -> None:
        super().__init__(
            f"Follow-up generation is not enabled for project '{project_key}'."
        )
        self.code = "FOLLOWUP_PROJECT_NOT_ALLOWED"
        self.retryable = False
        self.project_key = project_key


def allowed_project_keys() -> frozenset[str]:
    raw = str(settings.FOLLOWUP_ALLOWED_PROJECT_KEYS or "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def assert_followup_project_allowed(project_key: str) -> None:
    key = str(project_key or "").strip()
    if not key or key not in allowed_project_keys():
        raise FollowupRolloutError(key or "<empty>")
