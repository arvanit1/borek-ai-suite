"""ES-1 — transcript upload validation and normalization."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from docx import Document

from services.transcript.ingestion import (
    ALLOWED_TRANSCRIPT_EXTENSIONS,
    TranscriptIngestionError,
    ingest_transcript,
)


def _docx_bytes(*paragraphs: str) -> bytes:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_allowed_extensions_match_ticket() -> None:
    assert ALLOWED_TRANSCRIPT_EXTENSIONS == {".txt", ".vtt", ".srt", ".docx"}


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("meeting.txt", b"Speaker A: Hello.\nSpeaker B: Hi."),
        (
            "meeting.vtt",
            b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello from VTT\n",
        ),
        (
            "meeting.srt",
            b"1\n00:00:00,000 --> 00:00:02,000\nHello from SRT\n",
        ),
    ],
)
def test_accepted_text_formats_normalize(filename: str, content: bytes) -> None:
    result = ingest_transcript(filename, content)
    assert result.extension == Path(filename).suffix.lower()
    assert result.normalized_text
    assert "-->" not in result.normalized_text
    assert "WEBVTT" not in result.normalized_text


def test_accepted_docx_normalizes() -> None:
    result = ingest_transcript("meeting.docx", _docx_bytes("Hello from DOCX"))
    assert result.extension == ".docx"
    assert result.normalized_text == "Hello from DOCX"


def test_txt_preserves_body() -> None:
    result = ingest_transcript("notes.TXT", b"Line one\nLine two")
    assert result.filename == "notes.TXT"
    assert result.extension == ".txt"
    assert result.normalized_text == "Line one\nLine two"


def test_vtt_strips_cues_and_tags() -> None:
    raw = (
        "WEBVTT\n\n"
        "1\n"
        "00:00:01.000 --> 00:00:03.000\n"
        "<v Sandra>Invoice matching is slow</v>\n"
    )
    result = ingest_transcript("call.vtt", raw.encode("utf-8"))
    assert result.normalized_text == "Invoice matching is slow"


def test_srt_strips_index_and_timestamps() -> None:
    raw = "1\n00:00:01,000 --> 00:00:03,000\nFirst line\n\n2\n00:00:03,000 --> 00:00:05,000\nSecond line\n"
    result = ingest_transcript("call.srt", raw.encode("utf-8"))
    assert result.normalized_text == "First line\nSecond line"


def test_docx_joins_paragraphs() -> None:
    result = ingest_transcript("call.docx", _docx_bytes("First paragraph", "Second paragraph"))
    assert result.normalized_text == "First paragraph\nSecond paragraph"


@pytest.mark.parametrize(
    "filename",
    ["notes.pdf", "audio.mp3", "notes.doc", "notes", "notes.TXT.exe"],
)
def test_unsupported_format_raises_user_facing_error(filename: str) -> None:
    with pytest.raises(TranscriptIngestionError) as exc_info:
        ingest_transcript(filename, b"not a transcript")
    message = exc_info.value.user_message
    assert "Unsupported transcript format" in message
    assert ".txt" in message
    assert ".vtt" in message
    assert ".srt" in message
    assert ".docx" in message


def test_empty_file_is_rejected() -> None:
    with pytest.raises(TranscriptIngestionError) as exc_info:
        ingest_transcript("empty.txt", b"")
    assert "empty" in exc_info.value.user_message.lower()


def test_missing_filename_is_rejected() -> None:
    with pytest.raises(TranscriptIngestionError) as exc_info:
        ingest_transcript("   ", b"hello")
    assert ".txt" in exc_info.value.user_message


def test_corrupt_docx_is_rejected() -> None:
    with pytest.raises(TranscriptIngestionError) as exc_info:
        ingest_transcript("broken.docx", b"this is not a zip")
    assert "could not be read" in exc_info.value.user_message.lower()
