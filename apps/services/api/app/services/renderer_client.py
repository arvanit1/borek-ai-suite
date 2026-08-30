"""HTTP client for the stateless renderer artifact bundle."""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID

import httpx

from app.config import settings
from app.services.deck_assets import deck_assets_root


class RendererClientError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def render_deck_assets(
    *,
    version_id: UUID,
    presentation_plan: dict[str, Any],
    slide_specs: list[dict[str, Any]],
) -> dict[str, object]:
    try:
        response = httpx.post(
            f"{settings.RENDERER_URL.rstrip('/')}/render",
            json={"presentationPlan": presentation_plan, "slideSpecs": slide_specs},
            timeout=settings.RENDERER_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise RendererClientError(
            "RENDERER_UNAVAILABLE",
            f"Renderer request failed: {exc}",
            retryable=True,
        ) from exc

    if response.status_code != 200:
        code = "PPTX_RENDER_FAILED"
        message = response.text
        try:
            error = response.json().get("error") or {}
            code = str(error.get("code") or code)
            message = str(error.get("message") or message)
        except (ValueError, AttributeError):
            pass
        raise RendererClientError(code, message, retryable=response.status_code >= 500)

    return _extract_bundle(
        version_id=version_id,
        content=response.content,
        expected_slide_count=len(slide_specs),
    )


def _extract_bundle(
    *,
    version_id: UUID,
    content: bytes,
    expected_slide_count: int,
) -> dict[str, object]:
    output_dir = deck_assets_root() / str(version_id)
    staging_dir = output_dir.with_name(f"{output_dir.name}.staging")
    shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            for name in names:
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
                    raise RendererClientError(
                        "INVALID_RENDERER_ARCHIVE",
                        f"Unsafe renderer archive entry: {name}",
                    )
            required = {"deck.pptx", "deck.pdf", "manifest.json"}
            if not required.issubset(names):
                raise RendererClientError(
                    "INVALID_RENDERER_ARCHIVE",
                    "Renderer archive is missing required artifacts",
                )
            manifest = json.loads(archive.read("manifest.json"))
            previews = manifest.get("previews")
            if (
                manifest.get("validation", {}).get("status") != "VALID"
                or manifest.get("slideCount") != expected_slide_count
                or not isinstance(previews, list)
                or len(previews) != expected_slide_count
            ):
                raise RendererClientError(
                    "INVALID_RENDERER_MANIFEST",
                    "Renderer manifest does not match the requested presentation",
                )

            (staging_dir / "deck.pptx").write_bytes(archive.read("deck.pptx"))
            (staging_dir / "deck.pdf").write_bytes(archive.read("deck.pdf"))
            preview_paths: list[str] = []
            for index, source_name in enumerate(previews, start=1):
                if source_name not in names:
                    raise RendererClientError(
                        "INVALID_RENDERER_ARCHIVE",
                        f"Renderer archive is missing {source_name}",
                    )
                target = staging_dir / f"slide-{index:03d}.png"
                target.write_bytes(archive.read(source_name))
                preview_paths.append(str((output_dir / target.name).resolve()))

        shutil.rmtree(output_dir, ignore_errors=True)
        staging_dir.replace(output_dir)
        return {
            "pptx_storage_path": str((output_dir / "deck.pptx").resolve()),
            "pdf_storage_path": str((output_dir / "deck.pdf").resolve()),
            "preview_image_paths": preview_paths,
            "storage_size_bytes": sum(
                path.stat().st_size for path in output_dir.iterdir() if path.is_file()
            ),
        }
    except RendererClientError:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise RendererClientError(
            "INVALID_RENDERER_ARCHIVE",
            f"Could not store renderer artifacts: {exc}",
        ) from exc
