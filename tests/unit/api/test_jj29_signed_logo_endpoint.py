"""JJ-29: Gamma fetches the logo from an owned, signed HTTPS URL."""

from __future__ import annotations

import struct
import uuid
import zlib
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from services.gamma.signed_logo import mint_signed_client_logo_url

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
OWNED_BASE = "https://api.borek.test"


def _png(width: int, height: int) -> bytes:
    raw = b"".join(b"\x00" + (b"\x00\x00\x00\xff" * width) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def _headers() -> dict[str, str]:
    token = create_test_access_token(
        user_id=USER_ID,
        email="owner@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _store_logo(client: TestClient) -> tuple[str, bytes]:
    opportunity = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme Corp",
            "opportunity_name": "Invoice Automation",
            "department": "Finance",
        },
    )
    assert opportunity.status_code == 201
    opportunity_id = opportunity.json()["id"]
    png = _png(256, 128)
    uploaded = client.put(
        f"/opportunities/{opportunity_id}/client-logo",
        headers=_headers(),
        files={"file": ("acme.png", png, "image/png")},
    )
    assert uploaded.status_code == 200
    return opportunity_id, png


def test_signed_url_serves_the_logo_and_rejects_everything_else(monkeypatch) -> None:
    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", OWNED_BASE)
    monkeypatch.setattr(settings, "CLIENT_LOGO_SIGNING_SECRET", "jj29-endpoint-secret")
    client = TestClient(create_app())
    opportunity_id, png = _store_logo(client)

    url = mint_signed_client_logo_url(
        opportunity_id,
        public_api_base_url=OWNED_BASE,
        secret="jj29-endpoint-secret",
        ttl_seconds=900,
    )
    assert url is not None
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    path = parsed.path

    ok = client.get(path, params={"exp": query["exp"][0], "sig": query["sig"][0]})
    assert ok.status_code == 200
    assert ok.content == png
    assert ok.headers["content-type"].startswith("image/png")

    expired = client.get(path, params={"exp": "1", "sig": query["sig"][0]})
    assert expired.status_code == 404

    unsigned = client.get(path)
    assert unsigned.status_code == 404

    other = client.get(
        f"/public/client-logos/{uuid.uuid4()}",
        params={"exp": query["exp"][0], "sig": query["sig"][0]},
    )
    assert other.status_code == 404
