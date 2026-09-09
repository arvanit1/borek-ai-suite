"""Configurable enterprise destination for AT-61 artifact filing.

O2 still names the production repository. Until that decision lands:
- FILING_DESTINATION=fixture writes bytes under ARTIFACT_ROOT/enterprise
- FILING_DESTINATION=live is fail-closed without URL and token, then HTTP PUT
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from app.config import settings
from app.services.artifact_filing import ArtifactFilingError
from app.services.deck_assets import deck_assets_root


def _writable_path(path: Path) -> Path:
    resolved = path.resolve()
    text = str(resolved)
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return Path("\\\\?\\" + text)
    return resolved


class FixtureEnterpriseStore:
    """Local stand-in used until O2 names the real repository."""

    def __init__(self, root: Path, *, scheme: str = "fixture") -> None:
        self.root = root
        self.scheme = scheme
        self.backend = "fixture" if scheme == "fixture" else "in_app"

    def _target(self, destination_path: str) -> Path:
        root = self.root.resolve()
        target = root.joinpath(*Path(destination_path).parts).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ArtifactFilingError(
                "INVALID_DESTINATION_PATH",
                "Artifact destination must remain inside the repository root",
                retryable=False,
            ) from exc
        return _writable_path(target)

    def put(self, *, destination_path: str, content: bytes, content_type: str) -> str:
        del content_type
        target = self._target(destination_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return f"{self.scheme}://enterprise/{destination_path}"

    def get(self, *, destination_path: str) -> bytes:
        target = self._target(destination_path)
        if not target.is_file():
            raise ArtifactFilingError(
                "FILED_ARTIFACT_NOT_FOUND",
                "The filed artifact is no longer available",
                retryable=False,
            )
        return target.read_bytes()


class LiveEnterpriseStore:
    """Generic authenticated PUT. Replace once O2 names SharePoint or equivalent."""

    def __init__(self, *, base_url: str, token: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.backend = "live"

    def put(self, *, destination_path: str, content: bytes, content_type: str) -> str:
        if not self.base_url or not self.token:
            raise ArtifactFilingError(
                "ENTERPRISE_REPOSITORY_NOT_CONFIGURED",
                "Enterprise repository URL and token are required once O2 names the destination",
                retryable=False,
            )
        url = f"{self.base_url}/{destination_path}"
        try:
            response = httpx.put(
                url,
                content=content,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": content_type,
                },
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            error = ArtifactFilingError(
                "ENTERPRISE_REPOSITORY_TIMEOUT",
                "Enterprise repository timed out",
                retryable=True,
            )
            raise error from exc
        except httpx.HTTPError as exc:
            error = ArtifactFilingError(
                "ENTERPRISE_REPOSITORY_UNAVAILABLE",
                "Enterprise repository is unavailable",
                retryable=True,
            )
            raise error from exc

        if response.status_code in {401, 403}:
            raise ArtifactFilingError(
                "ENTERPRISE_REPOSITORY_NOT_CONFIGURED",
                "Enterprise repository rejected the configured credential",
                retryable=False,
            )
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise ArtifactFilingError(
                "ENTERPRISE_REPOSITORY_UNAVAILABLE",
                f"Enterprise repository returned HTTP {response.status_code}",
                retryable=True,
            )
        if response.status_code >= 400:
            raise ArtifactFilingError(
                "ENTERPRISE_REPOSITORY_REJECTED",
                f"Enterprise repository rejected the artifact with HTTP {response.status_code}",
                retryable=False,
            )
        location = response.headers.get("Location") or url
        return str(location)

    def get(self, *, destination_path: str) -> bytes:
        del destination_path
        raise ArtifactFilingError(
            "ENTERPRISE_REPOSITORY_READ_NOT_CONFIGURED",
            "External repository retrieval waits for the O2 adapter",
            retryable=False,
        )


def build_enterprise_destination(mode: str | None = None):
    selected = mode or settings.FILING_DESTINATION
    if selected != "live":
        scheme = "fixture" if selected == "fixture" else "in-app"
        return FixtureEnterpriseStore(deck_assets_root() / "enterprise", scheme=scheme)
    return LiveEnterpriseStore(
        base_url=settings.ENTERPRISE_REPOSITORY_URL.strip(),
        token=settings.ENTERPRISE_REPOSITORY_TOKEN.strip(),
        timeout_seconds=settings.ENTERPRISE_REPOSITORY_TIMEOUT_SECONDS,
    )
