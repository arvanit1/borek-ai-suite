"""Persistent framework + transcript store for the customer-report API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import settings

_STORE_ROOT = settings.artifact_dir / ".store"
_FRAMEWORKS_DIR = _STORE_ROOT / "frameworks"
_KNOWLEDGE_DIR = _STORE_ROOT / "knowledge"
_TRANSCRIPTS_DIR = _STORE_ROOT / "transcripts"
_VERSIONS_DIR = _STORE_ROOT / "versions"

_FRAMEWORKS: dict[str, dict[str, Any]] = {}
_KNOWLEDGE: dict[str, list[dict[str, Any]]] = {}
_TRANSCRIPTS: dict[str, dict[str, Any]] = {}


def _ensure_dirs() -> None:
    for path in (_FRAMEWORKS_DIR, _KNOWLEDGE_DIR, _TRANSCRIPTS_DIR, _VERSIONS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    _ensure_dirs()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _framework_path(framework_id: str) -> Path:
    return _FRAMEWORKS_DIR / f"{framework_id}.json"


def _knowledge_path(opportunity_id: str) -> Path:
    return _KNOWLEDGE_DIR / f"{opportunity_id}.json"


def _transcript_path(transcript_id: str) -> Path:
    return _TRANSCRIPTS_DIR / f"{transcript_id}.json"


def _version_path(framework_id: str, version: int) -> Path:
    return _VERSIONS_DIR / framework_id / f"v{version}.json"


def load_store_from_disk() -> None:
    """Load persisted records on API startup (ES-3)."""
    _ensure_dirs()
    for path in _FRAMEWORKS_DIR.glob("*.json"):
        framework = _read_json(path)
        key = str(framework.get("id") or framework.get("framework_id") or path.stem)
        _FRAMEWORKS[key] = framework
    for path in _KNOWLEDGE_DIR.glob("*.json"):
        _KNOWLEDGE[path.stem] = _read_json(path)
    for path in _TRANSCRIPTS_DIR.glob("*.json"):
        record = _read_json(path)
        _TRANSCRIPTS[str(record.get("transcript_id") or path.stem)] = record


def save_framework(framework: dict[str, Any]) -> dict[str, Any]:
    key = str(framework.get("id") or framework.get("framework_id"))
    _FRAMEWORKS[key] = framework
    _write_json(_framework_path(key), framework)
    return framework


def save_framework_version(framework: dict[str, Any]) -> None:
    """Persist an immutable historical version (ES-12)."""
    key = str(framework.get("id") or framework.get("framework_id"))
    version = int(framework.get("version") or 1)
    path = _version_path(key, version)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, framework)


def get_framework(framework_id: str) -> dict[str, Any] | None:
    cached = _FRAMEWORKS.get(framework_id)
    if cached is not None:
        return cached
    path = _framework_path(framework_id)
    if not path.is_file():
        return None
    framework = _read_json(path)
    _FRAMEWORKS[framework_id] = framework
    return framework


def list_frameworks() -> list[dict[str, Any]]:
    load_store_from_disk()
    return list(_FRAMEWORKS.values())


def save_knowledge(opportunity_id: str, model: dict[str, Any]) -> None:
    _KNOWLEDGE.setdefault(opportunity_id, []).append(model)
    _write_json(_knowledge_path(opportunity_id), _KNOWLEDGE[opportunity_id])


def knowledge_for(opportunity_id: str) -> list[dict[str, Any]]:
    if opportunity_id in _KNOWLEDGE:
        return list(_KNOWLEDGE[opportunity_id])
    path = _knowledge_path(opportunity_id)
    if path.is_file():
        _KNOWLEDGE[opportunity_id] = _read_json(path)
        return list(_KNOWLEDGE[opportunity_id])
    return []


def save_transcript(record: dict[str, Any]) -> dict[str, Any]:
    key = str(record["transcript_id"])
    _TRANSCRIPTS[key] = record
    _write_json(_transcript_path(key), record)
    return record


def get_transcript(transcript_id: str) -> dict[str, Any] | None:
    cached = _TRANSCRIPTS.get(transcript_id)
    if cached is not None:
        return cached
    path = _transcript_path(transcript_id)
    if not path.is_file():
        return None
    record = _read_json(path)
    _TRANSCRIPTS[transcript_id] = record
    return record
