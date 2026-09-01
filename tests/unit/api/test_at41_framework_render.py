"""AT-41: framework PDF / HTML / DOCX render contract."""

from __future__ import annotations

import uuid
from html import unescape
from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _client() -> TestClient:
    return TestClient(create_app())


def _headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_ID,
        email="owner@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _create_framework(client: TestClient, *, confirm: bool = False) -> tuple[str, dict]:
    created = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme Corp",
            "opportunity_name": "Invoice Automation",
            "department": "Finance",
        },
    )
    assert created.status_code == 201, created.text
    opportunity_id = created.json()["id"]
    generate = client.post(
        f"/opportunities/{opportunity_id}/framework/generate",
        headers=_headers(),
    )
    assert generate.status_code == 202, generate.text
    framework_id = generate.json()["framework_version_id"]
    if confirm:
        confirmed = client.post(
            f"/opportunities/{opportunity_id}/framework/confirm",
            headers=_headers(),
            json={"framework_version_id": framework_id},
        )
        assert confirmed.status_code == 200, confirmed.text
    latest = client.get(f"/frameworks/{framework_id}", headers=_headers())
    assert latest.status_code == 200, latest.text
    return framework_id, latest.json()


def _chapter_titles(framework: dict) -> list[str]:
    chapters = sorted(
        framework["framework_json"]["chapters"],
        key=lambda chapter: int(chapter["chapter_id"]),
    )
    assert len(chapters) == 14
    return [str(chapter["title"]) for chapter in chapters]


def test_render_pdf_returns_pdf_bytes() -> None:
    client = _client()
    framework_id, _ = _create_framework(client)
    response = client.get(
        f"/frameworks/{framework_id}/render?format=pdf",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


def test_render_pdf_includes_version_and_client_metadata() -> None:
    from io import BytesIO

    from pypdf import PdfReader

    client = _client()
    framework_id, framework = _create_framework(client)
    response = client.get(
        f"/frameworks/{framework_id}/render?format=pdf",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    blob = "\n".join(
        page.extract_text() or ""
        for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "Borek" in blob
    assert "Acme Corp" in blob
    assert "v1" in blob or "Version" in blob
    assert str(framework.get("version") or framework["framework_json"].get("version") or 1) in blob


def test_render_html_returns_html() -> None:
    client = _client()
    framework_id, framework = _create_framework(client)
    response = client.get(
        f"/frameworks/{framework_id}/render?format=html",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    assert "text/html" in response.headers["content-type"]
    body = unescape(response.text)
    for title in _chapter_titles(framework):
        assert title in body


def test_render_docx_returns_valid_docx() -> None:
    client = _client()
    framework_id, _ = _create_framework(client)
    response = client.get(
        f"/frameworks/{framework_id}/render?format=docx",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    assert DOCX_TYPE in response.headers["content-type"]
    document = Document(BytesIO(response.content))
    texts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    assert len(texts) >= 14


def test_render_docx_contains_all_chapters() -> None:
    client = _client()
    framework_id, framework = _create_framework(client)
    response = client.get(
        f"/frameworks/{framework_id}/render?format=docx",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    document = Document(BytesIO(response.content))
    headings = [
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.style and str(paragraph.style.name).startswith("Heading")
    ]
    heading_blob = "\n".join(headings)
    for title in _chapter_titles(framework):
        assert title in heading_blob


def test_render_draft_shows_draft_status() -> None:
    client = _client()
    framework_id, framework = _create_framework(client, confirm=False)
    assert framework["status"] == "draft"
    response = client.get(
        f"/frameworks/{framework_id}/render?format=docx",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    document = Document(BytesIO(response.content))
    blob = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "DRAFT" in blob
    assert "not confirmed" in blob.lower()


def test_render_confirmed_does_not_show_draft() -> None:
    client = _client()
    framework_id, framework = _create_framework(client, confirm=True)
    assert framework["status"] == "confirmed"
    response = client.get(
        f"/frameworks/{framework_id}/render?format=docx",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    document = Document(BytesIO(response.content))
    blob = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "DRAFT" not in blob
    assert "Confirmed" in blob


def test_render_docx_includes_client_metadata_and_evidence() -> None:
    client = _client()
    framework_id, framework = _create_framework(client)
    response = client.get(
        f"/frameworks/{framework_id}/render?format=docx",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    document = Document(BytesIO(response.content))
    blob = "\n".join(
        [paragraph.text for paragraph in document.paragraphs]
        + [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    )
    assert "Borek" in blob
    assert "Acme Corp" in blob
    assert "Invoice Automation" in blob
    assert "Quality and readiness" in blob
    assert "Assumptions and open items" in blob
    json_blob = str(framework["framework_json"])
    if "source_refs" in json_blob:
        assert "Sources:" in blob or "C1" in blob or "conversation" in blob.lower()


def test_render_html_includes_overview_and_tables() -> None:
    client = _client()
    framework_id, _ = _create_framework(client)
    response = client.get(
        f"/frameworks/{framework_id}/render?format=html",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    body = unescape(response.text)
    assert "Acme Corp" in body
    assert "Borek" in body
    assert "<table" in body
    assert "Quality and readiness" in body


def test_render_does_not_mutate_stored_framework() -> None:
    client = _client()
    framework_id, before = _create_framework(client)
    client.get(f"/frameworks/{framework_id}/render?format=docx", headers=_headers())
    after = client.get(f"/frameworks/{framework_id}", headers=_headers())
    assert after.status_code == 200
    assert after.json()["status"] == before["status"]
    assert after.json()["framework_json"]["title"] == before["framework_json"]["title"]


def test_render_docx_includes_tables_and_lists() -> None:
    client = _client()
    framework_id, framework = _create_framework(client)
    framework_json = framework["framework_json"]
    opportunity_id = framework["opportunity_id"]
    chapter = framework_json["chapters"][2]
    chapter["body"] = [
        {
            "block": "bullets",
            "items": ["Manual invoice matching", "Exception handling backlog"],
        },
        {
            "block": "table",
            "caption": "KPI baseline",
            "columns": ["Metric", "Current"],
            "rows": [["Auto-match rate", "42%"]],
        },
    ]
    patch = client.patch(
        f"/opportunities/{opportunity_id}/framework",
        headers=_headers(),
        json={"framework_json": framework_json},
    )
    assert patch.status_code == 200, patch.text

    response = client.get(
        f"/frameworks/{framework_id}/render?format=docx",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    document = Document(BytesIO(response.content))
    styles = {paragraph.style.name for paragraph in document.paragraphs if paragraph.text.strip()}
    blob = "\n".join(
        [paragraph.text for paragraph in document.paragraphs]
        + [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    )
    assert "List Bullet" in styles or "Manual invoice matching" in blob
    assert "Manual invoice matching" in blob
    assert "Auto-match rate" in blob
    assert len(document.tables) >= 1


def test_render_german_framework() -> None:
    client = _client()
    framework_id, _ = _create_framework(client)
    response = client.get(
        f"/frameworks/{framework_id}/render?format=docx&lang=de",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    assert DOCX_TYPE in response.headers["content-type"]
    document = Document(BytesIO(response.content))
    blob = "\n".join(
        [paragraph.text for paragraph in document.paragraphs]
        + [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    )
    assert "Kunden-Framework-Bericht" in blob
    assert "ENTWURF" in blob or "nicht bestätigt" in blob
    assert "Version" in blob
    Document(BytesIO(response.content))
