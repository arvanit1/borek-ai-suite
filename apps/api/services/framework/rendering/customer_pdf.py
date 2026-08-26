"""Customer Framework Report PDF — structure, chapter order, tables, score bars."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib.utils import simpleSplit
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.framework.customer_view import resolve_customer_view
from services.framework.eligibility import RenderBlocked
from services.framework.guardrails import strip_citations

NAVY = HexColor("#0E1C36")
NAVY_MID = HexColor("#1B3358")
GOLD = HexColor("#C4A35A")
INK = HexColor("#1C1916")
MUTED = HexColor("#5C574F")
RULE = HexColor("#D9D2C5")
PAPER = HexColor("#F6F3EE")
GREEN = HexColor("#2F6F4E")
AMBER = HexColor("#B86A1A")
RED = HexColor("#8B2E2E")
CARD = HexColor("#FFFFFF")
LANE_AGENT = HexColor("#1B3358")
LANE_HUMAN = HexColor("#C4A35A")
LANE_SYSTEM = HexColor("#5C574F")
LANE_DECISION = HexColor("#7A3E12")

_PDF_LABELS = {
    "en": {
        "framework_title": "Automation Framework",
        "report_title": "Customer Framework Report v2",
        "footer_left": "Borek AI Suite · Customer Framework Report · Confidential",
        "closing": (
            "This document was generated automatically by the Borek AI Suite Framework Engine "
            "from the confirmed conversation data. Changes can be submitted via the review "
            "conversation — the report is then regenerated and versioned."
        ),
        "cover_kicker": "Borek Solutions Group · boreksolutions.de · Confidential",
        "automation_framework": "Automation Framework",
    },
    "de": {
        "framework_title": "Automatisierungs-Framework",
        "report_title": "Kunden-Framework-Bericht v2",
        "footer_left": "Borek AI Suite · Kunden-Framework-Bericht · Vertraulich",
        "closing": (
            "Dieses Dokument wurde automatisch durch die Borek AI Suite Framework Engine "
            "aus den bestätigten Gesprächsdaten erstellt. Änderungen können über das Review-Gespräch "
            "eingereicht werden — der Bericht wird dann neu erzeugt und versioniert."
        ),
        "cover_kicker": "Borek Solutions Group · boreksolutions.de · Vertraulich",
        "automation_framework": "Automatisierungs-Framework",
    },
}


class ScoreBar(Flowable):
    def __init__(self, name: str, score: float, explanation: str, band: str, width: float) -> None:
        super().__init__()
        self.name = name
        self.score = float(score)
        self.explanation = explanation
        self.band = band
        self.width = width
        self.height = 42

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(NAVY)
        c.roundRect(0, 12, self.width, 28, 3, fill=1, stroke=0)
        fill_w = max(8, self.width * min(self.score, 100) / 100)
        c.setFillColor(_score_color(self.score))
        c.roundRect(0, 12, fill_w, 28, 3, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Times-Bold", 9)
        c.drawString(8, 22, self.name.upper())
        c.drawRightString(self.width - 8, 22, f"{int(self.score)}/100")
        c.setFillColor(MUTED)
        c.setFont("Times-Italic", 8)
        c.drawString(0, 2, f"{self.band} — {self.explanation[:110]}")


class ProcessFlow(Flowable):
    def __init__(self, block: dict[str, Any], width: float) -> None:
        super().__init__()
        self.nodes = list(block.get("nodes") or [])
        self.edges = list(block.get("edges") or [])
        self.width = width
        self.box_w = 42 * mm
        self.box_h = 22 * mm
        self.gap = 6 * mm
        per_row = max(1, int((width + self.gap) // (self.box_w + self.gap)))
        rows = (len(self.nodes) + per_row - 1) // per_row if self.nodes else 1
        self.per_row = per_row
        self.height = rows * (self.box_h + 10 * mm) + 8 * mm

    def draw(self) -> None:
        c = self.canv
        positions: dict[str, tuple[float, float]] = {}
        for index, node in enumerate(self.nodes):
            col = index % self.per_row
            row = index // self.per_row
            x = col * (self.box_w + self.gap)
            y = self.height - (row + 1) * (self.box_h + 10 * mm)
            positions[str(node.get("id"))] = (x, y)
            kind = str(node.get("kind") or "system")
            color = {
                "agent": LANE_AGENT,
                "human": LANE_HUMAN,
                "system": LANE_SYSTEM,
                "decision": LANE_DECISION,
                "start_end": GOLD,
            }.get(kind, LANE_SYSTEM)
            c.setFillColor(color)
            if kind == "decision":
                c.saveState()
                path = c.beginPath()
                path.moveTo(x + self.box_w / 2, y + self.box_h)
                path.lineTo(x + self.box_w, y + self.box_h / 2)
                path.lineTo(x + self.box_w / 2, y)
                path.lineTo(x, y + self.box_h / 2)
                path.close()
                c.drawPath(path, fill=1, stroke=0)
                c.restoreState()
            else:
                c.roundRect(x, y, self.box_w, self.box_h, 4, fill=1, stroke=0)
            c.setFillColor(white if kind != "human" else NAVY)
            c.setFont("Times-Bold", 6.5)
            label = str(node.get("label") or "")
            lines = simpleSplit(label, "Times-Bold", 6.5, self.box_w - 3 * mm)[:4]
            if not lines:
                lines = [""]
            text_h = 7
            start_y = y + self.box_h / 2 + (len(lines) - 1) * text_h / 2 - 2
            for index, line in enumerate(lines):
                c.drawCentredString(x + self.box_w / 2, start_y - index * text_h, line)
        c.setStrokeColor(NAVY)
        c.setLineWidth(0.8)
        for edge in self.edges:
            start = positions.get(str(edge.get("from")))
            end = positions.get(str(edge.get("to")))
            if not start or not end:
                continue
            x1, y1 = start[0] + self.box_w, start[1] + self.box_h / 2
            x2, y2 = end[0], end[1] + self.box_h / 2
            c.line(x1, y1, x2, y2)


def render_customer_pdf(framework: dict[str, Any], *, lang: str = "en") -> bytes:
    decision = framework.get("render") or {}
    if decision.get("allowed") is False:
        raise RenderBlocked(
            decision.get("reason") or "Customer report is not rendered below build-readiness 60.",
            int((framework.get("quality_scores") or {}).get("build_readiness") or 0),
        )
    view = resolve_customer_view(framework, lang=lang)
    labels = _PDF_LABELS.get(lang, _PDF_LABELS["en"])
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=f"Customer Framework Report — {view.get('title', '')}",
        author="Borek AI Suite",
    )
    styles = _styles()
    story: list[Any] = []
    story.extend(_cover(view, styles, lang, labels))
    story.append(PageBreak())
    if decision.get("assumptions_banner"):
        story.append(_banner(styles, lang, str(decision.get("band") or "")))
        story.append(Spacer(1, 6 * mm))
    for chapter in view.get("chapters") or []:
        story.extend(_chapter(chapter, styles, view))
        story.append(Spacer(1, 4 * mm))
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            strip_citations(labels["closing"]),
            styles["muted"],
        )
    )

    def _header_footer(canvas, doc_obj) -> None:  # noqa: ANN001
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 10 * mm, A4[0], 10 * mm, fill=1, stroke=0)
        canvas.setFillColor(GOLD)
        canvas.rect(0, A4[1] - 10.8 * mm, A4[0], 0.8 * mm, fill=1, stroke=0)
        canvas.setFillColor(white)
        canvas.setFont("Times-Roman", 8)
        title = str(view.get("title") or "Customer Framework Report")
        canvas.drawString(16 * mm, A4[1] - 7 * mm, f"{labels['framework_title']} · {title}")
        canvas.drawRightString(A4[0] - 16 * mm, A4[1] - 7 * mm, labels["report_title"])
        canvas.setFillColor(PAPER)
        canvas.rect(0, 0, A4[0], 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(MUTED)
        canvas.setFont("Times-Roman", 8)
        fw_id = view.get("id") or view.get("framework_id") or ""
        version = view.get("version") or 1
        page_label = "Seite" if lang == "de" else "Page"
        canvas.drawString(16 * mm, 5 * mm, labels["footer_left"])
        canvas.drawRightString(
            A4[0] - 16 * mm,
            5 * mm,
            f"{fw_id} · v{version} · {page_label} {doc_obj.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buffer.getvalue()


def write_customer_pdf(framework: dict[str, Any], path: Path, *, lang: str = "en") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_customer_pdf(framework, lang=lang))
    return path


def _cover(view: dict[str, Any], styles: dict[str, ParagraphStyle], lang: str, labels: dict[str, str]) -> list[Any]:
    cover = view.get("cover") or {}
    scores = view.get("quality_scores") or {}
    story: list[Any] = [
        Spacer(1, 8 * mm),
        Paragraph(labels["cover_kicker"], styles["kicker"]),
        Spacer(1, 10 * mm),
        Paragraph(labels["automation_framework"], styles["cover_kicker"]),
        Paragraph(strip_citations(str(view.get("title") or "Untitled opportunity")), styles["cover_title"]),
        Spacer(1, 4 * mm),
        Paragraph(
            strip_citations(
                cover.get("tagline")
                or "What gets automated, why, how it works, what it returns — and how trustworthy the data behind it is."
            ),
            styles["cover_lead"],
        ),
        Spacer(1, 8 * mm),
        _meta_table(
            [
                ["Opportunity", str(view.get("opportunity_id") or "")],
                ["Department", str(view.get("department") or "")],
                ["Sources", strip_citations(str(cover.get("sources_line") or ""))],
                [
                    "Status",
                    f"{cover.get('status_label') or view.get('readiness_band', '')} · "
                    f"build-readiness {scores.get('build_readiness', '')}/100",
                ],
                [
                    "Priority",
                    f"{scores.get('opportunity_rating', '')}/100 · rank {view.get('priority_rank') or '—'}",
                ],
                ["Document type", "Customer Framework Report v2 · generated by the Borek AI Suite"],
                ["Version / date", f"v{view.get('version', 1)} · {(view.get('generation_meta') or {}).get('generated_at', '')}"],
                ["Language", lang.upper()],
            ]
        ),
    ]
    return story


def _banner(styles: dict[str, ParagraphStyle], lang: str, band: str) -> Any:
    if band == "ready_to_build":
        text = (
            "Assumptions apply. Open items are listed in chapter 11. They do not block this report."
            if lang != "de"
            else "Es gelten Annahmen. Offene Punkte stehen in Kapitel 11. Sie blockieren diesen Bericht nicht."
        )
    else:
        text = (
            "Assumptions apply. Build-readiness is between 60 and 80. "
            "Read every open item in chapter 11 before you decide."
            if lang != "de"
            else "Es gelten Annahmen. Die Build-Readiness liegt zwischen 60 und 80. "
            "Lesen Sie jedes offene Thema in Kapitel 11, bevor Sie entscheiden."
        )
    table = Table([[Paragraph(f"<b>Assumptions banner</b> — {text}", styles["banner"])]], colWidths=[178 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F3E6C8")),
                ("BOX", (0, 0), (-1, -1), 0.6, GOLD),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _chapter(chapter: dict[str, Any], styles: dict[str, ParagraphStyle], view: dict[str, Any]) -> list[Any]:
    cid = chapter.get("chapter_id")
    title = chapter.get("title")
    parts: list[Any] = [
        Paragraph(f"{cid} {strip_citations(str(title))}", styles["h1"]),
        Spacer(1, 2 * mm),
    ]
    body = chapter.get("body")
    if isinstance(body, str):
        parts.append(Paragraph(strip_citations(body), styles["body"]))
        return parts
    for block in body or []:
        if not isinstance(block, dict):
            continue
        parts.extend(_render_block(block, styles, view))
        parts.append(Spacer(1, 2.5 * mm))
    return parts


def _render_block(block: dict[str, Any], styles: dict[str, ParagraphStyle], view: dict[str, Any]) -> list[Any]:
    kind = block.get("block")
    if kind == "prose":
        return [Paragraph(strip_citations(str(block.get("text") or "")), styles["body"])]
    if kind == "bullets":
        items = [
            ListItem(Paragraph(strip_citations(str(item)), styles["body"]), leftIndent=8, bulletColor=GOLD)
            for item in block.get("items") or []
        ]
        return [ListFlowable(items, bulletType="bullet", start="•", leftIndent=12)]
    if kind == "callout":
        label = str(block.get("kind") or "note").title()
        table = Table(
            [[Paragraph(f"<b>{label}.</b> {strip_citations(str(block.get('text') or ''))}", styles["body"])]],
            colWidths=[178 * mm],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HexColor("#EEF2F7")),
                    ("BOX", (0, 0), (-1, -1), 0.4, NAVY_MID),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return [table]
    if kind == "kv_rows":
        caption = strip_citations(str(block.get("caption") or ""))
        rows = [[strip_citations(str(row.get("label") or "")), strip_citations(str(row.get("value") or ""))] for row in block.get("rows") or []]
        return _kv_table(caption, rows, styles)
    if kind == "table":
        return [_data_table(block, styles)]
    if kind == "process_flow":
        caption = strip_citations(str(block.get("caption") or "Process"))
        return [Paragraph(caption, styles["caption"]), ProcessFlow(block, 178 * mm), _legend(styles)]
    if kind == "score_bars":
        bars = []
        for item in block.get("items") or []:
            bars.append(
                ScoreBar(
                    str(item.get("name") or ""),
                    float(item.get("score") or 0),
                    strip_citations(str(item.get("explanation") or "")),
                    str(item.get("band") or ""),
                    178 * mm,
                )
            )
            bars.append(Spacer(1, 3 * mm))
        return bars
    if kind == "timeline":
        weeks = block.get("weeks") or []
        data = [[Paragraph(f"<b>{week.get('id')}</b>", styles["th"]) for week in weeks]]
        data.append(
            [
                Paragraph("<br/>".join(strip_citations(str(item)) for item in week.get("items") or []), styles["td"])
                for week in weeks
            ]
        )
        table = Table(data, colWidths=[178 * mm / max(len(weeks), 1)] * max(len(weeks), 1))
        table.setStyle(_table_style())
        return [table]
    if kind == "ai_split":
        used = "<br/>".join(f"• {strip_citations(str(item))}" for item in block.get("used_for") or [])
        not_used = "<br/>".join(f"• {strip_citations(str(item))}" for item in block.get("not_used_for") or [])
        table = Table(
            [
                [Paragraph("<b>AI is used for</b>", styles["th"]), Paragraph("<b>AI is NOT used for</b>", styles["th"])],
                [Paragraph(used, styles["td"]), Paragraph(not_used, styles["td"])],
            ],
            colWidths=[89 * mm, 89 * mm],
        )
        table.setStyle(_table_style())
        return [table]
    if kind == "sensitivity":
        rows = [[strip_citations(str(row.get("label") or "")), strip_citations(str(row.get("detail") or ""))] for row in block.get("rows") or []]
        return _kv_table("Sensitivity (range instead of a point value)", rows, styles)
    if kind == "glossary":
        rows = [[strip_citations(str(term.get("term") or "")), strip_citations(str(term.get("meaning") or ""))] for term in block.get("terms") or []]
        return _kv_table("Glossary", rows, styles)
    return []


def _legend(styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(
        "<font color='#1B3358'><b>■</b></font> Agent step &nbsp; "
        "<font color='#C4A35A'><b>■</b></font> Human step &nbsp; "
        "<font color='#5C574F'><b>■</b></font> System &nbsp; "
        "<font color='#7A3E12'><b>◆</b></font> Decision",
        styles["muted"],
    )


def _kv_table(caption: str, rows: list[list[str]], styles: dict[str, ParagraphStyle]) -> list[Any]:
    data = [[Paragraph("<b>Item</b>", styles["th"]), Paragraph("<b>Detail</b>", styles["th"])]]
    for label, value in rows:
        data.append([Paragraph(label, styles["td_strong"]), Paragraph(value, styles["td"])])
    table = Table(data, colWidths=[48 * mm, 130 * mm])
    table.setStyle(_table_style())
    parts: list[Any] = []
    if caption:
        parts.append(Paragraph(caption, styles["caption"]))
    parts.append(table)
    return parts


def _data_table(block: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Any:
    columns = [strip_citations(str(col)) for col in block.get("columns") or []]
    width = 178 * mm
    col_w = [width / max(len(columns), 1)] * max(len(columns), 1)
    header = [Paragraph(f"<b>{col}</b>", styles["th"]) for col in columns]
    data = [header]
    for row in block.get("rows") or []:
        data.append([Paragraph(strip_citations(str(cell)), styles["td"]) for cell in row])
    table = Table(data, colWidths=col_w, repeatRows=1)
    table.setStyle(_table_style())
    return KeepTogether([Paragraph(strip_citations(str(block.get("caption") or "")), styles["caption"]), table] if block.get("caption") else [table])


def _meta_table(rows: list[list[str]]) -> Table:
    styles = _styles()
    data = [
        [Paragraph(f"<b>{label}</b>", styles["td_strong"]), Paragraph(value, styles["td"])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[42 * mm, 136 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), NAVY),
                ("TEXTCOLOR", (0, 0), (0, -1), white),
                ("BACKGROUND", (1, 0), (1, -1), CARD),
                ("BOX", (0, 0), (-1, -1), 0.3, RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("BACKGROUND", (0, 1), (-1, -1), CARD),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [CARD, HexColor("#F3F0EA")]),
            ("BOX", (0, 0), (-1, -1), 0.3, RULE),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle("kicker", parent=base["Normal"], fontName="Times-Italic", fontSize=9, textColor=MUTED),
        "cover_kicker": ParagraphStyle(
            "cover_kicker", parent=base["Normal"], fontName="Times-Bold", fontSize=12, textColor=GOLD, tracking=1
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Normal"], fontName="Times-Bold", fontSize=28, leading=32, textColor=NAVY
        ),
        "cover_lead": ParagraphStyle(
            "cover_lead", parent=base["Normal"], fontName="Times-Italic", fontSize=12, leading=16, textColor=INK
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=14,
            leading=18,
            textColor=NAVY,
            spaceBefore=4,
            borderPadding=3,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Times-Roman", fontSize=10, leading=14, textColor=INK, alignment=TA_JUSTIFY
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"], fontName="Times-Bold", fontSize=9, textColor=NAVY, spaceBefore=2, spaceAfter=3
        ),
        "muted": ParagraphStyle("muted", parent=base["Normal"], fontName="Times-Italic", fontSize=8, leading=11, textColor=MUTED),
        "th": ParagraphStyle("th", parent=base["Normal"], fontName="Times-Bold", fontSize=8, leading=11, textColor=white),
        "td": ParagraphStyle("td", parent=base["Normal"], fontName="Times-Roman", fontSize=8.5, leading=11, textColor=INK),
        "td_strong": ParagraphStyle("td_strong", parent=base["Normal"], fontName="Times-Bold", fontSize=8.5, leading=11, textColor=NAVY),
        "banner": ParagraphStyle("banner", parent=base["Normal"], fontName="Times-Roman", fontSize=9, leading=12, textColor=INK),
    }


def _score_color(score: float) -> Color:
    if score >= 80:
        return GREEN
    if score >= 60:
        return AMBER
    return RED
