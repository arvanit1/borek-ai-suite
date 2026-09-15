"""BT-33 follow-up rendering errors."""

from __future__ import annotations


class FollowupRenderError(ValueError):
    """Classified renderer failure — fail closed, no silent truncation."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
