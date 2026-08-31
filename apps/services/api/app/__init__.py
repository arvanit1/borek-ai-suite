"""Borek AI Suite FastAPI application (AT-34+)."""

from __future__ import annotations

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]
_APPS_API_DIR = Path(__file__).resolve().parents[3] / "api"
_REPO_ROOT = Path(__file__).resolve().parents[4]

for _path in (_REPO_ROOT, _APPS_API_DIR, _APP_DIR):
    _resolved = str(_path)
    if _resolved not in sys.path:
        sys.path.insert(0, _resolved)
