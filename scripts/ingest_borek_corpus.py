#!/usr/bin/env python3
"""Ingest the bundled Borek corpus as the approved AT-59 version.

Usage:
  py -3 scripts/ingest_borek_corpus.py
  py -3 scripts/ingest_borek_corpus.py --path path/to/corpus.json

Uses the worker/service-role store so normal users stay read-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "services" / "api"
APPS_API_DIR = ROOT / "apps" / "api"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(APPS_API_DIR))
sys.path.insert(0, str(API_DIR))

load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the versioned Borek knowledge corpus")
    parser.add_argument("--path", type=Path, default=None, help="Optional corpus JSON path")
    args = parser.parse_args()

    from app.services.data import build_worker_data_store
    from services.borek_rag.corpus import bundled_corpus_mapping

    if args.path is None:
        raw = bundled_corpus_mapping()
    else:
        raw = json.loads(args.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise SystemExit("Corpus file must contain a JSON object")

    result = build_worker_data_store().ingest_approved_corpus(raw)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
