"""Shared Anthropic Claude client. Temperature is pinned at 0 for synthesis."""

from __future__ import annotations

import copy
import os
from typing import Any

DEFAULT_SONNET_MODEL = "claude-sonnet-4-5"
# 14-chapter drafts can exceed the SDK's 10-minute non-streaming estimate.
REQUEST_TIMEOUT_SECONDS = 900.0
# Sonnet 4.5 structured-output ceiling. ES-5/ES-9 must use this — a lower cap
# truncates KnowledgeModel / FrameworkObject JSON (stop_reason=max_tokens).
CLAUDE_STRUCTURED_MAX_TOKENS = 64000
_MAX_TRUNCATION_RETRIES = 1
_COMPACT_RETRY = (
    "RETRY — previous tool JSON was cut off at max_tokens. Resubmit the complete "
    "object now. Keep each statement to one sentence. Do not duplicate the same "
    "fact across fields or buckets. Empty arrays are valid."
)


class ClaudeClientError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


def sonnet_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_SONNET_MODEL).strip() or DEFAULT_SONNET_MODEL


def structured_complete(
    system: str,
    user: str,
    schema: dict[str, Any],
    *,
    tool_name: str,
    tool_description: str,
    max_tokens: int = CLAUDE_STRUCTURED_MAX_TOKENS,
    temperature: float = 0,  # kept for callers; anthropic 1.x create() does not accept it
    usage_out: list[Any] | None = None,
) -> dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ClaudeClientError(
            "ANTHROPIC_API_KEY is not set. Add it to the .env file before generating a customer report."
        )

    # anthropic>=1.0 dropped the temperature kwarg on messages.create.
    _ = temperature
    tokens = max(1, int(max_tokens))
    current_user = user
    last_truncated = False

    for attempt in range(1 + _MAX_TRUNCATION_RETRIES):
        create_kwargs: dict[str, Any] = {
            "model": sonnet_model(),
            "max_tokens": tokens,
            "system": system,
            "messages": [{"role": "user", "content": current_user}],
            "tools": [
                {
                    "name": tool_name,
                    "description": tool_description,
                    "input_schema": _tool_input_schema(schema),
                }
            ],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        try:
            response = _stream_final_message(create_kwargs, api_key)
        except ClaudeClientError:
            raise
        except Exception as exc:
            raise ClaudeClientError(_public_claude_error(exc)) from exc

        if usage_out is not None:
            usage_out.append(getattr(response, "usage", None))

        if getattr(response, "stop_reason", None) == "max_tokens":
            last_truncated = True
            if attempt < _MAX_TRUNCATION_RETRIES:
                tokens = max(tokens, CLAUDE_STRUCTURED_MAX_TOKENS)
                current_user = f"{user}\n\n{_COMPACT_RETRY}"
                continue
            raise ClaudeClientError(
                "Claude output was truncated before the JSON was complete. Retry generation."
            )

        last_truncated = False
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                data = block.input
                if isinstance(data, dict):
                    return data
        raise ClaudeClientError(f"Claude did not return a {tool_name} tool payload.")

    if last_truncated:
        raise ClaudeClientError(
            "Claude output was truncated before the JSON was complete. Retry generation."
        )
    raise ClaudeClientError(f"Claude did not return a {tool_name} tool payload.")


def _stream_final_message(create_kwargs: dict[str, Any], api_key: str) -> Any:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
    with client.messages.stream(**create_kwargs) as stream:
        return stream.get_final_message()


def _public_claude_error(exc: Exception) -> str:
    text = str(exc)
    if isinstance(exc, ImportError) or "No module named 'anthropic'" in text:
        return "The anthropic package is not installed. Add it to the API environment."
    if "Streaming is required" in text:
        return "Claude needs a streaming request for the 14-chapter draft. Retry generate."
    if "api_key" in text.lower() or "authentication" in text.lower():
        return "Claude rejected the API key. Check ANTHROPIC_API_KEY in .env."
    if "rate" in text.lower() and "limit" in text.lower():
        return "Claude rate-limited the request. Wait a minute and retry generate."
    return text or "Claude request failed."


def _tool_input_schema(schema: dict[str, Any]) -> dict[str, Any]:
    cleaned = copy.deepcopy(schema)
    cleaned.pop("$schema", None)
    cleaned.pop("$id", None)
    cleaned.pop("title", None)
    cleaned.pop("description", None)
    _replace_const_with_enum(cleaned)
    return cleaned


def _replace_const_with_enum(node: Any) -> None:
    if isinstance(node, dict):
        if "const" in node and "enum" not in node:
            node["enum"] = [node.pop("const")]
        else:
            node.pop("const", None)
        for value in node.values():
            _replace_const_with_enum(value)
    elif isinstance(node, list):
        for item in node:
            _replace_const_with_enum(item)
