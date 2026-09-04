"""Persist owned Gamma artifacts under the private artifact root (AT-60)."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, replace
from pathlib import Path

from services.gamma.contract import GammaArtifact, GammaGenerateResult, GammaProviderError


def persist_gamma_result(
    result: GammaGenerateResult,
    *,
    artifact_root: str | Path,
) -> GammaGenerateResult:
    root = Path(artifact_root)
    stored = tuple(persist_gamma_artifact(artifact, artifact_root=root) for artifact in result.artifacts)
    return replace(result, artifacts=stored)


def persist_gamma_artifact(artifact: GammaArtifact, *, artifact_root: Path) -> GammaArtifact:
    if not artifact.content:
        raise GammaProviderError("Gamma artifact has no bytes to store.")
    if not artifact.storage_key.startswith(
        f"gamma/{artifact.owner_opportunity_id}/{artifact.owner_presentation_version_id}/"
    ):
        raise GammaProviderError("Gamma artifact storage key is not opportunity-owned.")
    target = artifact_root.joinpath(*Path(artifact.storage_key).parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(artifact.content)
    digest = hashlib.sha256(artifact.content).hexdigest()
    return replace(
        artifact,
        byte_size=len(artifact.content),
        checksum_sha256=digest,
        content=b"",
    )


def gamma_result_metadata(result: GammaGenerateResult) -> dict[str, object]:
    return {
        "generation_id": result.generation_id,
        "template_id": result.template_id,
        "template_version": result.template_version,
        "branding_locked": result.branding_locked,
        "client_logo_applied": result.client_logo_applied,
        "artifacts": [
            {
                key: value
                for key, value in asdict(artifact).items()
                if key != "content"
            }
            for artifact in result.artifacts
        ],
    }
