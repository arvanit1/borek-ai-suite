"""Mailbox provider factory — fixture today, live Outlook later."""

from __future__ import annotations

from typing import Literal

from services.mailbox.contract import MailboxProvider
from services.mailbox.fixture_client import FixtureMailboxClient

ExecutionMode = Literal["fixture", "live"]


def build_mailbox_provider(execution_mode: ExecutionMode = "fixture") -> MailboxProvider:
    if execution_mode == "fixture":
        return FixtureMailboxClient()
    raise NotImplementedError(
        "Live Outlook mailbox integration is not implemented; use MAILBOX_EXECUTION_MODE=fixture."
    )
