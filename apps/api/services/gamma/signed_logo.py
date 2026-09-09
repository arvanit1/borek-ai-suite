"""JJ-29: short-lived HTTPS URLs so Gamma can fetch a quality-gated client logo.

The JJ-27 gate decides whether a logo is placeable. This module only mints a URL
for a logo that already passed, under an owned host. Private `artifact:` and
`s3://` references are never returned. Failure to sign is silent here — the
caller falls back to the client-name wordmark.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any
from uuid import UUID

from services.gamma.template import load_gamma_template

SIGNED_LOGO_PATH = "/public/client-logos/"
DEFAULT_TTL_SECONDS = 900


def owned_https_prefixes() -> tuple[str, ...]:
    """Hosts Gamma may fetch. JSON prefixes plus the configured public API base."""
    configured = _prefix_from_public_base(_public_api_base_url())
    extra = (configured,) if configured else ()
    return tuple(dict.fromkeys((*load_gamma_template().client_logo.signed_url_prefixes, *extra)))


def mint_signed_client_logo_url(
    opportunity_id: UUID | str,
    *,
    public_api_base_url: str | None = None,
    secret: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: int | None = None,
) -> str | None:
    """Return an owned HTTPS URL, or None when the URL cannot be minted."""
    prefix = _prefix_from_public_base(
        public_api_base_url if public_api_base_url is not None else _public_api_base_url()
    )
    signing_secret = (secret if secret is not None else _signing_secret()).strip()
    if prefix is None or not signing_secret or ttl_seconds <= 0:
        return None
    expires_at = int(now if now is not None else time.time()) + int(ttl_seconds)
    token = _signature(str(opportunity_id), expires_at, signing_secret)
    return f"{prefix}{opportunity_id}?exp={expires_at}&sig={token}"


def verify_signed_client_logo_request(
    opportunity_id: UUID | str,
    *,
    exp: str,
    signature: str,
    secret: str | None = None,
    now: int | None = None,
) -> bool:
    """True only for a timely HMAC issued by this host. Fail closed otherwise."""
    signing_secret = (secret if secret is not None else _signing_secret()).strip()
    if not signing_secret or not signature or not exp:
        return False
    try:
        expires_at = int(exp)
    except (TypeError, ValueError):
        return False
    if expires_at < int(now if now is not None else time.time()):
        return False
    expected = _signature(str(opportunity_id), expires_at, signing_secret)
    try:
        return hmac.compare_digest(expected, signature.strip().lower())
    except (TypeError, ValueError):
        return False


def _prefix_from_public_base(base: str) -> str | None:
    cleaned = (base or "").strip().rstrip("/")
    if not cleaned.startswith("https://"):
        return None
    return f"{cleaned}{SIGNED_LOGO_PATH}"


def _signature(opportunity_id: str, expires_at: int, secret: str) -> str:
    payload = f"{opportunity_id}:{expires_at}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _public_api_base_url() -> str:
    return str(_setting("PUBLIC_API_BASE_URL") or os.environ.get("PUBLIC_API_BASE_URL", "")).strip()


def _signing_secret() -> str:
    return str(
        _setting("CLIENT_LOGO_SIGNING_SECRET")
        or _setting("SUPABASE_JWT_SECRET")
        or os.environ.get("CLIENT_LOGO_SIGNING_SECRET", "")
        or os.environ.get("SUPABASE_JWT_SECRET", "")
    ).strip()


def _setting(name: str) -> Any:
    try:
        from app.config import settings

        return getattr(settings, name, "")
    except Exception:
        return ""
