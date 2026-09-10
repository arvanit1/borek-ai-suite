"""JJ-30: ready-screen previews match the downloaded PDF page-for-page."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.services.data.memory_store import get_memory_store
from app.services.deck_assets import _MINIMAL_PNG
from app.services.gamma_preview import apply_gamma_preview_raster

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
GAMMA_PPTX = b"gamma-export-pptx-bytes"
PAGE_COUNT = 3


def _headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_ID,
        email="owner@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _ready_presentation(client: TestClient) -> tuple[str, str]:
    opportunity = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme Corp",
            "opportunity_name": "Invoice Automation",
            "department": "Finance",
        },
    )
    assert opportunity.status_code == 201
    opportunity_id = opportunity.json()["id"]

    client.post(f"/opportunities/{opportunity_id}/framework/generate", headers=_headers())
    confirm = client.post(
        f"/opportunities/{opportunity_id}/framework/confirm",
        headers=_headers(),
        json={},
    )
    assert confirm.status_code == 200

    client.post(
        f"/opportunities/{opportunity_id}/presentation-plan/generate",
        headers=_headers(),
        json={},
    )
    generate = client.post(
        f"/opportunities/{opportunity_id}/presentation/generate",
        headers=_headers(),
        json={},
    )
    assert generate.status_code == 202
    return opportunity_id, generate.json()["presentation_id"]


def _write_export_pdf(path: Path, *, pages: int) -> None:
    writer = canvas.Canvas(str(path), pagesize=A4)
    for index in range(pages):
        writer.drawString(72, 720, f"Export page {index + 1}")
        writer.showPage()
    writer.save()


def _write_gamma_export(
    root: Path,
    *,
    opportunity_id: str,
    presentation_id: str,
    pages: int = PAGE_COUNT,
) -> Path:
    version = get_memory_store().get_presentation_version_assets(
        presentation_id=uuid.UUID(presentation_id),
        user_id=USER_ID,
    )
    directory = root / "gamma" / opportunity_id / str(version["id"])
    directory.mkdir(parents=True, exist_ok=True)
    generation_id = uuid.uuid4()
    (directory / f"{generation_id}.pptx").write_bytes(GAMMA_PPTX)
    pdf_path = directory / f"{generation_id}.pdf"
    _write_export_pdf(pdf_path, pages=pages)
    return pdf_path


def test_preview_page_count_matches_the_downloaded_pdf(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    client = TestClient(create_app())
    opportunity_id, presentation_id = _ready_presentation(client)
    pdf_path = _write_gamma_export(
        tmp_path,
        opportunity_id=opportunity_id,
        presentation_id=presentation_id,
    )

    version = get_memory_store().get_presentation_version_assets(
        presentation_id=uuid.UUID(presentation_id),
        user_id=USER_ID,
    )
    internal_previews = list(version.get("preview_image_paths") or [])
    assert internal_previews
    assert Path(internal_previews[0]).read_bytes() == _MINIMAL_PNG

    apply_gamma_preview_raster(
        get_memory_store(),
        presentation_id=presentation_id,
        user_id=USER_ID,
        version=version,
    )

    deck = client.get(f"/presentations/{presentation_id}/deck", headers=_headers())
    assert deck.status_code == 200
    body = deck.json()
    assert len(body["slides"]) == PAGE_COUNT
    assert "engine" not in body
    assert "gamma" not in deck.text.lower()

    images = []
    for index in range(PAGE_COUNT):
        preview = client.get(
            f"/presentations/{presentation_id}/preview/slides/{index}.png",
            headers=_headers(),
        )
        assert preview.status_code == 200
        assert preview.headers["content-type"].startswith("image/png")
        images.append(preview.content)
        assert preview.content != _MINIMAL_PNG
    assert len(set(images)) == PAGE_COUNT

    pdf = client.get(f"/presentations/{presentation_id}/download/pdf", headers=_headers())
    assert pdf.status_code == 200
    assert pdf.content == pdf_path.read_bytes()


def test_rasteriser_failure_keeps_downloads_and_internal_previews(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    client = TestClient(create_app())
    opportunity_id, presentation_id = _ready_presentation(client)
    pdf_path = _write_gamma_export(
        tmp_path,
        opportunity_id=opportunity_id,
        presentation_id=presentation_id,
    )

    def _boom(*_args, **_kwargs):
        raise RuntimeError("pdftoppm exploded")

    monkeypatch.setattr(
        "app.services.gamma_preview.rasterise_pdf_pages",
        _boom,
    )

    version = get_memory_store().get_presentation_version_assets(
        presentation_id=uuid.UUID(presentation_id),
        user_id=USER_ID,
    )
    before = list(version.get("preview_image_paths") or [])
    apply_gamma_preview_raster(
        get_memory_store(),
        presentation_id=presentation_id,
        user_id=USER_ID,
        version=version,
    )
    after = get_memory_store().get_presentation_version_assets(
        presentation_id=uuid.UUID(presentation_id),
        user_id=USER_ID,
    )
    assert list(after.get("preview_image_paths") or []) == before

    deck = client.get(f"/presentations/{presentation_id}/deck", headers=_headers())
    assert deck.status_code == 200
    body = deck.json()
    assert set(body) == {
        "presentation_id",
        "presentation_name",
        "version_number",
        "status",
        "slides",
        "pptx_download_url",
        "pdf_download_url",
    }
    assert "engine" not in body
    assert "gamma" not in deck.text.lower()

    preview = client.get(
        f"/presentations/{presentation_id}/preview/slides/0.png",
        headers=_headers(),
    )
    assert preview.status_code == 200
    assert preview.content == _MINIMAL_PNG

    pdf = client.get(f"/presentations/{presentation_id}/download/pdf", headers=_headers())
    assert pdf.status_code == 200
    assert pdf.content == pdf_path.read_bytes()
    pptx = client.get(
        f"/presentations/{presentation_id}/download/pptx",
        headers=_headers(),
    )
    assert pptx.status_code == 200
    assert pptx.content == GAMMA_PPTX


def test_internal_previews_stay_put_without_an_export(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    client = TestClient(create_app())
    _opportunity_id, presentation_id = _ready_presentation(client)

    before = client.get(f"/presentations/{presentation_id}/deck", headers=_headers())
    assert before.status_code == 200
    version = get_memory_store().get_presentation_version_assets(
        presentation_id=uuid.UUID(presentation_id),
        user_id=USER_ID,
    )
    apply_gamma_preview_raster(
        get_memory_store(),
        presentation_id=presentation_id,
        user_id=USER_ID,
        version=version,
    )
    after = client.get(f"/presentations/{presentation_id}/deck", headers=_headers())
    assert after.status_code == 200
    assert len(after.json()["slides"]) == len(before.json()["slides"])
    preview = client.get(
        f"/presentations/{presentation_id}/preview/slides/0.png",
        headers=_headers(),
    )
    assert preview.status_code == 200
    assert preview.content == _MINIMAL_PNG
