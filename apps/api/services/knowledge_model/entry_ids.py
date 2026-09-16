"""Stable server-owned identities for atomic KnowledgeModel evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from services.knowledge_model.source_refs import KNOWLEDGE_BUCKETS


def ensure_knowledge_entry_ids(model: dict[str, Any]) -> dict[str, Any]:
    transcript_id = str(model.get("transcript_id") or "")
    for bucket in KNOWLEDGE_BUCKETS:
        for entry in model.get(bucket) or []:
            if not isinstance(entry, dict):
                continue
            refs = sorted(
                (
                    str(ref.get("conversation_id") or ""),
                    str(ref.get("speaker_role") or ""),
                    str(ref.get("excerpt_pointer") or ""),
                )
                for ref in entry.get("source_refs") or []
                if isinstance(ref, dict)
            )
            identity = {
                "transcript_id": transcript_id,
                "bucket": bucket,
                "statement": " ".join(str(entry.get("statement") or "").split()).casefold(),
                "source_refs": refs,
            }
            digest = hashlib.sha256(
                json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()[:24]
            entry["entry_id"] = f"KE-{digest}"
    return model
