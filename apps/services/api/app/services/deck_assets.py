"""Stub deck preview artifacts for local dev and unit tests (AT-9 / AT-49)."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID

from app.config import settings

_ROOT = Path(__file__).resolve().parents[5]
_MINIMAL_PPTX = _ROOT / "tests" / "fixtures" / "renderer" / "minimal.pptx"

# Valid 1x1 PNG (transparent).
_MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c630001000005000108d0960000000049454e44ae426082"
)

_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

# Ready-screen rasters of the downloaded PDF live here, not under the internal
# slide-00N.png names, so a failed raster never overwrites the internal previews.
EXPORT_PREVIEW_DIRNAME = "export-preview"


def deck_assets_root() -> Path:
    configured = Path(settings.ARTIFACT_ROOT)
    root = configured if configured.is_absolute() else _ROOT / configured
    root.mkdir(parents=True, exist_ok=True)
    return root


def materialize_fixture_deck_assets(*, version_id: UUID, slide_count: int) -> dict[str, object]:
    """Write deterministic placeholder assets for isolated tests only."""
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


def export_preview_dir(*, version_id: UUID | str) -> Path:
    return deck_assets_root() / str(version_id) / EXPORT_PREVIEW_DIRNAME


def list_preview_image_paths(
    *,
    version_id: UUID | str,
    stored_paths: list[str] | None = None,
    slide_count: int = 0,
) -> list[str]:
    """Prefer PDF-page rasters when they exist; otherwise the stored or internal PNGs."""
    raster_dir = export_preview_dir(version_id=version_id)
    if raster_dir.is_dir():
        rasters = sorted(
            path for path in raster_dir.glob("slide-*.png") if path.is_file()
        )
        if rasters:
            return [str(path.resolve()) for path in rasters]
    existing = [
        str(Path(str(path)).resolve())
        for path in (stored_paths or [])
        if Path(str(path)).is_file()
    ]
    if existing:
        return existing
    return [
        str(resolve_preview_image_path(version_id=UUID(str(version_id)), slide_index=index).resolve())
        for index in range(max(slide_count, 0))
    ]


def resolve_pptx_path(*, version_id: UUID) -> Path:
    return deck_assets_root() / str(version_id) / "deck.pptx"


def resolve_pdf_path(*, version_id: UUID) -> Path:
    return deck_assets_root() / str(version_id) / "deck.pdf"


def resolve_gamma_artifact_path(
    *,
    opportunity_id: UUID | str,
    version_id: UUID | str,
    kind: str,
) -> Path | None:
    """JJ-28 / BT-28: locate a Gamma export for this version, if the Gamma stage ran.

    Canonical location is `packages/contracts/gamma_artifact_location.json`:
    `gamma/{opportunity}/{version}/{generation}.{kind}`. The generation id is not
    known here, so the newest matching export wins.
    """
    relative = Path("gamma") / str(opportunity_id) / str(version_id)
    roots = {deck_assets_root(), Path(settings.ARTIFACT_ROOT)}
    exports = [
        path
        for root in roots
        if (directory := root / relative).is_dir()
        for path in directory.glob(f"*.{kind}")
        if path.is_file()
    ]
    if not exports:
        return None
    return max(exports, key=lambda path: path.stat().st_mtime)
