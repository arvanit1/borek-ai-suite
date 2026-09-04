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

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, *, destination_path: str, content: bytes, content_type: str) -> str:
        del content_type
        target = _writable_path(self.root.joinpath(*Path(destination_path).parts))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return f"fixture://enterprise/{destination_path}"


class LiveEnterpriseStore:
    """Generic authenticated PUT. Replace once O2 names SharePoint or equivalent."""

    def __init__(self, *, base_url: str, token: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds

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


def build_enterprise_destination():
    if settings.FILING_DESTINATION != "live":
        return FixtureEnterpriseStore(deck_assets_root() / "enterprise")
    return LiveEnterpriseStore(
        base_url=settings.ENTERPRISE_REPOSITORY_URL.strip(),
        token=settings.ENTERPRISE_REPOSITORY_TOKEN.strip(),
        timeout_seconds=settings.ENTERPRISE_REPOSITORY_TIMEOUT_SECONDS,
    )
