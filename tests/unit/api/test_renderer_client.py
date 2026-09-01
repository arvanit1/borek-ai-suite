from __future__ import annotations

import io
import json
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.config import settings
from app.services.renderer_client import RendererClientError, _extract_bundle


def _bundle(*, unsafe_name: str | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("deck.pptx", b"PK-rendered-deck")
        archive.writestr("deck.pdf", b"%PDF-rendered-deck")
        archive.writestr("slide-01.png", b"png")
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "pptx": "deck.pptx",
                    "pdf": "deck.pdf",
                    "previews": ["slide-01.png"],
                    "slideCount": 1,
                    "validation": {"status": "VALID", "issues": []},
                }
            ),
        )
        if unsafe_name:
            archive.writestr(unsafe_name, b"unsafe")
    return output.getvalue()


def test_extract_renderer_bundle_stores_private_normalized_assets(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    version_id = uuid.uuid4()

    assets = _extract_bundle(
        version_id=version_id,
        content=_bundle(),
        expected_slide_count=1,
    )

    assert (tmp_path / str(version_id) / "deck.pptx").read_bytes() == b"PK-rendered-deck"
    assert (tmp_path / str(version_id) / "slide-001.png").read_bytes() == b"png"
    assert assets["storage_size_bytes"] > 0


def test_extract_renderer_bundle_replaces_existing_output_dir(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    version_id = uuid.uuid4()
    stale_dir = tmp_path / str(version_id)
    stale_dir.mkdir(parents=True)
    (stale_dir / "deck.pptx").write_bytes(b"stale")

    assets = _extract_bundle(
        version_id=version_id,
        content=_bundle(),
        expected_slide_count=1,
    )

    assert (tmp_path / str(version_id) / "deck.pptx").read_bytes() == b"PK-rendered-deck"
    assert assets["storage_size_bytes"] > 0


def test_extract_renderer_bundle_rejects_path_traversal(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))

    with pytest.raises(RendererClientError, match="Unsafe renderer archive entry"):
        _extract_bundle(
            version_id=uuid.uuid4(),
            content=_bundle(unsafe_name="../escape.txt"),
            expected_slide_count=1,
        )


def test_extract_renderer_bundle_preserves_existing_assets_on_invalid_replacement(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    version_id = uuid.uuid4()
    output_dir = tmp_path / str(version_id)
    output_dir.mkdir(parents=True)
    (output_dir / "deck.pptx").write_bytes(b"previous-valid-deck")

    with pytest.raises(RendererClientError, match="Unsafe renderer archive entry"):
        _extract_bundle(
            version_id=version_id,
            content=_bundle(unsafe_name="../escape.txt"),
            expected_slide_count=1,
        )

    assert (output_dir / "deck.pptx").read_bytes() == b"previous-valid-deck"


def test_extract_renderer_bundle_serializes_same_version_publication(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ARTIFACT_ROOT", str(tmp_path))
    version_id = uuid.uuid4()

    def extract() -> dict[str, object]:
        return _extract_bundle(
            version_id=version_id,
            content=_bundle(),
            expected_slide_count=1,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: extract(), range(2)))

    assert len(results) == 2
    assert (tmp_path / str(version_id) / "deck.pptx").read_bytes() == b"PK-rendered-deck"
