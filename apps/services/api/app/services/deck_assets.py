"""Stub deck preview artifacts for local dev and unit tests (AT-9 / AT-49)."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID

_ROOT = Path(__file__).resolve().parents[6]
_MINIMAL_PPTX = _ROOT / "tests" / "fixtures" / "renderer" / "minimal.pptx"
_ASSETS_ROOT = _ROOT / "tmp" / "deck_assets"

# Valid 1x1 PNG (transparent).
_MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c630001000005000108d0960000000049454e44ae426082"
)

_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def deck_assets_root() -> Path:
    root = _ASSETS_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def materialize_stub_deck_assets(*, version_id: UUID, slide_count: int) -> dict[str, object]:
    """Write pptx/pdf/png preview files for a presentation version."""
    output_dir = deck_assets_root() / str(version_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    pptx_path = output_dir / "deck.pptx"
    pdf_path = output_dir / "deck.pdf"
    if _MINIMAL_PPTX.is_file():
        shutil.copyfile(_MINIMAL_PPTX, pptx_path)
    else:
        pptx_path.write_bytes(b"PK\x03\x04")

    pdf_path.write_bytes(_MINIMAL_PDF)

    preview_image_paths: list[str] = []
    for index in range(slide_count):
        png_path = output_dir / f"slide-{index + 1:03d}.png"
        png_path.write_bytes(_MINIMAL_PNG)
        preview_image_paths.append(str(png_path.resolve()))

    return {
        "pptx_storage_path": str(pptx_path.resolve()),
        "pdf_storage_path": str(pdf_path.resolve()),
        "preview_image_paths": preview_image_paths,
    }


def resolve_preview_image_path(*, version_id: UUID, slide_index: int) -> Path:
    return deck_assets_root() / str(version_id) / f"slide-{slide_index + 1:03d}.png"


def resolve_pptx_path(*, version_id: UUID) -> Path:
    return deck_assets_root() / str(version_id) / "deck.pptx"


def resolve_pdf_path(*, version_id: UUID) -> Path:
    return deck_assets_root() / str(version_id) / "deck.pdf"
