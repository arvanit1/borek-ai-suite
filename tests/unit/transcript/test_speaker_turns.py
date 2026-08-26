"""ES-2 — speaker-turn splitting for all four transcript formats."""

from __future__ import annotations

import io

import pytest
from docx import Document

from services.transcript.ingestion import TranscriptIngestionError
from services.transcript.speaker_turns import UNKNOWN_SPEAKER, split_speaker_turns


def _docx_bytes(*paragraphs: str) -> bytes:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_txt_one_entry_per_speaker_with_label() -> None:
    content = b"Sandra: Matching invoices is slow.\nArvanit: We can automate the clean cases."
    turns = split_speaker_turns("call.txt", content)
    assert [(t.turn_index, t.speaker, t.text) for t in turns] == [
        (0, "Sandra", "Matching invoices is slow."),
        (1, "Arvanit", "We can automate the clean cases."),
    ]


def test_txt_unlabeled_lines_continue_previous_turn() -> None:
    content = b"Sandra: First sentence.\nAnd a follow-up on the same turn.\nIT: Access is still open."
    turns = split_speaker_turns("call.txt", content)
    assert turns[0].speaker == "Sandra"
    assert turns[0].text == "First sentence. And a follow-up on the same turn."
    assert turns[1].speaker == "IT"
    assert turns[1].text == "Access is still open."


def test_txt_without_labels_uses_unknown_speaker() -> None:
    turns = split_speaker_turns("notes.txt", b"There is no speaker prefix here.")
    assert len(turns) == 1
    assert turns[0].speaker == UNKNOWN_SPEAKER
    assert turns[0].text == "There is no speaker prefix here."


def test_vtt_uses_voice_tag_as_speaker() -> None:
    raw = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.000\n"
        "<v Sandra>Invoice matching is slow</v>\n\n"
        "00:00:02.000 --> 00:00:04.000\n"
        "<v Arvanit>We should automate it</v>\n"
    )
    turns = split_speaker_turns("call.vtt", raw.encode("utf-8"))
    assert [t.speaker for t in turns] == ["Sandra", "Arvanit"]
    assert turns[0].text == "Invoice matching is slow"
    assert turns[1].text == "We should automate it"


def test_vtt_without_voice_tag_uses_unknown() -> None:
    raw = b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello from VTT\n"
    turns = split_speaker_turns("call.vtt", raw)
    assert len(turns) == 1
    assert turns[0].speaker == UNKNOWN_SPEAKER
    assert turns[0].text == "Hello from VTT"


def test_srt_one_cue_per_turn_with_name_prefix() -> None:
    raw = (
        "1\n00:00:00,000 --> 00:00:02,000\nSandra: First line\n\n"
        "2\n00:00:02,000 --> 00:00:04,000\nArvanit: Second line\n"
    )
    turns = split_speaker_turns("call.srt", raw.encode("utf-8"))
    assert [(t.speaker, t.text) for t in turns] == [
        ("Sandra", "First line"),
        ("Arvanit", "Second line"),
    ]


def test_docx_splits_labeled_paragraphs() -> None:
    content = _docx_bytes("Sandra: From Word.", "Arvanit: Confirmed.")
    turns = split_speaker_turns("call.docx", content)
    assert [(t.speaker, t.text) for t in turns] == [
        ("Sandra", "From Word."),
        ("Arvanit", "Confirmed."),
    ]


def test_unsupported_format_still_rejected() -> None:
    with pytest.raises(TranscriptIngestionError) as exc_info:
        split_speaker_turns("notes.pdf", b"not a transcript")
    assert "Unsupported transcript format" in exc_info.value.user_message
