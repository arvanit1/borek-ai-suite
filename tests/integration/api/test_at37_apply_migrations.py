"""AT-37: live clean-reapply of repository migrations."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.integration


def test_apply_migrations_is_safe_to_reapply() -> None:
    if os.getenv("RUN_SUPABASE_INTEGRATION") != "1":
        pytest.skip("Set RUN_SUPABASE_INTEGRATION=1 to reapply hosted migrations")

    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from apply_migrations import apply, database_url

    url = database_url()
    hostname = urlparse(url).hostname
    if not url or hostname in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("Hosted DATABASE_URL / SUPABASE_DB_PASSWORD required")

    apply(url, times=2)
