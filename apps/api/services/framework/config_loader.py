"""Load engine and voice config from /config. Never hardcode weights or tone."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_DIR = _REPO_ROOT / "config"


def repo_root() -> Path:
    return _REPO_ROOT


@lru_cache(maxsize=16)
def load_json_config(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=16)
def load_yaml_config(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def scoring_config() -> dict[str, Any]:
    return load_json_config("scoring.config.json")


def estimation_config() -> dict[str, Any]:
    return load_json_config("estimation.config.json")


def business_case_config() -> dict[str, Any]:
    return load_json_config("business_case.config.json")


def run_cost_config() -> dict[str, Any]:
    return load_json_config("run_cost.config.json")


def tone_voice() -> dict[str, Any]:
    return load_yaml_config("tone_voice.yaml")


def glossary() -> dict[str, Any]:
    return load_yaml_config("glossary.yaml")
