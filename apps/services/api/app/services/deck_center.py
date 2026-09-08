"""Deck center helpers (AT-49)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.services.api_errors import conflict, not_found
from app.services.data import DataStore
from app.services.deck_assets import (
    resolve_gamma_artifact_path,
    resolve_pdf_path,
    resolve_pptx_path,
    resolve_preview_image_path,
)


def build_deck_center_payload(
    store: DataStore,
    *,
    presentation_id: UUID,
    user_id: UUID,
) -> dict[str, object]:
    presentation = store.get_presentation(presentation_id=presentation_id, user_id=user_id)
    version = store.get_presentation_version_assets(
        presentation_id=presentation_id,
        user_id=user_id,
    )
    _require_ready(version)
    slides = store.list_slides(presentation_id=presentation_id, user_id=user_id)
    presentation_id_str = str(presentation_id)

    slide_items: list[dict[str, object]] = []
    for slide in slides:
        slide_items.append(
            {
                "slide_id": slide["id"],
                "slide_index": slide["slide_index"],
                "layout_id": slide["layout_id"],
                "preview_url": (
                    f"/presentations/{presentation_id_str}/preview/slides/{slide['slide_index']}.png"
                ),
            }
        )

    return {
        "presentation_id": presentation_id,
        "presentation_name": presentation["name"],
        "version_number": version["version_number"],
        "status": version["status"],
        "slides": slide_items,
        "pptx_download_url": f"/presentations/{presentation_id_str}/download/pptx",
        "pdf_download_url": f"/presentations/{presentation_id_str}/download/pdf",
    }


def resolve_deck_file_path(
    store: DataStore,
    *,
    presentation_id: UUID,
    user_id: UUID,
    kind: str,
) -> Path:
    version = store.get_presentation_version_assets(
        presentation_id=presentation_id,
        user_id=user_id,
    )
    _require_ready(version)
    version_id = version["id"]
    if kind not in ("pptx", "pdf"):
        raise not_found("DECK_FILE_NOT_FOUND", f"Unknown deck file type: {kind}")

    # JJ-28: whichever engine produced the deck, it is downloaded from the same
    # URL. A Gamma export supersedes the internal render for this version.
    gamma_path = _resolve_gamma_deck_file(
        store,
        presentation_id=presentation_id,
        user_id=user_id,
        version_id=version_id,
        kind=kind,
    )
    if gamma_path is not None:
        return gamma_path

    if kind == "pptx":
        path = Path(version["pptx_storage_path"]) if version.get("pptx_storage_path") else resolve_pptx_path(version_id=version_id)
    else:
        path = Path(version["pdf_storage_path"]) if version.get("pdf_storage_path") else resolve_pdf_path(version_id=version_id)

    if not path.is_file():
        raise not_found("DECK_FILE_NOT_FOUND", f"Deck {kind} file is not available")
    return path


def _resolve_gamma_deck_file(
    store: DataStore,
    *,
    presentation_id: UUID,
    user_id: UUID,
    version_id: object,
    kind: str,
) -> Path | None:
    try:
        opportunity_id = store.get_presentation_opportunity_id(
            presentation_id=presentation_id,
            user_id=user_id,
        )
    except Exception:
        return None
    return resolve_gamma_artifact_path(
        opportunity_id=opportunity_id,
        version_id=version_id,
        kind=kind,
    )


def resolve_deck_preview_image_path(
    store: DataStore,
    *,
    presentation_id: UUID,
    user_id: UUID,
    slide_index: int,
) -> Path:
    version = store.get_presentation_version_assets(
        presentation_id=presentation_id,
        user_id=user_id,
    )
    _require_ready(version)
    preview_paths = version.get("preview_image_paths") or []
    if slide_index < len(preview_paths):
        path = Path(str(preview_paths[slide_index]))
        if path.is_file():
            return path

    path = resolve_preview_image_path(version_id=version["id"], slide_index=slide_index)
    if not path.is_file():
        raise not_found(
            "SLIDE_PREVIEW_NOT_FOUND",
            f"Preview image for slide {slide_index + 1} was not found",
        )
    return path


def _require_ready(version: dict) -> None:
    if version.get("status") != "ready":
        raise conflict(
            "PRESENTATION_NOT_READY",
            "Presentation artifacts are not ready for preview or download",
        )
