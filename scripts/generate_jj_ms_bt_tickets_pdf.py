"""Build the Jaya / Mayank / Blenard new-ticket assignment PDF.

Source: Consolidated Team Plan v1.0 (scripts/generate_team_plan_docx.py)
plus remaining work recorded in JJ-27 and JJ-28.

Usage:  py -3 scripts/generate_jj_ms_bt_tickets_pdf.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "tickets"
    / "Pitch_Factory_New_Tickets_Jaya_Mayank_Blenard.pdf"
)

NAVY = colors.HexColor("#1B2A4A")
ACCENT = colors.HexColor("#2C567A")
PALE = colors.HexColor("#F2F4F7")
LINE = colors.HexColor("#D5DAE3")
WHITE = colors.white
MUTED = colors.HexColor("#595F6B")
JAYA = colors.HexColor("#0D1D51")
MAYANK = colors.HexColor("#1B4F72")
BLENARD = colors.HexColor("#1A5276")


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_kicker": ParagraphStyle(
            "cover_kicker",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=9,
            textColor=ACCENT,
            alignment=TA_CENTER,
            letterSpacing=1.2,
            spaceAfter=6,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=22,
            leading=26,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=11,
            leading=14,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=16,
            leading=20,
            textColor=NAVY,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            leading=13,
            textColor=NAVY,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "note": ParagraphStyle(
            "note",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=9,
            leading=12,
            textColor=MUTED,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "th": ParagraphStyle(
            "th",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=8.5,
            leading=11,
            textColor=WHITE,
        ),
        "td": ParagraphStyle(
            "td",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=8.5,
            leading=11,
            textColor=NAVY,
        ),
        "td_bold": ParagraphStyle(
            "td_bold",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=8.5,
            leading=11,
            textColor=NAVY,
        ),
        "ticket_title": ParagraphStyle(
            "ticket_title",
            parent=base["Heading3"],
            fontName="Times-Bold",
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceBefore=8,
            spaceAfter=3,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=8.5,
            leading=11,
            textColor=MUTED,
            spaceAfter=3,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "person_banner": ParagraphStyle(
            "person_banner",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=14,
            leading=18,
            textColor=WHITE,
            alignment=TA_LEFT,
        ),
        "person_sub": ParagraphStyle(
            "person_sub",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=9,
            leading=12,
            textColor=WHITE,
        ),
    }


def header_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Times-Bold", 8)
    canvas.drawString(18 * mm, A4[1] - 7.5 * mm, "Borek Pitch Factory  ·  New-direction tickets")
    canvas.setFont("Times-Roman", 8)
    canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 7.5 * mm, "Jaya  ·  Mayank  ·  Blenard")
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, A4[0], 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Times-Roman", 8)
    canvas.drawString(18 * mm, 4 * mm, "Consolidated Team Plan v1.0  ·  8 September 2026")
    canvas.drawRightString(A4[0] - 18 * mm, 4 * mm, f"Page {doc.page}")
    canvas.restoreState()


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), style)


def table(headers: list[str], rows: list[list[str]], s: dict, col_widths: list[float]) -> Table:
    head = [p(h, s["th"]) for h in headers]
    body = []
    for row in rows:
        cells = []
        for i, value in enumerate(row):
            cells.append(p(value, s["td_bold"] if i == 0 else s["td"]))
        body.append(cells)
    data = [head, *body]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), PALE))
    t.setStyle(TableStyle(style_cmds))
    return t


def person_banner(name: str, role: str, tickets: str, s: dict, fill: colors.Color) -> Table:
    inner = Table(
        [
            [p(name, s["person_banner"])],
            [p(f"{role}<br/>Tickets: {tickets}", s["person_sub"])],
        ],
        colWidths=[170 * mm],
    )
    inner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (0, 0), 10),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
            ]
        )
    )
    return inner


def ticket_block(s: dict, ticket: str, title: str, meta: str, goal: str, done: str, deps: str):
    return KeepTogether(
        [
            p(f"{ticket}  —  {title}", s["ticket_title"]),
            p(meta, s["meta"]),
            p(f"<b>Goal.</b> {goal}", s["body"]),
            p(f"<b>Done when.</b> {done}", s["body"]),
            p(f"<b>Depends on.</b> {deps}", s["note"]),
        ]
    )


def build() -> Path:
    s = styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
        title="Borek Pitch Factory (Next Steps)",
        author="Pitch Factory delivery",
    )
    usable = A4[0] - 32 * mm
    story: list = []

    story.append(p("PITCH FACTORY  ·  NEW-DIRECTION BACKLOG", s["cover_kicker"]))
    story.append(p("Borek Pitch Factory (Next Steps)", s["cover_title"]))
    story.append(
        p(
            "Jaya Joshi  ·  Mayank Somwani  ·  Blenard Tahiraj",
            s["cover_sub"],
        )
    )
    story.append(
        p(
            "Source: Consolidated Team Plan v1.0 (Head of AI direction, 3 September 2026). "
            "The plan states that ticket numbers above the existing ranges "
            "(BT-28+, JJ-26+, MS-27+) are new and were not yet in the official backlog. "
            "This document adds those tickets, the follow-ons recorded as remaining work in "
            "JJ-27 and JJ-28, the three-stage client journey (First contact, Deepening, "
            "Concretisation) with its demo data, and the earlier-range work these tickets "
            "cannot close without.",
            s["body"],
        )
    )
    story.append(
        p(
            "Closure rule: do not close until every Done when condition and required proof "
            "is satisfied. Implementation without proof is not done.",
            s["note"],
        )
    )

    story.append(p("1. Distribution at a glance", s["h1"]))
    story.append(
        p(
            "JJ-26, JJ-27 and JJ-28 have landed, so they are owned but are not workload. "
            "That leaves eighteen live items, six each. The split follows verticals rather "
            "than layers: a layered split (one person owns templates, one owns the UI, one "
            "owns orchestration) forces every single feature to cross all three people, "
            "which is exactly the coupling that has been stalling the chain.",
            s["body"],
        )
    )
    story.append(
        table(
            ["Owner", "Vertical", "Live tickets", "Count"],
            [
                [
                    "Jaya Joshi",
                    "Content grounding and deck fidelity",
                    "AT-59, ES-39, ES-40, JJ-29, JJ-30, JJ-31  (JJ-26 – JJ-28 closed)",
                    "6",
                ],
                [
                    "Mayank Somwani",
                    "User surface and filed history",
                    "AT-61, MS-27, MS-28, MS-29, MS-30, MS-31",
                    "6",
                ],
                [
                    "Blenard Tahiraj",
                    "Pipeline stages and release",
                    "AT-60, BT-28, BT-29, BT-30, BT-31, BT-32",
                    "6",
                ],
            ],
            s,
            [30 * mm, 44 * mm, usable - 90 * mm, 16 * mm],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        p(
            "Each owner also holds exactly one earlier-range leftover, chosen so that its "
            "only consumers are that owner's own tickets. AT-59 goes to Jaya because ES-39 "
            "and ES-40 are the only things that read the corpus. AT-61 goes to Mayank "
            "because MS-29 and MS-30 are the only consumers of filing metadata. AT-60 stays "
            "with Blenard because BT-28 and BT-32 depend on it directly. Nobody now waits on "
            "another owner for their own inputs.",
            s["body"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(p("2. Why these tickets", s["h1"]))
    story.append(
        p(
            "Phase 1 tickets (JJ-9, JJ-22–25, MS-24–26, BT-25–27) stay in the original "
            "continuation backlog. They are not re-opened here. The Head of AI direction "
            "adds a client pack, Borek retrieval, and Gamma as the presentation engine, and "
            "the client journey splits the output into three cumulative stages. The three "
            "owners below take the product-facing slices of that work. Platform and Framework "
            "grounding remain Arvanit's and Endrit's, except for AT-59, AT-60, AT-61, ES-39 "
            "and ES-40 — those never landed, these tickets cannot close without them, and each "
            "is now held by the owner whose own tickets are its only consumers. The table "
            "below lists the new tickets; the carried-over items appear in each owner's "
            "section with their original IDs.",
            s["body"],
        )
    )
    story.append(
        table(
            ["ID", "Title", "Phase", "P", "Owner", "Status in repo today"],
            [
                ["JJ-26", "Borek Gamma template and named slots", "2 / 4", "P0", "Jaya", "Spec + contract landed"],
                ["JJ-27", "Client logo placement rules", "4", "P0", "Jaya", "Rules + gate landed"],
                ["JJ-28", "Ready screen for either engine", "4", "P0", "Jaya", "Parity landed; previews still internal"],
                ["JJ-29", "Signed client-logo URL for Gamma", "4", "P0", "Jaya", "New — remaining from JJ-27"],
                ["JJ-30", "Rasterise Gamma PDF for previews", "4", "P1", "Jaya", "New — known gap in JJ-28"],
                ["JJ-31", "Stage profiles for the Borek template", "3 / 4", "P0", "Jaya", "New — JJ-26 assumes one output"],
                ["MS-27", "Extended intake experience", "3", "P0", "Mayank", "UI started; close against AT-58"],
                ["MS-28", "Recovery states for the new stages", "4", "P1", "Mayank", "New"],
                ["MS-29", "Archive and history view", "5", "P2", "Mayank", "New; blocked on O2 / AT-61"],
                ["MS-30", "Demo data pack (decks, rate cards, packs)", "3", "P1", "Mayank", "New — unblocks MS-29/31, BT-29/30"],
                ["MS-31", "Journey-stage selector on the landing page", "3", "P0", "Mayank", "New — three cumulative outputs"],
                ["BT-28", "Gamma rendering stage in orchestration", "4", "P0", "Blenard", "AT-60 stage exists; BT owns the chain"],
                ["BT-29", "Progress mapping for the new stages", "4", "P0", "Blenard", "Partial labels exist"],
                ["BT-30", "End-to-end gate, second edition", "5", "P0", "Blenard", "New; after BT-28/29"],
                ["BT-31", "Stage prerequisites and prior-stage context", "4", "P0", "Blenard", "New — the lock behind MS-31"],
                ["BT-32", "Egress classification and allow-list closure", "4", "P0", "Blenard", "New number for unnumbered O4 work"],
            ],
            s,
            [16 * mm, 48 * mm, 16 * mm, 12 * mm, 20 * mm, usable - 112 * mm],
        )
    )

    story.append(Spacer(1, 8))
    story.append(p("3. The three-stage client journey", s["h1"]))
    story.append(
        p(
            "The product now produces three outputs rather than one, and they are cumulative. "
            "A Deepening pitch continues the First contact pack for that client, and a "
            "Concretisation proposal continues the Deepening pitch. That is why the later two "
            "cannot simply be picked from a menu: the stage before them has to have produced a "
            "deck first, otherwise there is nothing to continue from and the deck would restart "
            "the story or invent the middle.",
            s["body"],
        )
    )
    story.append(
        table(
            ["Stage", "What it is", "Precondition", "Must not contain"],
            [
                [
                    "First contact",
                    "Generic Borek information pack",
                    "None — always available",
                    "Prices, client-specific references, client logo",
                ],
                [
                    "Deepening",
                    "Tailored pitch with references and the client logo",
                    "A completed First contact deck for the same client",
                    "Offer-grade pricing",
                ],
                [
                    "Concretisation",
                    "Priced proposal",
                    "A completed Deepening deck for the same client",
                    "Any price ES-39 did not ground, or a price not labelled indicative",
                ],
            ],
            s,
            [26 * mm, 42 * mm, 46 * mm, usable - 114 * mm],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        p(
            "The work splits three ways and none of the three parts is useful alone. MS-31 is the "
            "selector with its locked states, BT-31 is the server-side lock and the loading of the "
            "earlier stage's confirmed content, and JJ-31 turns JJ-26's single slot set into three "
            "stage profiles. MS-30 supplies the seed decks that make an unlocked state reachable in "
            "a demo before live sources exist.",
            s["body"],
        )
    )
    story.append(
        p(
            "Open decision D2 still asks whether Deepening survives review, and whether these are "
            "three profiles of one template or three templates. Both MS-31 and JJ-31 are specified "
            "so that answer is configuration rather than a rewrite.",
            s["note"],
        )
    )

    story.append(PageBreak())
    story.append(person_banner(
        "Jaya Joshi",
        "Content grounding and deck fidelity",
        "AT-59 · ES-39 · ES-40 · JJ-29 · JJ-30 · JJ-31   (JJ-26 – JJ-28 closed)",
        s,
        JAYA,
    ))
    story.append(Spacer(1, 8))
    story.append(
        p(
            "Jaya owns everything that decides what ends up in the deck and whether it looks "
            "right: the corpus the facts come from, the grounding rule for prices, the "
            "payload built from the Framework, the stage profiles, the client logo and the "
            "previews. AT-59, ES-39 and ES-40 come to her because they are the inputs to her "
            "own tickets — left elsewhere she would be blocked on someone else for her own "
            "starting material. Her whole chain, AT-59 → ES-39 → JJ-31 and ES-40 → JJ-31, is "
            "now internal to her.",
            s["body"],
        )
    )
    story.append(
        ticket_block(
            s,
            "AT-59",
            "Live corpus and rate cards, carried over",
            "Phase 3  ·  P0  ·  CARRIED OVER, re-owned  ·  spec in the AT range",
            "Turn the retrieval corpus and rate cards into something real rather than the "
            "fixture. Rate-card content updates sit with Fiona; this is the pipeline side.",
            "ES-39 and ES-40 read live Borek facts rather than fixtures. Blenard needs only "
            "the stage name from this, so BT-29 is not blocked on it.",
            "O2 / O3 for the source of truth. Fiona owns rate-card content.",
        )
    )
    story.append(
        ticket_block(
            s,
            "ES-39",
            "Grounded prices and staffing, carried over",
            "Phase 3  ·  P0  ·  CARRIED OVER, re-owned  ·  spec in the ES range",
            "Prices and staffing come from retrieval or they do not appear. The system may "
            "explain an approved price; it may never originate one. Foundation exists, live "
            "grounding does not.",
            "Concretisation pricing in JJ-31 has provenance for every figure, and an "
            "ungrounded price is refused rather than softened.",
            "AT-59 (same owner). MS-30 needs only the demo corpus id and provenance marker.",
        )
    )
    story.append(
        ticket_block(
            s,
            "ES-40",
            "Gamma content payload, carried over",
            "Phase 4  ·  P0  ·  CARRIED OVER, re-owned  ·  the biggest single miss",
            "Build the provider payload from the confirmed Framework plus retrieved facts. "
            "Nothing downstream works without it — this is why BT-28 cannot close.",
            "A payload exists for every stage profile, built from grounded content only. "
            "Freeze its schema in packages/contracts on day one so Blenard can build BT-28 "
            "against a fixture in parallel instead of waiting.",
            "JJ-26 (landed). Blocks BT-28; the schema freeze is what unblocks it early.",
        )
    )
    story.append(
        ticket_block(
            s,
            "JJ-26",
            "Borek Gamma template and named content slots",
            "Phase 2 design, Phase 4 delivery  ·  P0  ·  docs/gamma/JJ26_BOREK_GAMMA_TEMPLATE.md",
            "One branded template. Branding is locked inside it. Only named content slots "
            "vary per client. Document which Framework chapter feeds which slot. This is "
            "the concrete form of “design agent driven by a CI sheet”.",
            "Machine-readable contract in packages/contracts/gamma_template.json; branding "
            "keys rejected as GAMMA_TEMPLATE_LOCKED; every chapter-fed slot on the egress "
            "allow-list. (Landed.)",
            "O1, O5, Gamma access. Blocks ES-40.",
        )
    )
    story.append(
        ticket_block(
            s,
            "JJ-27",
            "Client logo placement rules",
            "Phase 4  ·  P0  ·  docs/gamma/JJ27_CLIENT_LOGO_PLACEMENT.md",
            "Define where and how an uploaded client logo appears (cover and closing, "
            "bottom-right, with the Borek mark bottom-left), and what happens when the "
            "logo is missing or poor quality (client-name wordmark; pipeline never fails).",
            "Quality gate, placement payload on the GAMMA_RENDERING result, and fixture "
            "coverage. (Rules landed. Shipping the bytes is JJ-29.)",
            "AT-58 logo metadata. Live placement needs JJ-29.",
        )
    )
    story.append(
        ticket_block(
            s,
            "JJ-28",
            "Ready screen for Gamma output",
            "Phase 4  ·  P0  ·  docs/gamma/JJ28_READY_SCREEN_PARITY.md",
            "Preview and download the Gamma artifact through the same “Your presentation "
            "is ready” experience, so users never see which engine produced the deck.",
            "GET /presentations/{id}/deck has no engine field; downloads prefer a Gamma "
            "export when present; GAMMA_* errors are engine-neutral. (Landed. Matching "
            "previews are JJ-30.)",
            "BT-28, AT-60.",
        )
    )
    story.append(
        ticket_block(
            s,
            "JJ-29",
            "Signed client-logo URL for Gamma",
            "Phase 4  ·  P0  ·  NEW  ·  docs/gamma/JJ29_SIGNED_LOGO_URL.md",
            "Mint a short-lived HTTPS URL on an owned host for a logo that passed the "
            "JJ-27 gate, so Gamma can fetch it. Private artifact: and s3:// refs must "
            "not be sent as-is. Failure still falls back to the wordmark.",
            "A quality-gated AT-58 logo appears on cover and closing of a Gamma deck; "
            "arbitrary https:// is still rejected; unsignable refs report "
            "provider_could_not_fetch_reference.",
            "JJ-27, AT-58, AT-60.",
        )
    )
    story.append(
        ticket_block(
            s,
            "JJ-30",
            "Rasterise Gamma PDF for ready-screen previews",
            "Phase 4  ·  P1  ·  NEW  ·  docs/gamma/JJ30_GAMMA_PREVIEW_RASTER.md",
            "Slide previews are still internal-render PNGs. When Gamma produces the "
            "download, rasterise that PDF during PREVIEW_RENDERING so the ready screen "
            "matches the file the user downloads.",
            "Gamma path: one preview image per PDF page, same order as the download. "
            "Rasteriser failure must not block downloads or introduce an engine field.",
            "JJ-28, BT-28.",
        )
    )
    story.append(
        ticket_block(
            s,
            "JJ-31",
            "Stage profiles for the Borek template",
            "Phase 3 design, Phase 4 delivery  ·  P0  ·  NEW  ·  docs/gamma/JJ31_STAGE_TEMPLATE_PROFILES.md",
            "JJ-26 assumes one output, so one slot set. Add a stage_profiles block to the "
            "contract declaring, per journey stage, which cards are included, which "
            "chapters feed which slot, and whether pricing is permitted at all. A later "
            "stage may reuse the confirmed content of the stage before it.",
            "First contact carries no pricing and no client logo; Deepening carries "
            "references and the logo slot; Concretisation carries indicative prices only "
            "where ES-39 grounded them. Unknown stage is GAMMA_PAYLOAD_INVALID, not a "
            "silent default. Branding stays locked in all three.",
            "JJ-26, ES-40, ES-39, JJ-27/JJ-29, BT-31, D2, D5, O1.",
        )
    )

    story.append(PageBreak())
    story.append(person_banner(
        "Mayank Somwani",
        "User surface and filed history",
        "AT-61 · MS-27 · MS-28 · MS-29 · MS-30 · MS-31",
        s,
        MAYANK,
    ))
    story.append(Spacer(1, 8))
    story.append(
        p(
            "Mayank owns every surface the user actually touches — intake, recovery states, "
            "archive, the stage selector — plus the data behind them. AT-61 comes to him "
            "because MS-29 and MS-30 are the only consumers of filing metadata, so the shape "
            "of that metadata is now settled in one head instead of negotiated across two. "
            "MS-30 is deliberately first: without seed data none of his other tickets can be "
            "shown working.",
            s["body"],
        )
    )
    story.append(
        ticket_block(
            s,
            "AT-61",
            "File into a real repository, carried over",
            "Phase 5  ·  P1  ·  CARRIED OVER, re-owned  ·  spec in the AT range",
            "Filing currently lands in a local fixture. Make it a real repository "
            "destination so archived collateral genuinely exists. Filing is a job stage; "
            "the archive UI on top of it is MS-29.",
            "A generated deck is filed with retrievable metadata, and MS-29 reads real "
            "filed artifacts rather than a fixture. Until O2 names the enterprise "
            "repository, in-app filing ships and the UI degrades honestly.",
            "O2 (where the knowledge base lives) is still open. Blenard needs only the "
            "lineage field from this for BT-31.",
        )
    )
    story.append(
        ticket_block(
            s,
            "MS-27",
            "Extended intake experience",
            "Phase 3  ·  P0  ·  NEW (UI already started)  ·  docs/tickets/MS27_EXTENDED_INTAKE.md",
            "Add optional client logo upload (preview, format and size validation, clear "
            "errors) and optional client information fields to the upload screen. Both "
            "must read as genuinely optional so the fast path stays fast.",
            "A first-time user can skip both and start a presentation. A user who fills them "
            "in gets validation, preview, and AT-58 persistence. Neither field is required.",
            "AT-58. Blocks ES-38 (use of the client pack).",
        )
    )
    story.append(
        ticket_block(
            s,
            "MS-28",
            "Recovery states for the new stages",
            "Phase 4  ·  P1  ·  NEW  ·  docs/tickets/MS28_RECOVERY_STATES.md",
            "Understandable states and correct next actions for retrieval failures, Gamma "
            "failures, credential problems, and a missing or changed template. Same "
            "MS-25 categories; one dominant banner; no vendor name; no stack traces.",
            "Each situation maps to CONNECTION_LOST / STILL_RUNNING / RETRYING / "
            "INPUT_REQUIRED / VALIDATION_NEEDS_REVIEW / TERMINAL_FAILURE with the right "
            "button. Reconnect during Gamma is still running, not a lost connection.",
            "MS-25, AT-57, AT-60, BT-28, JJ-28.",
        )
    )
    story.append(
        ticket_block(
            s,
            "MS-29",
            "Archive and history view",
            "Phase 5  ·  P2  ·  NEW  ·  docs/tickets/MS29_ARCHIVE_HISTORY.md",
            "Extend recent presentations into a view over the filed knowledge base so "
            "past collateral can be found and reused — by client and date, not UUID.",
            "A returning user finds and downloads a previously generated deck without "
            "knowing the opportunity id. Until O2 names an enterprise repository, the "
            "view reads in-app AT-61 filing and does not pretend SharePoint is connected.",
            "MS-24, AT-61, O2.",
        )
    )
    story.append(
        ticket_block(
            s,
            "MS-30",
            "Demo data pack: decks, rate cards, client packs, corpus",
            "Phase 3  ·  P1  ·  NEW  ·  docs/tickets/MS30_DEMO_DATA_PACK.md",
            "Seed data plus one command to install it: three decks for one demo client "
            "(one per journey stage), a versioned demo rate card in its own corpus id, two "
            "client packs (rich and bare), and corpus facts that produce a hit, a miss and "
            "an ambiguous answer. Fixtures only — ES-39 still forbids originating a price, "
            "so a demo rate card must be impossible to mistake for a grounded fact.",
            "An empty database becomes a populated archive, a client whose stages unlock "
            "in order, and a retrieval stage that can be made to hit or miss. Seeding twice "
            "changes nothing. The production profile refuses rather than half-writing.",
            "AT-58, AT-61 (filing shape), ES-39, MS-27, MS-29, MS-31. Real rate cards "
            "remain AT-59 and Fiona's.",
        )
    )
    story.append(
        ticket_block(
            s,
            "MS-31",
            "Journey-stage selection on the landing page",
            "Phase 3  ·  P0  ·  NEW  ·  docs/tickets/MS31_JOURNEY_STAGE_SELECTOR.md",
            "Three named options on the landing page, First contact as the default for a "
            "client with no history. Deepening stays locked until a completed First "
            "contact deck exists for that client; Concretisation until a Deepening deck "
            "does. A locked option states the reason and the next action instead of being "
            "silently greyed out, and is not submittable. Eligibility is read from BT-31, "
            "never recomputed in the UI.",
            "A new client shows one selectable option and two locked ones with readable "
            "reasons; each stage unlocks as the one before it completes; the selected "
            "stage travels through to Approve. No stage id, template id or vendor name is "
            "ever shown. Removing Deepening is a config change, not a rewrite.",
            "BT-31 (the actual rule), MS-24, MS-27, AT-58, JJ-31, MS-30, D2.",
        )
    )

    story.append(PageBreak())
    story.append(person_banner(
        "Blenard Tahiraj",
        "Pipeline stages and release",
        "AT-60 · BT-28 · BT-29 · BT-30 · BT-31 · BT-32",
        s,
        BLENARD,
    ))
    story.append(Spacer(1, 8))
    story.append(
        p(
            "Blenard owns every job stage and the release itself: the live provider "
            "contract, the Gamma stage on the Approve path, the customer-facing step names, "
            "the server-side journey lock, what may leave Borek, and the acceptance gate. "
            "AT-60 stays with him because BT-28 and BT-32 depend on it directly, which makes "
            "his run AT-60 → BT-28 → BT-29 / BT-31 → BT-32 → BT-30 almost entirely internal.",
            s["body"],
        )
    )
    story.append(
        ticket_block(
            s,
            "AT-60",
            "Live credentials, template id and error contract, carried over",
            "Phase 4  ·  P0  ·  CARRIED OVER, re-owned  ·  spec in the AT range",
            "The adapter and the stage exist; the live contract does not. Real credentials, "
            "the real template id, and a final error contract with retryability settled. "
            "Delivery still has to supply the credentials themselves.",
            "BT-28 can run against the live provider, and the error contract is stable "
            "enough that Jaya (JJ-29) and Mayank (MS-28) can build against it. Freeze the "
            "error shape and the owned-host rule early — those are the only parts they need.",
            "Delivery for credentials. Blocks BT-28, BT-32, and the live proofs in JJ-29 "
            "and MS-28.",
        )
    )
    story.append(
        ticket_block(
            s,
            "BT-28",
            "Gamma rendering stage",
            "Phase 4  ·  P0  ·  NEW  ·  docs/tickets/BT28_GAMMA_RENDERING_STAGE.md",
            "Replace the internal render stage with the Gamma call inside the "
            "orchestration, behind PRESENTATION_ENGINE, keeping the existing renderer as "
            "a fallback until Gamma is proven in production.",
            "One Approve action with the flag on produces a Gamma artifact the ready "
            "screen can download. Flag off restores the internal renderer. Failure stops "
            "at GAMMA_RENDERING and preserves earlier work. Users never choose an engine.",
            "AT-60, ES-40, JJ-26. Blocks JJ-28 (download path) and MS-28.",
        )
    )
    story.append(
        ticket_block(
            s,
            "BT-29",
            "Progress mapping for the new stages",
            "Phase 4  ·  P0  ·  NEW  ·  docs/tickets/BT29_PROGRESS_MAPPING.md",
            "Add customer-facing names for the new steps, following BT-26 rules: "
            "Retrieving Borek information, Building your presentation, plus filing. "
            "Show a step only when the backend reports it. No invented percentages, no "
            "false timeout, no vendor names.",
            "A long job that includes retrieval and Gamma progresses through the new "
            "names. A job that never takes those stages never shows them.",
            "BT-26, AT-56, BT-28, AT-59 when retrieval is a job stage.",
        )
    )
    story.append(
        ticket_block(
            s,
            "BT-30",
            "End-to-end gate, second edition",
            "Phase 5  ·  P0  ·  NEW  ·  docs/tickets/BT30_E2E_GATE_V2.md",
            "Re-accept the full journey with the client pack, retrieval and Gamma in "
            "place, including failure and recovery. English E2E pass; German smoke.",
            "A clean user completes login → optional intake → transcripts → Framework "
            "→ Approve → automatic deck → preview → download without developer "
            "intervention, and one classified failure path recovers without a dead end.",
            "BT-28, BT-29, AT-58–61, ES-38–40, JJ-26, JJ-28, MS-27, MS-28.",
        )
    )
    story.append(
        ticket_block(
            s,
            "BT-31",
            "Journey-stage prerequisites and prior-stage context",
            "Phase 4  ·  P0  ·  NEW  ·  docs/tickets/BT31_STAGE_PREREQUISITES.md",
            "Make MS-31's lock real. Record the stage on the presentation version, expose "
            "an eligibility contract saying which stages are startable and why the others "
            "are not, refuse a locked stage server-side, and load the confirmed Framework "
            "and deck reference of the earlier stage into the later job so the deck "
            "continues the story rather than restarting it.",
            "A direct API call for a locked stage is refused with a classified error, no "
            "job row created and never a 500. A Deepening job demonstrably carries First "
            "contact content. A missing or superseded prerequisite is an INPUT_REQUIRED "
            "state with a next action, not a crash. Lineage is queryable. Stage is never "
            "coupled to the engine flag.",
            "BT-28 (same owner), AT-56, AT-57, D2. Needs only the stage enum from JJ-31 "
            "and the lineage field from AT-61 — freeze both and neither is a blocker. "
            "MS-31 and MS-28 are consumers, not blockers.",
        )
    )
    story.append(
        ticket_block(
            s,
            "BT-32",
            "Egress classification and allow-list, production closure",
            "Phase 4  ·  P0  ·  NEW NUMBER for unnumbered O4 work  ·  docs/tickets/BT32_EGRESS_CLASSIFICATION_CLOSURE.md",
            "The policy file, the filter code and JJ-26's allow-list requirement all "
            "exist; closure does not. Classify every field that can reach a provider "
            "under O4, cover all three JJ-31 stage profiles, keep unlisted fields "
            "fail-closed, and record per send what left — opportunity, version, stage, "
            "provider, field names and classifications, without storing the payload. "
            "Classification runs against the frozen slot list, so it does not wait for "
            "JJ-31 to land.",
            "No field leaves without an explicit classification and an allow-list entry "
            "for that provider and stage. A slot added to the contract with no policy "
            "entry fails in CI, not in production. Restricted never egresses. The audit "
            "trail answers what client data went out for a given version, and the O4 "
            "sign-off is recorded rather than assumed.",
            "JJ-26, AT-60 (same owner), AT-52 (audit log), O4 decision and sign-off. From "
            "JJ-31 it needs the frozen slot list only.",
        )
    )

    story.append(PageBreak())
    story.append(p("4. Contracts to freeze before building", s["h1"]))
    story.append(
        p(
            "The verticals remove most of the coupling but not all of it, and the honest "
            "position is that some edges cannot be removed at all — three people building one "
            "product will hand things to each other. What they can be is few, one-directional, "
            "and contract-shaped. Agree each shape below in week one, commit it to "
            "packages/contracts, and both sides then build in parallel against a fixture "
            "instead of one waiting on the other. This is already how the repo works: "
            "gamma_template.json is the source of truth and the provider has a fixture client.",
            s["body"],
        )
    )
    story.append(
        table(
            ["Handoff", "Freeze this", "So the consumer can"],
            [
                [
                    "ES-40 → BT-28",
                    "Gamma payload schema",
                    "Blenard builds the stage against a fixture payload rather than waiting "
                    "for Jaya's builder. This is the edge that has stalled everything, so it "
                    "is the one to freeze first.",
                ],
                [
                    "JJ-31 → BT-31",
                    "stage_profiles block and the stage enum",
                    "Blenard enforces prerequisites against the enum before the profiles are "
                    "filled in.",
                ],
                [
                    "JJ-31 → BT-32",
                    "The slot list per stage profile",
                    "Blenard classifies slots for egress before they physically exist.",
                ],
                [
                    "AT-60 → JJ-29, MS-28",
                    "Provider error contract and the owned-host rule",
                    "Jaya signs logo URLs against a fixture host; Mayank maps fixture errors "
                    "to recovery categories.",
                ],
                [
                    "BT-28 → JJ-30",
                    "Where the Gamma PDF lands on the version",
                    "Jaya rasterises a fixture PDF from that location.",
                ],
                [
                    "BT-31 → MS-31",
                    "Eligibility response JSON",
                    "Mayank renders locked and unlocked states from a fixture payload.",
                ],
                [
                    "AT-59 → BT-29",
                    "The stage name, nothing else",
                    "Blenard ships the label behind the existing “shown only when reported” "
                    "rule, so the live corpus is not a blocker.",
                ],
                [
                    "ES-39 → MS-30",
                    "Demo corpus id and provenance marker",
                    "Mayank seeds demo rate cards that can never be mistaken for grounded "
                    "facts.",
                ],
            ],
            s,
            [30 * mm, 42 * mm, usable - 72 * mm],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        p(
            "BT-30 is the exception and should not be engineered around: the acceptance gate "
            "depends on everything by design and runs last. MS-30 is the other half of the "
            "answer — while AT-59 and AT-61 are in flight there is no live corpus and no real "
            "filing, so seed data is what lets MS-29, MS-31, BT-29 and BT-30 be demonstrated "
            "instead of postponed.",
            s["note"],
        )
    )

    story.append(p("5. Sequence the three owners should not break", s["h1"]))
    story.append(
        p(
            "Most chains are now internal to one owner, which is the point of the re-cut. "
            "The crossings column is what the freeze list in section 4 exists for.",
            s["body"],
        )
    )
    story.append(
        table(
            ["Chain", "Crossings", "Why it matters"],
            [
                [
                    "AT-59 → ES-39 → JJ-31",
                    "None — all Jaya",
                    "Corpus, then the grounding rule, then priced Concretisation content. "
                    "Previously this crossed two owners.",
                ],
                [
                    "ES-40 → JJ-31",
                    "None — all Jaya",
                    "Payload builder before the stage profiles that specialise it.",
                ],
                [
                    "AT-60 → BT-28 → BT-29 / BT-31 → BT-32",
                    "None — all Blenard",
                    "Live contract, then the stage, then labels and prerequisites, then what "
                    "may leave. The entire pipeline run is his.",
                ],
                [
                    "AT-61 → MS-29, MS-30",
                    "None — all Mayank",
                    "Real filing before an archive over it and before seeding filed work.",
                ],
                [
                    "MS-30 → MS-27 / MS-29 / MS-31",
                    "None — all Mayank",
                    "Seed data first: a locked stage cannot be shown unlocking and an "
                    "archive cannot be shown full without it.",
                ],
                [
                    "ES-40 → BT-28",
                    "Jaya → Blenard",
                    "The one edge that has stalled the chain. Freeze the payload schema and "
                    "it stops being a wait.",
                ],
                [
                    "JJ-31 → BT-31 → MS-31",
                    "Jaya → Blenard → Mayank",
                    "Profiles, then the server-side lock, then the selector. Building the "
                    "selector first would ship a menu whose options do nothing.",
                ],
                [
                    "D2 → JJ-31",
                    "Leadership → Jaya",
                    "Whether Deepening survives, and one template or three. Both MS-31 and "
                    "JJ-31 treat the answer as configuration.",
                ],
                [
                    "O2 → AT-61",
                    "Leadership → Mayank",
                    "The archive must not claim an enterprise repository that is not decided.",
                ],
                [
                    "Everything → BT-30",
                    "All three → Blenard",
                    "Inherent. The acceptance gate runs last and now has to accept all three "
                    "journey stages.",
                ],
            ],
            s,
            [46 * mm, 30 * mm, usable - 76 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(p("6. Suggested start order", s["h2"]))
    story.append(
        table(
            ["Who", "Start now", "Then", "Wait for"],
            [
                [
                    "Jaya",
                    "Freeze the ES-40 payload schema, then build ES-40",
                    "AT-59 corpus, ES-39 grounding, JJ-31 profiles, then JJ-29 and JJ-30",
                    "Nothing to start. JJ-29 and JJ-30 need Blenard's frozen shapes, not his "
                    "finished code.",
                ],
                [
                    "Mayank",
                    "MS-30 demo data — everything else of his is demonstrable only after it",
                    "AT-61 filing, MS-29 archive, close MS-27, then MS-31 and MS-28",
                    "Nothing to start. MS-31 needs the eligibility JSON shape; MS-29 needs O2 "
                    "before it can claim an external repository.",
                ],
                [
                    "Blenard",
                    "AT-60 live contract, and publish the error shape on day one",
                    "BT-28 against the fixture payload, then BT-29, BT-31, BT-32",
                    "Delivery for the credentials. BT-30 until the Phase 4 tickets pass.",
                ],
            ],
            s,
            [24 * mm, 46 * mm, 46 * mm, usable - 116 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        p(
            "All three can start on day one and none of them starts by waiting. That is the "
            "test of whether this division worked.",
            s["body"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        p(
            "Specs live in the repo: docs/gamma/JJ26–JJ31 and docs/tickets/BT28–BT32, "
            "MS27–MS31. The carried-over AT and ES items keep their original IDs and specs so "
            "the history stays traceable. This PDF is the assignment list, not a substitute "
            "for those files.",
            s["note"],
        )
    )

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return OUTPUT


if __name__ == "__main__":
    path = build()
    print(path)
