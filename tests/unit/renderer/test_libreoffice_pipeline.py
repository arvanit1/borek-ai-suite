"""AT-9: LibreOffice render-validation pipeline tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RENDERER_DIR = ROOT / "apps" / "renderer"
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "renderer"
FIXTURE_PPTX = FIXTURES_DIR / "minimal.pptx"
BUILD_FIXTURE_SCRIPT = FIXTURES_DIR / "build_minimal_pptx.py"
PREVIEW_CLI = RENDERER_DIR / "scripts" / "run_preview_pipeline.ts"
AT9_E2E_DOCKERFILE = ROOT / "scripts" / "docker" / "at9-e2e" / "Dockerfile"
AT9_E2E_IMAGE = "borek-at9-e2e"
WORKER_PREVIEW = ROOT / "apps" / "worker" / "tasks" / "preview_render.py"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def _tool_available(command: str) -> bool:
    lookup = "where" if sys.platform == "win32" else "which"
    result = subprocess.run([lookup, command], cwd=ROOT, capture_output=True, text=True)
    return result.returncode == 0


def _docker_available() -> bool:
    result = subprocess.run(["docker", "version"], cwd=ROOT, capture_output=True, text=True)
    return result.returncode == 0


def _libreoffice_tools_available() -> bool:
    for key in ("SOFFICE_PATH", "LIBREOFFICE_PATH"):
        value = __import__("os").environ.get(key)
        if value and Path(value).is_file():
            return _tool_available("pdftoppm")
    return _tool_available("soffice") and _tool_available("pdftoppm")


def _assert_preview_payload(payload: dict[str, object]) -> None:
    pdf_path = Path(str(payload["pdfPath"]))
    slide_paths = [Path(str(path)) for path in payload["slideImagePaths"]]

    assert pdf_path.is_file(), "pipeline must produce a PDF"
    assert pdf_path.suffix == ".pdf"
    assert len(slide_paths) >= 1, "pipeline must produce at least one slide PNG"

    for index, slide_path in enumerate(slide_paths, start=1):
        assert slide_path.is_file(), f"missing slide image: {slide_path}"
        assert slide_path.suffix == ".png"
        assert slide_path.name == f"slide-{index:02d}.png"

    assert not any(path.name == "slide-1.png" for path in slide_paths), (
        "slide images must use zero-padded names (slide-01.png)"
    )


def _run_local_preview_pipeline(pptx_path: Path, output_dir: Path) -> dict[str, object]:
    result = _run_shell(
        f'npx tsx "{PREVIEW_CLI}" "{pptx_path}" "{output_dir}"',
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout.strip())


def _ensure_at9_e2e_image() -> None:
    build = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            AT9_E2E_IMAGE,
            "-f",
            str(AT9_E2E_DOCKERFILE),
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr or build.stdout


def _run_docker_preview_pipeline(pptx_path: Path) -> dict[str, object]:
    _ensure_at9_e2e_image()
    docker_output = ROOT / "tmp" / "at9-e2e-preview"
    if docker_output.exists():
        shutil.rmtree(docker_output)
    docker_output.mkdir(parents=True, exist_ok=True)

    run = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{docker_output}:/workspace/tmp/at9-e2e-preview",
            AT9_E2E_IMAGE,
            "npx",
            "tsx",
            "apps/renderer/scripts/run_preview_pipeline.ts",
            "tests/fixtures/renderer/minimal.pptx",
            "tmp/at9-e2e-preview",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert run.returncode == 0, run.stderr or run.stdout
    payload = json.loads(run.stdout.strip())

    pdf_path = docker_output / Path(str(payload["pdfPath"])).name
    slide_paths = [docker_output / Path(str(path)).name for path in payload["slideImagePaths"]]
    host_payload = {
        "pdfPath": str(pdf_path),
        "slideImagePaths": [str(path) for path in slide_paths],
    }
    return host_payload


@pytest.fixture(scope="module")
def minimal_pptx() -> Path:
    if not FIXTURE_PPTX.is_file():
        subprocess.run([sys.executable, str(BUILD_FIXTURE_SCRIPT)], cwd=ROOT, check=True)
    assert FIXTURE_PPTX.is_file(), "minimal.pptx fixture must exist for AT-9 tests"
    return FIXTURE_PPTX


def test_at9_renderer_unit_checks() -> None:
    """Pure AT-9 helpers and missing-input errors (no LibreOffice required)."""
    result = _run_shell("npm run test:at9 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
    assert "AT-9 renderer unit checks passed" in result.stdout


def test_at9_typecheck_includes_validation_modules() -> None:
    _run_shell("npm run typecheck --workspace borek-renderer")


def test_at9_cli_rejects_missing_arguments() -> None:
    result = _run_shell(f'npx tsx "{PREVIEW_CLI}"', check=False)
    assert result.returncode == 1
    assert "Usage:" in (result.stderr or result.stdout)


def test_at9_cli_rejects_missing_pptx() -> None:
    missing = FIXTURES_DIR / "does-not-exist.pptx"
    output_dir = FIXTURES_DIR / "_preview_missing"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    result = _run_shell(
        f'npx tsx "{PREVIEW_CLI}" "{missing}" "{output_dir}"',
        check=False,
    )
    assert result.returncode == 1
    assert "PPTX input file not found" in (result.stderr or result.stdout)


def test_at9_pipeline_produces_pdf_and_per_slide_pngs(minimal_pptx: Path, tmp_path: Path) -> None:
    if _libreoffice_tools_available():
        payload = _run_local_preview_pipeline(minimal_pptx, tmp_path / "preview")
    elif _docker_available():
        payload = _run_docker_preview_pipeline(minimal_pptx)
    else:
        pytest.fail("AT-9 E2E requires LibreOffice+pdftoppm locally or Docker")

    _assert_preview_payload(payload)


def test_at9_worker_wrapper_invokes_preview_cli(minimal_pptx: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util

    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "pdfPath": str(tmp_path / "minimal.pdf"),
                    "slideImagePaths": [str(tmp_path / "slide-01.png")],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    spec = importlib.util.spec_from_file_location("preview_render", WORKER_PREVIEW)
    assert spec and spec.loader
    preview_render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview_render)

    result = preview_render.run_preview_render(minimal_pptx, tmp_path / "worker-preview")

    assert result["pdfPath"].endswith("minimal.pdf")
    assert calls, "worker wrapper must invoke preview CLI"
    assert calls[0][0] == "npx"
    assert any(str(PREVIEW_CLI) in part for part in calls[0])
