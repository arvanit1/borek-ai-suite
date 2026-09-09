"""AT-59 / ES-39 corpus identity frozen in packages/contracts/knowledge_corpus.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CONTRACT_PATH = (
    Path(__file__).resolve().parents[4] / "packages" / "contracts" / "knowledge_corpus.json"
)


@lru_cache(maxsize=1)
def knowledge_corpus_contract() -> dict[str, Any]:
    raw = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("knowledge_corpus.json must be an object.")
    return raw


def live_corpus_id() -> str:
    return str(knowledge_corpus_contract()["live"]["corpus_id"])


def demo_corpus_id() -> str:
    return str(knowledge_corpus_contract()["demo"]["corpus_id"])


def live_provenance_marker() -> str:
    return str(knowledge_corpus_contract()["live"]["provenance_marker"])


def demo_provenance_marker() -> str:
    return str(knowledge_corpus_contract()["demo"]["provenance_marker"])


def retrieval_stage_name() -> str:
    return str(knowledge_corpus_contract()["retrieval_stage"]["stage"])


def provenance_marker_for(corpus_id: str) -> str:
    if corpus_id == demo_corpus_id():
        return demo_provenance_marker()
    return live_provenance_marker()


def is_demo_corpus(corpus_id: str | None) -> bool:
    return str(corpus_id or "").strip() == demo_corpus_id()
