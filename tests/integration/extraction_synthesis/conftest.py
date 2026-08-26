"""Pytest config for ES-34 integration tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
load_dotenv(ROOT / ".env")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live_claude: calls Anthropic Claude live; requires ANTHROPIC_API_KEY (skipped in CI by default)",
    )


def _anthropic_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


@pytest.fixture(scope="session")
def anthropic_api_key() -> str:
    key = _anthropic_api_key()
    if not key:
        pytest.skip("ANTHROPIC_API_KEY is not set — add it to .env or the environment to run live Claude tests.")
    return key
