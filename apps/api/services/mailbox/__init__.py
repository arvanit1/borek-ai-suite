"""BT-33 mailbox draft provider boundary."""

from services.mailbox.contract import MailboxDraftRequest, MailboxDraftResult, MailboxProvider
from services.mailbox.errors import (
    MailboxClientRecipientForbiddenError,
    MailboxError,
    MailboxSendForbiddenError,
)
from services.mailbox.fixture_client import (
    FixtureMailboxClient,
    mailbox_draft_idempotency_key,
    reset_fixture_mailbox_store,
)
from services.mailbox.provider import build_mailbox_provider

__all__ = [
    "FixtureMailboxClient",
    "MailboxClientRecipientForbiddenError",
    "MailboxDraftRequest",
    "MailboxDraftResult",
    "MailboxError",
    "MailboxProvider",
    "MailboxSendForbiddenError",
    "build_mailbox_provider",
    "mailbox_draft_idempotency_key",
    "reset_fixture_mailbox_store",
]
