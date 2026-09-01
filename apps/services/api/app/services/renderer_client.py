"""HTTP client for the stateless renderer artifact bundle."""

from __future__ import annotations

import io
import json
import os
import shutil
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

if os.name == "nt":
    import msvcrt
else:
    import fcntl

import httpx

from app.config import settings
from app.services.deck_assets import deck_assets_root

_publication_locks: dict[UUID, Lock] = {}
_publication_locks_guard = Lock()


@contextmanager
def _process_publication_lock(version_id: UUID) -> Iterator[None]:
    lock_path = deck_assets_root() / f".{version_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        if os.name == "nt":
            if lock_path.stat().st_size == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def _publication_lock(version_id: UUID) -> Iterator[None]:
    with _publication_locks_guard:
        thread_lock = _publication_locks.setdefault(version_id, Lock())
    with thread_lock, _process_publication_lock(version_id):
        yield


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
    invocation_id = uuid4().hex
    staging_dir = output_dir.with_name(f"{output_dir.name}.staging-{invocation_id}")
    backup_dir = output_dir.with_name(f"{output_dir.name}.backup-{invocation_id}")
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

        with _publication_lock(version_id):
            if output_dir.exists():
                output_dir.replace(backup_dir)
            try:
                staging_dir.replace(output_dir)
            except OSError:
                if backup_dir.exists() and not output_dir.exists():
                    backup_dir.replace(output_dir)
                raise
            shutil.rmtree(backup_dir, ignore_errors=True)
            storage_size_bytes = sum(
                path.stat().st_size for path in output_dir.iterdir() if path.is_file()
            )

        return {
            "pptx_storage_path": str((output_dir / "deck.pptx").resolve()),
            "pdf_storage_path": str((output_dir / "deck.pdf").resolve()),
            "preview_image_paths": preview_paths,
            "storage_size_bytes": storage_size_bytes,
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
