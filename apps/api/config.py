"""API settings. Secrets come from .env — never commit the key."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")


class Settings:
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", "8000"))
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    web_origin: str = os.environ.get("WEB_ORIGIN", "http://localhost:3000")
    artifact_dir: Path = _REPO_ROOT / "generated" / "customer_reports"


settings = Settings()
REPO_ROOT = _REPO_ROOT
