"""AT-10: render validation checks tests."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RENDERER_DIR = ROOT / "apps" / "renderer"
PLAN_FIXTURE = ROOT / "packages" / "contracts" / "fixtures" / "presentation_plan.minimal.json"
RENDER_CHECKS_CLI = RENDERER_DIR / "scripts" / "run_render_checks.ts"
WORKER_RENDER_VALIDATE = ROOT / "apps" / "worker" / "tasks" / "render_validate.py"
AT9_E2E_IMAGE = "borek-at9-e2e"


def _run_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=check, shell=True, text=True, capture_output=True)


def _docker_available() -> bool:
    result = subprocess.run(["docker", "ps"], cwd=ROOT, capture_output=True, text=True)
    return result.returncode == 0


def _ensure_at9_e2e_image() -> None:
    build = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            AT9_E2E_IMAGE,
            "-f",
            str(ROOT / "scripts" / "docker" / "at9-e2e" / "Dockerfile"),
            str(ROOT),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr or build.stdout


def test_at10_renderer_unit_checks() -> None:
    result = _run_shell("npm run test:at10 --workspace borek-renderer")
    assert result.returncode == 0, result.stderr or result.stdout
    assert "AT-10 renderer unit checks passed" in result.stdout


def test_at10_cli_flags_render_exception_for_missing_preview(tmp_path: Path) -> None:
    missing_preview = tmp_path / "missing-preview.json"
    result = _run_shell(
        f'npx tsx "{RENDER_CHECKS_CLI}" "{PLAN_FIXTURE}" "{missing_preview}"',
        check=False,
    )
    assert result.returncode == 1


def test_at10_worker_wrapper_invokes_render_checks_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"status": "VALID", "issues": []}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    spec = importlib.util.spec_from_file_location("render_validate", WORKER_RENDER_VALIDATE)
    assert spec and spec.loader
    render_validate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render_validate)

    plan = tmp_path / "plan.json"
    preview = tmp_path / "preview.json"
    plan.write_text(PLAN_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    preview.write_text("{}", encoding="utf-8")

    result = render_validate.run_render_validation(plan, preview)
    assert result["status"] == "VALID"
    assert calls
    assert any(str(RENDER_CHECKS_CLI) in part for part in calls[0])


@pytest.mark.skipif(not _docker_available(), reason="Docker required for AT-10 E2E")
def test_at10_passes_after_at9_preview_pipeline(tmp_path: Path) -> None:
    _ensure_at9_e2e_image()
    docker_output = ROOT / "tmp" / "at10-e2e-preview"
    if docker_output.exists():
        import shutil

        shutil.rmtree(docker_output)
    docker_output.mkdir(parents=True, exist_ok=True)

    preview_run = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{docker_output}:/workspace/tmp/at10-e2e-preview",
            AT9_E2E_IMAGE,
            "npx",
            "tsx",
            "apps/renderer/scripts/run_preview_pipeline.ts",
            "tests/fixtures/renderer/minimal.pptx",
            "tmp/at10-e2e-preview",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert preview_run.returncode == 0, preview_run.stderr or preview_run.stdout
    preview_payload = json.loads(preview_run.stdout.strip())

    single_slide_plan = {
        "schema_version": "1.0",
        "title": "Single slide plan",
        "slides": [
            {
                "order": 1,
                "purpose": "cover",
                "layoutId": "COVER_01",
                "frameworkReferences": ["opportunity"],
            }
        ],
    }
    plan_path = tmp_path / "single-slide-plan.json"
    preview_path = tmp_path / "preview.json"
    plan_path.write_text(json.dumps(single_slide_plan), encoding="utf-8")
    preview_path.write_text(json.dumps(preview_payload), encoding="utf-8")

    checks_run = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{docker_output}:/workspace/tmp/at10-e2e-preview",
            "-v",
            f"{tmp_path}:/tmp/at10",
            AT9_E2E_IMAGE,
            "npx",
            "tsx",
            "apps/renderer/scripts/run_render_checks.ts",
            "/tmp/at10/single-slide-plan.json",
            "/tmp/at10/preview.json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert checks_run.returncode == 0, checks_run.stderr or checks_run.stdout
    payload = json.loads(checks_run.stdout.strip())
    assert payload["status"] == "VALID"


def test_at10_fails_when_plan_expects_more_slides_than_preview(tmp_path: Path) -> None:
    preview_payload = {
        "pdfPath": str(tmp_path / "deck.pdf"),
        "slideImagePaths": [str(tmp_path / "slide-01.png")],
    }
    (tmp_path / "deck.pdf").write_bytes(b"%PDF-1.4")
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x08\x00\x00\x00\x08\x08\x02\x00\x00\x00=\xF6\xCF\x10"
        b"\x00\x00\x00\x19IDATx\x9cc``\xF8\xFF\xFF?\x03\x05\xA0\x02\x00\x04\xFC\x02\xFE\x1B\xd5\xc4\xf8"
        b"\x00\x00\x00\x00IEND\xAEB`\x82"
    )
    (tmp_path / "slide-01.png").write_bytes(png_bytes)

    plan_path = tmp_path / "plan.json"
    preview_path = tmp_path / "preview.json"
    plan_path.write_text(PLAN_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    preview_path.write_text(json.dumps(preview_payload), encoding="utf-8")

    result = _run_shell(
        f'npx tsx "{RENDER_CHECKS_CLI}" "{plan_path}" "{preview_path}"',
        check=False,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout.strip())
    assert payload["status"] == "VALIDATION_FAILED"
    assert any(issue["code"] == "SLIDE_COUNT_MISMATCH" for issue in payload["issues"])
