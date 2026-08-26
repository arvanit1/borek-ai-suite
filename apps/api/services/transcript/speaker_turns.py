"""ES-2 — split a normalized transcript into speaker turns.

Each turn is one utterance with a speaker label. Caption formats (.vtt / .srt)
use one cue as one turn. Plain text (.txt / .docx) uses ``Name:`` prefixes;
unlabeled lines continue the previous turn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from services.transcript.ingestion import (
    TranscriptIngestionError,
    _decode_text_bytes,
    _HTML_TAG_RE,
    _SRT_INDEX_RE,
    _TIMESTAMP_RE,
    ingest_transcript,
)

UNKNOWN_SPEAKER = "unknown"

_VOICE_TAG_RE = re.compile(r"<v\s+([^>]+)>", re.IGNORECASE)
_SPEAKER_PREFIX_RE = re.compile(
    r"^(?P<speaker>[A-Za-z][A-Za-z0-9 .'\-_]{0,80}):\s*(?P<text>.*)$"
)


@dataclass(frozen=True, slots=True)
class SpeakerTurn:
    turn_index: int
    speaker: str
    text: str


def split_speaker_turns(filename: str, content: bytes) -> list[SpeakerTurn]:
    ingested = ingest_transcript(filename, content)
    extension = ingested.extension

    if extension == ".vtt":
        raw_turns = _turns_from_cues(_decode_text_bytes(content), skip_webvtt_header=True)
    elif extension == ".srt":
        raw_turns = _turns_from_cues(_decode_text_bytes(content), skip_webvtt_header=False)
    else:
        raw_turns = _turns_from_plain_text(ingested.normalized_text)

    if not raw_turns:
        raise TranscriptIngestionError(
            "No speaker turns could be read from this transcript. "
            "Check the export and upload a .txt, .vtt, .srt, or .docx file."
        )

    return [
        SpeakerTurn(turn_index=index, speaker=speaker, text=text)
        for index, (speaker, text) in enumerate(raw_turns)
    ]


def _turns_from_cues(raw: str, *, skip_webvtt_header: bool) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    payload: list[str] = []
    in_payload = False

    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if skip_webvtt_header and stripped.upper().startswith("WEBVTT"):
            continue
        if stripped.upper().startswith("KIND:") or stripped.upper().startswith("LANGUAGE:"):
            continue
        if stripped.startswith("NOTE"):
            continue

        if not stripped:
            _flush_cue(turns, payload)
            payload = []
            in_payload = False
            continue

        if _TIMESTAMP_RE.match(stripped):
            _flush_cue(turns, payload)
            payload = []
            in_payload = True
            continue

        if not in_payload and _SRT_INDEX_RE.match(stripped):
            continue

        payload.append(stripped)
        in_payload = True

    _flush_cue(turns, payload)
    return turns


def _flush_cue(turns: list[tuple[str, str]], payload: list[str]) -> None:
    if not payload:
        return
    joined = " ".join(payload)
    speaker = UNKNOWN_SPEAKER
    voice = _VOICE_TAG_RE.search(joined)
    if voice:
        speaker = _clean_speaker(voice.group(1))
    plain = _HTML_TAG_RE.sub("", joined).strip()
    prefix = _SPEAKER_PREFIX_RE.match(plain)
    if prefix and prefix.group("text").strip():
        speaker = _clean_speaker(prefix.group("speaker"))
        plain = prefix.group("text").strip()
    if not plain:
        return
    turns.append((speaker, plain))


def _turns_from_plain_text(text: str) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    current_speaker = UNKNOWN_SPEAKER
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        body = " ".join(part for part in current_lines if part).strip()
        if body:
            turns.append((current_speaker, body))
        current_lines = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        prefix = _SPEAKER_PREFIX_RE.match(line)
        if prefix:
            flush()
            current_speaker = _clean_speaker(prefix.group("speaker"))
            remainder = prefix.group("text").strip()
            current_lines = [remainder] if remainder else []
        else:
            current_lines.append(line)

    flush()
    return turns


def _clean_speaker(label: str) -> str:
    cleaned = " ".join(label.replace("_", " ").split())
    return cleaned if cleaned else UNKNOWN_SPEAKER
