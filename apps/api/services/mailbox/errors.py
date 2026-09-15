"""Mailbox provider errors — BT-33 safety boundary."""

from __future__ import annotations


class MailboxError(RuntimeError):
    def __init__(self, message: str, *, code: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable


class MailboxSendForbiddenError(MailboxError):
    """BT-33 never auto-sends; send is forbidden from the generation pipeline."""

    def __init__(self, message: str = "Sending follow-up email is forbidden from BT-33.") -> None:
        super().__init__(message, code="FOLLOWUP_SEND_FORBIDDEN", retryable=False)


class MailboxClientRecipientForbiddenError(MailboxError):
    """Unreviewed drafts must not be addressed to the client."""

    def __init__(
        self,
        message: str = "Client recipient is forbidden before MS-32 review.",
    ) -> None:
        super().__init__(message, code="FOLLOWUP_CLIENT_UNREVIEWED", retryable=False)
