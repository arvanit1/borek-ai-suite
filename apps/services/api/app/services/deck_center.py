"""Deck center helpers (AT-49)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.services.api_errors import not_found
from app.services.data import DataStore
from app.services.deck_assets import resolve_pdf_path, resolve_pptx_path, resolve_preview_image_path


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
    version_id = version["id"]
    if kind == "pptx":
        path = Path(version["pptx_storage_path"]) if version.get("pptx_storage_path") else resolve_pptx_path(version_id=version_id)
    elif kind == "pdf":
        path = Path(version["pdf_storage_path"]) if version.get("pdf_storage_path") else resolve_pdf_path(version_id=version_id)
    else:
        raise not_found("DECK_FILE_NOT_FOUND", f"Unknown deck file type: {kind}")

    if not path.is_file():
        raise not_found("DECK_FILE_NOT_FOUND", f"Deck {kind} file is not available")
    return path


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
