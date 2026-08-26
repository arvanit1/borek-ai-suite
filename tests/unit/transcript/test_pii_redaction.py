"""ES-4 — PII redaction before LLM calls."""

from __future__ import annotations

from services.transcript.pii_redaction import (
    is_redaction_enabled,
    load_pii_redaction_config,
    redact_turns_for_llm,
)
from services.transcript.speaker_turns import UNKNOWN_SPEAKER, SpeakerTurn, split_speaker_turns


def _turns(*pairs: tuple[str, str]) -> list[SpeakerTurn]:
    return [
        SpeakerTurn(turn_index=index, speaker=speaker, text=text)
        for index, (speaker, text) in enumerate(pairs)
    ]


def test_config_defaults_redaction_on() -> None:
    config = load_pii_redaction_config()
    assert config.default_enabled is True
    assert is_redaction_enabled() is True
    assert is_redaction_enabled(False) is False
    assert is_redaction_enabled(True) is True


def test_emails_phones_and_names_are_stripped() -> None:
    original = _turns(
        (
            "Sandra",
            "Call Sandra at +49 170 1234567 or sandra.ap@client.de about the ERP.",
        ),
        ("Arvanit", "Arvanit will confirm access."),
    )
    redacted = redact_turns_for_llm(original, enabled=True)

    assert original[0].text.startswith("Call Sandra")
    assert redacted[0].speaker == "SPEAKER_1"
    assert redacted[1].speaker == "SPEAKER_2"
    assert "Sandra" not in redacted[0].text
    assert "Arvanit" not in redacted[1].text
    assert "sandra.ap@client.de" not in redacted[0].text
    assert "[EMAIL]" in redacted[0].text
    assert "+49 170 1234567" not in redacted[0].text
    assert "[PHONE]" in redacted[0].text
    assert redacted[0].text.endswith("about the ERP.")


def test_third_party_person_name_pair_is_redacted() -> None:
    original = _turns(
        ("SPEAKER_1", "Please ask Alice Johnson to approve the sandbox access."),
    )
    redacted = redact_turns_for_llm(original, enabled=True)
    joined = redacted[0].text
    assert "Alice Johnson" not in joined
    assert "[NAME]" in joined


def test_all_caps_name_pair_is_redacted() -> None:
    original = _turns(
        ("SPEAKER_1", "Escalate to ALICE JOHNSON if access is blocked."),
    )
    redacted = redact_turns_for_llm(original, enabled=True)
    assert "ALICE JOHNSON" not in redacted[0].text
    assert "[NAME]" in redacted[0].text


def test_unicode_name_pair_is_redacted() -> None:
    original = _turns(
        ("SPEAKER_1", "Loop in Élodie Durand for the French entity."),
    )
    redacted = redact_turns_for_llm(original, enabled=True)
    assert "Élodie Durand" not in redacted[0].text
    assert "[NAME]" in redacted[0].text


def test_single_speaker_first_name_is_redacted() -> None:
    original = _turns(
        ("Alice", "Alice will send the sandbox credentials tomorrow."),
    )
    redacted = redact_turns_for_llm(original, enabled=True)
    assert redacted[0].speaker == "SPEAKER_1"
    assert "Alice" not in redacted[0].text
    assert "SPEAKER_1" in redacted[0].text


def test_third_party_single_first_name_is_redacted() -> None:
    original = _turns(
        ("SPEAKER_1", "Please ask Alice to approve the sandbox access."),
    )
    redacted = redact_turns_for_llm(original, enabled=True)
    assert "Alice" not in redacted[0].text
    assert "[NAME]" in redacted[0].text


def test_named_systems_and_processes_are_preserved() -> None:
    samples = [
        "Oracle Fusion is the system of record.",
        "ServiceNow handles exceptions.",
        "Microsoft Dynamics 365 handles posting.",
        "Invoice Processing starts Monday.",
    ]
    for text in samples:
        redacted = redact_turns_for_llm(_turns(("SPEAKER_1", text)), enabled=True)[0].text
        assert redacted == text, f"Business term stripped from: {text!r} -> {redacted!r}"
        assert "[NAME]" not in redacted


def test_disabled_per_opportunity_leaves_pii() -> None:
    original = _turns(("Sandra", "Email sandra@client.de or +1 555 010 2233."))
    redacted = redact_turns_for_llm(original, enabled=False)
    assert redacted[0].speaker == "Sandra"
    assert "sandra@client.de" in redacted[0].text
    assert "+1 555 010 2233" in redacted[0].text


def test_unknown_speaker_is_not_renamed() -> None:
    original = _turns((UNKNOWN_SPEAKER, "No name label here."))
    redacted = redact_turns_for_llm(original, enabled=True)
    assert redacted[0].speaker == UNKNOWN_SPEAKER


def test_pipeline_from_txt_upload() -> None:
    content = b"Sandra: Reach me at sandra@client.de\nArvanit: Use +49 30 123456."
    turns = split_speaker_turns("call.txt", content)
    redacted = redact_turns_for_llm(turns, enabled=True)
    joined = " ".join(turn.text for turn in redacted)
    assert "sandra@client.de" not in joined
    assert [turn.speaker for turn in redacted] == ["SPEAKER_1", "SPEAKER_2"]
