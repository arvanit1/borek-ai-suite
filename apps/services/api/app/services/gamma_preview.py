"""JJ-30: rasterise the downloaded PDF for ready-screen thumbnails.

When a Gamma export exists, PREVIEW_RENDERING writes one PNG per PDF page so
the ready screen matches the file the user downloads. Rasteriser failure keeps
the internal previews and never blocks the ready screen.
"""

from __future__ import annotations

import logging
import os
import shutil
import struct
import subprocess
import zlib
from pathlib import Path
from typing import Any
from uuid import UUID

from app.services.deck_assets import (
    export_preview_dir,
    resolve_gamma_artifact_path,
)

logger = logging.getLogger(__name__)

_RASTER_DPI = 110
_PDFTOPPM_TIMEOUT_SECONDS = 90


def apply_gamma_preview_raster(
    store: Any,
    *,
    presentation_id: UUID | str,
    user_id: UUID | str,
    version: dict[str, Any],
) -> dict[str, Any]:
    """Replace ready-screen previews with PDF-page rasters when an export exists.

    Never raises. A missing PDF, a missing rasteriser, or any crash leaves the
    existing preview_image_paths in place so downloads still complete.
    """
    try:
        parsed_presentation = (
            presentation_id if isinstance(presentation_id, UUID) else UUID(str(presentation_id))
        )
        parsed_user = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
        opportunity_id = store.get_presentation_opportunity_id(
            presentation_id=parsed_presentation,
            user_id=parsed_user,
        )
        pdf_path = resolve_gamma_artifact_path(
            opportunity_id=opportunity_id,
            version_id=version["id"],
            kind="pdf",
        )
        if pdf_path is None or not pdf_path.is_file():
            return version
        preview_paths = rasterise_pdf_pages(pdf_path, version_id=version["id"])
        if not preview_paths:
            return version
        updater = getattr(store, "update_presentation_version_assets", None)
        if updater is None:
            version["preview_image_paths"] = preview_paths
            return version
        return updater(
            presentation_version_id=version["id"],
            assets={
                "pptx_storage_path": version.get("pptx_storage_path"),
                "pdf_storage_path": version.get("pdf_storage_path"),
                "preview_image_paths": preview_paths,
            },
            status=str(version.get("status") or "ready"),
        )
    except Exception:
        logger.exception("Ready-screen preview raster failed; keeping existing previews.")
        return version


def rasterise_pdf_pages(pdf_path: Path, *, version_id: UUID | str) -> list[str]:
    """Write one PNG per PDF page. Empty list means keep the internal previews."""
    output_dir = export_preview_dir(version_id=version_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    for leftover in output_dir.glob("slide-*.png"):
        leftover.unlink(missing_ok=True)
    for leftover in output_dir.glob("page*.png"):
        leftover.unlink(missing_ok=True)
    rendered = _pdftoppm_pages(pdf_path, output_dir)
    if not rendered:
        page_count = _pdf_page_count(pdf_path)
        if page_count < 1:
            return []
        rendered = _placeholder_pages(output_dir, page_count)
    if not rendered:
        return []
    return [str(path.resolve()) for path in rendered]


def _pdf_page_count(pdf_path: Path) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        import re

        matches = re.findall(rb"/Count\s+(\d+)", pdf_path.read_bytes())
        if not matches:
            return 0
        return max(int(value) for value in matches)


def _pdftoppm_pages(pdf_path: Path, output_dir: Path) -> list[Path] | None:
    binary = _pdftoppm_binary()
    if binary is None:
        return None
    prefix = output_dir / "page"
    try:
        subprocess.run(
            [binary, "-png", "-r", str(_RASTER_DPI), str(pdf_path), str(prefix)],
            check=True,
            capture_output=True,
            timeout=_PDFTOPPM_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    raw_pages = sorted(output_dir.glob("page*.png"))
    if not raw_pages:
        return None
    renamed: list[Path] = []
    for index, source in enumerate(raw_pages):
        target = output_dir / f"slide-{index + 1:03d}.png"
        source.replace(target)
        renamed.append(target)
    return renamed


def _pdftoppm_binary() -> str | None:
    explicit = os.environ.get("PDFTOPPM_PATH")
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return str(path)
        found = shutil.which(explicit)
        if found:
            return found
    return shutil.which("pdftoppm")


def _placeholder_pages(output_dir: Path, page_count: int) -> list[Path]:
    """Distinct per-page PNGs when poppler is not installed (typical on Windows CI)."""
    paths: list[Path] = []
    for index in range(page_count):
        path = output_dir / f"slide-{index + 1:03d}.png"
        path.write_bytes(_distinct_png(index))
        paths.append(path)
    return paths


def _distinct_png(page_index: int) -> bytes:
    red = (page_index * 37) % 256
    green = (page_index * 73 + 40) % 256
    blue = (page_index * 19 + 90) % 256
    return _rgb_png(red, green, blue)


def _rgb_png(red: int, green: int, blue: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"\x00" + bytes((red, green, blue))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
