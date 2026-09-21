"""Source-status and render-language checks for customer-facing slide fields.

This is a narrow deterministic guard for asserted implementation/completion and
material English prose in German slides, not general semantic entailment or translation.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import re
from typing import Any

from services.validation.compression_retry import get_value_at_path
from services.validation.source_chapter_enforcement import populated_content_leaf_paths


class ContentPolicyError(ValueError):
    code = "SLIDE_CONTENT_POLICY_FAILED"
    retryable = False


_REQUIRED_LANGUAGE: ContextVar[str | None] = ContextVar(
    "slide_render_language", default=None
)


@contextmanager
def compression_language(language: str):
    token = _REQUIRED_LANGUAGE.set(language)
    try:
        yield
    finally:
        _REQUIRED_LANGUAGE.reset(token)


def current_compression_language() -> str | None:
    return _REQUIRED_LANGUAGE.get()


def language_instruction(language: str) -> str:
    name = "German (Deutsch)" if language == "de" else "English"
    return (
        f"Required output language: {name}. Write all customer-facing prose in this "
        "language, including titles, labels, descriptions and repaired fields. "
        "Preserve company/product names, acronyms, technical terms and verbatim "
        "source quotations. Do not translate status enum values or schema keys. "
    )


STATUS_INSTRUCTION = (
    "SOURCE STATUS: Preserve the distinction between current state, proposed work, "
    "planned work, conditional recommendations, work in progress and completed "
    "implementation. Never present a proposal, recommendation or ongoing work as "
    "already implemented, deployed or completed. Each completion assertion needs "
    "explicit evidence about that same work in that field's attributed chapters. "
    "Preserve negation, conditions and future qualifiers, including during repair. "
)

_COMPLETION = re.compile(
    r"\b(?:implemented|deployed|completed|launched|finished|rolled\s+out|"
    r"implementiert(?:e[nrs]?)?|umgesetzt(?:e[nrs]?)?|eingeführt(?:e[nrs]?)?|"
    r"abgeschlossen(?:e[nrs]?)?|fertiggestellt|ausgerollt|in\s+betrieb|"
    r"in\s+production|is\s+operational|ist\s+produktiv)\b",
    re.I,
)
_NON_ASSERTION = re.compile(
    r"\b(?:not|never|no|nicht|niemals|kein\w*|ohne)\b|n['’]t\b|"
    r"\b(?:if|unless|when|wenn|falls|sofern|sobald)\b|"
    r"\b(?:will|would|should|could|might|may|must|can|soll\w*|sollte\w*|"
    r"kann|könnte\w*|muss|müsste\w*|würde\w*|werden|wird)\b|"
    r"\b(?:being|currently\s+implementing|in\s+progress|in\s+arbeit|"
    r"in\s+umsetzung|geplant|vorgeschlagen|empfohlen)\b|"
    r"\b(?:plan\w*|propos\w*|recommend\w*|intend\w*)\s+(?:to|for|that)\b|"
    r"\b(?:planned|proposed|recommended|ongoing|partially|partly|teilweise)\b|\bto\s+be\b",
    re.I,
)
_WORDS = re.compile(r"[^\W\d_]+", re.UNICODE)
_TOPIC_STOP = set(
    """the a an this that these those it its we our they their has have had
is are was were been being be already now successfully fully completely
work with for by to of in and or at as on die der das den dem des ein eine
einer einem einen eines ist sind war
waren wurde wurden hat haben hatte hatten bereits schon jetzt erfolgreich vollständig mit für von zur zum
im am und oder es sie wir unser unsere dieser diese dieses""".split()
)


def _terms(text: str) -> set[str]:
    result = set()
    for word in re.findall(r"[^\W_]+", text.casefold()):
        if word in _TOPIC_STOP:
            continue
        if word.startswith(("automat", "automatis")):
            if "stufe" in word:
                result.add("stage")
            word = "automation"
        elif word in {"system", "systems", "systeme", "systemen"}:
            word = "system"
        elif word in {"migration", "migrationen"}:
            word = "migration"
        elif word in {"implementation", "implementierung"}:
            word = "implementation"
        elif word in {"prozess", "process", "workflow"}:
            word = "process"
        elif word in {"first", "erste", "ersten", "erster", "1"}:
            word = "1"
        elif word in {"second", "zweite", "zweiten", "zweiter", "2"}:
            word = "2"
        elif word in {"stage", "stufe", "phase"}:
            word = "stage"
        result.add(word)
    return result


def _sentences(text: str) -> list[str]:
    return re.split(
        r"[.!?;\n]+|,?\s+\b(?:but|however|aber|jedoch)\b\s+|"
        r"\s+(?:and|und)\s+(?=(?:\w+\s+){1,5}"
        r"(?:is|are|was|were|has|have|ist|sind|wurde|wurden)\b)",
        text,
        flags=re.I,
    )


def _completion_subjects(text: str):
    for sentence in _sentences(text):
        match = _COMPLETION.search(sentence)
        if not match:
            continue
        # 'not only' is not a negation of the completion assertion.
        # Scope polarity to the assertion, not qualifiers such as 'without errors'
        # or a later sentence. A trailing condition still makes it conditional.
        status_text = re.sub(
            r"\b(?:not\s+only|nicht\s+nur)\b", "", sentence[: match.start()], flags=re.I
        )
        if _NON_ASSERTION.search(status_text):
            continue
        if re.search(
            r"\b(?:if|unless|when|wenn|falls|sofern|sobald|only\s+after|erst\s+nach)\b",
            sentence[match.end() :],
            re.I,
        ):
            continue
        before = sentence[: match.start()]
        # In passive assertions the work precedes the auxiliary. Dates/adverbs
        # between 'was/wurde' and 'implemented' describe the event, not its subject.
        subject_text = re.split(
            r"\b(?:is|are|was|were|has|have|had|ist|sind|war|waren|wurde|wurden)\b",
            before,
            maxsplit=1,
            flags=re.I,
        )[0]
        subject = _terms(subject_text)
        active = (
            re.search(r"\b(?:has|have|had|we|they|team)\b", before, re.I)
            and not re.search(r"\b(?:been|is|was|were|are)\b", before, re.I)
            and match.group().lower()
            in {"implemented", "deployed", "completed", "launched", "finished"}
        )
        if not subject or active:  # Active voice: 'The team implemented automation.'
            after = re.split(
                r"\b(?:with|mit|for|für)\b", sentence[match.end() :], flags=re.I
            )[0]
            subject = _terms(after)
        yield subject


def _source_strings(value: Any, *, for_completion: bool = False):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _source_strings(item, for_completion=for_completion)
    elif isinstance(value, dict):
        planned_label = re.search(
            r"\b(?:target|goal|planned|proposed|zielzustand|sollzustand|geplant)\b",
            str(value.get("label", "")),
            re.I,
        )
        if for_completion and (
            value.get("kind") in {"recommendation", "proposal", "planned"}
            or planned_label
        ):
            # A recommendation callout is not evidence of completed work, even
            # when its desired outcome uses a past participle.
            return
        if isinstance(value.get("label"), str) and isinstance(value.get("value"), str):
            yield value["label"] + " " + value["value"]
        for key, item in value.items():
            if key not in {"source_refs", "chapter_id", "block", "kind"}:
                yield from _source_strings(item, for_completion=for_completion)


_QUOTED = re.compile(r'"([^"\n]+)"|“([^”\n]+)”|„([^“\n]+)“|«([^»\n]+)»')


def _without_supported_quotes(text: str, sources: list[str]) -> str:
    def replace(match):
        quote = next(group for group in match.groups() if group is not None)
        return "" if any(quote in source for source in sources) else match.group(0)

    return _QUOTED.sub(replace, text)


_ENGLISH = set("""the and is are was were has have had been being will would should
could must each every these those this that which who their they them our your its
with from into before after without within about through while because can does do
takes needs requires receives arrives remains becomes enables ensures provides
current manual monthly challenges next steps supplier invoices processing handling
matching booking people human oversight delivered completed recommended""".split())
_GERMAN = set("""der die das den dem des ein eine einer einem einen und oder ist sind
war waren wird werden wurde wurden hat haben hatte mit für von zu zur zum im am auf
bei durch ohne über nach vor aus nicht noch bereits jeder jede dieses diese dieser
soll sollen kann können muss müssen erhält dauert benötigt erfolgt bleibt ermöglicht
stellt sicher manuell monatlich rechnungen bearbeitung nächste schritte""".split())
_TECHNICAL = re.compile(
    r"\b(?:human\s+in\s+the\s+loop|single\s+sign[ -]on|"
    r"proof\s+of\s+concept|state\s+of\s+the\s+art|"
    r"end[ -]to[ -]end|as[ -]is|to[ -]be)\b",
    re.I,
)


def _material_english(text: str) -> bool:
    for sentence in _sentences(_TECHNICAL.sub("", text)):
        words = [w.casefold() for w in _WORDS.findall(sentence)]
        english = sum(w in _ENGLISH for w in words)
        german = sum(w in _GERMAN for w in words)
        if len(words) >= 4 and english >= 3 and english > 2 * german:
            return True
    return False


def validate_content_policy(
    slide_spec: dict, chapters: tuple[dict, ...], language: str = "en"
) -> None:
    by_id = {str(ch["chapter_id"]): ch for ch in chapters}
    attribution = {
        entry["path"]: entry["sourceChapterIds"]
        for entry in slide_spec.get("fieldProvenance", [])
    }
    for path in populated_content_leaf_paths(slide_spec):
        value = get_value_at_path(slide_spec, path)
        if not isinstance(value, str):
            continue
        # Never use an unrelated root chapter to justify a field assertion.
        sources = [
            text
            for cid in attribution.get(path, [])
            for text in _source_strings(by_id.get(str(cid), {}))
        ]
        prose = _without_supported_quotes(value, sources)
        for subject in _completion_subjects(prose):
            evidence_subjects = [
                terms
                for cid in attribution.get(path, [])
                for source in _source_strings(
                    by_id.get(str(cid), {}), for_completion=True
                )
                for terms in _completion_subjects(source)
            ]
            # Equal normalized work subjects prevent completion of 'automation
            # documentation' or another stage from proving completed automation.
            if not subject or subject not in evidence_subjects:
                raise ContentPolicyError(
                    f"Unsupported implementation/completion assertion at {path}: "
                    "the field-attributed chapters do not explicitly establish completion of this work. "
                    "Preserve the source's current, planned, conditional or in-progress status."
                )
        if language == "de" and _material_english(prose):
            raise ContentPolicyError(
                f"German output required at {path}: material English prose detected. "
                "Rewrite in German while preserving source facts, status and provenance."
            )
