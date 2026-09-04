"""AT-58: optional client information and private opportunity logo API."""

from __future__ import annotations

import io
import struct
import uuid
import zlib

from fastapi.testclient import TestClient

from app.auth import create_test_access_token
from app.config import settings
from app.main import create_app
from app.services.client_logos import MAX_CLIENT_LOGO_BYTES
from app.services.data.memory_store import get_memory_store

USER_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
USER_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _png(width: int, height: int) -> bytes:
    raw = b"".join(b"\x00" + (b"\x00\x00\x00\xff" * width) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(raw, 9))
        + _png_chunk(b"IEND", b"")
    )


def _png_header(width: int, height: int) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr)


def _jpeg(width: int, height: int) -> bytes:
    sof = bytes(
        [
            0xFF,
            0xC0,
            0x00,
            0x11,
            0x08,
            *height.to_bytes(2, "big"),
            *width.to_bytes(2, "big"),
            0x03,
            0x01,
            0x22,
            0x00,
            0x02,
            0x11,
            0x01,
            0x03,
            0x11,
            0x01,
        ]
    )
    return b"\xff\xd8" + sof + b"\xff\xd9"


def _webp(width: int, height: int) -> bytes:
    payload = bytearray(10)
    payload[4:7] = (width - 1).to_bytes(3, "little")
    payload[7:10] = (height - 1).to_bytes(3, "little")
    chunk = b"VP8X" + (10).to_bytes(4, "little") + payload
    return b"RIFF" + (4 + len(chunk)).to_bytes(4, "little") + b"WEBP" + chunk


PNG = _png(64, 64)
JPEG = _jpeg(80, 80)
WEBP = _webp(96, 96)


def _headers(user_id: uuid.UUID = USER_A) -> dict[str, str]:
    token = create_test_access_token(
        user_id=user_id,
        email="owner@example.com",
        secret=settings.SUPABASE_JWT_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _create(client: TestClient, **extra: object) -> dict:
    response = client.post(
        "/opportunities",
        headers=_headers(),
        json={
            "client_name": "Acme",
            "opportunity_name": "Automation",
            "department": "Finance",
            **extra,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_fast_path_remains_backward_compatible_and_information_is_optional() -> None:
    with TestClient(create_app()) as client:
        created = _create(client)
        assert created["additional_client_information"] is None


def test_create_and_patch_structured_additional_client_information() -> None:
    information = {
        "location_requirements": ["EU hosting", "Berlin delivery"],
        "constraints": ["Go-live by Q4"],
        "contacts": [
            {
                "name": "Ada Lovelace",
                "role": "Sponsor",
                "email": "ada@example.com",
            }
        ],
        "priorities": ["Accuracy", "Auditability"],
        "notes": "Procurement review is pending.",
    }
    with TestClient(create_app()) as client:
        created = _create(client, additional_client_information=information)
        assert created["additional_client_information"]["location_requirements"] == [
            "EU hosting",
            "Berlin delivery",
        ]
        assert created["additional_client_information"]["contacts"][0]["email"] == (
            "ada@example.com"
        )
        patched = client.patch(
            f"/opportunities/{created['id']}",
            headers=_headers(),
            json={
                "additional_client_information": {
                    **information,
                    "priorities": ["Speed"],
                }
            },
        )
        assert patched.status_code == 200
        assert patched.json()["additional_client_information"]["priorities"] == ["Speed"]
        cleared = client.patch(
            f"/opportunities/{created['id']}",
            headers=_headers(),
            json={"additional_client_information": None},
        )
        assert cleared.status_code == 200
        assert cleared.json()["additional_client_information"] is None


def test_logo_upload_get_replace_delete_and_audit() -> None:
    with TestClient(create_app()) as client:
        opportunity = _create(client)
        path = f"/opportunities/{opportunity['id']}/client-logo"
        content_path = f"{path}/content"

        uploaded = client.put(
            path,
            headers=_headers(),
            files={"file": ("brand.png", io.BytesIO(PNG), "image/png")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["file_name"] == "brand.png"
        assert uploaded.json()["size_bytes"] == len(PNG)
        assert uploaded.json()["width_px"] == 64
        assert uploaded.json()["height_px"] == 64
        assert "storage_path" not in uploaded.json()
        logo_id = uploaded.json()["id"]

        metadata = client.get(path, headers=_headers())
        assert metadata.status_code == 200
        assert metadata.json()["id"] == logo_id
        assert metadata.json()["width_px"] == 64

        bytes_response = client.get(content_path, headers=_headers())
        assert bytes_response.status_code == 200
        assert bytes_response.content == PNG
        assert bytes_response.headers["content-type"].startswith("image/png")
        assert "brand.png" in bytes_response.headers["content-disposition"]

        replaced = client.put(
            path,
            headers=_headers(),
            files={"file": ("brand.jpg", io.BytesIO(JPEG), "image/jpeg")},
        )
        assert replaced.status_code == 200
        assert replaced.json()["id"] == logo_id
        assert replaced.json()["file_name"] == "brand.jpg"
        assert replaced.json()["width_px"] == 80
        assert replaced.json()["height_px"] == 80
        assert client.get(content_path, headers=_headers()).content == JPEG

        webp = client.put(
            path,
            headers=_headers(),
            files={"file": ("brand.webp", io.BytesIO(WEBP), "image/webp")},
        )
        assert webp.status_code == 200
        assert webp.json()["width_px"] == 96
        assert webp.json()["height_px"] == 96

        deleted = client.delete(path, headers=_headers())
        assert deleted.status_code == 204
        assert client.get(path, headers=_headers()).status_code == 404
        assert client.get(content_path, headers=_headers()).status_code == 404

        actions = [
            row["action"]
            for row in get_memory_store().list_audit_logs(actor_id=USER_A)
            if row["object_type"] == "client_logo"
        ]
        assert actions == [
            "client_logo.upload",
            "client_logo.replace",
            "client_logo.replace",
            "client_logo.delete",
        ]


def test_logo_is_opportunity_and_user_scoped_in_memory_store() -> None:
    with TestClient(create_app()) as client:
        opportunity = _create(client)
        path = f"/opportunities/{opportunity['id']}/client-logo"
        assert client.put(
            path,
            headers=_headers(),
            files={"file": ("brand.png", io.BytesIO(PNG), "image/png")},
        ).status_code == 200
        assert client.get(path, headers=_headers(USER_B)).status_code == 404
        assert client.get(f"{path}/content", headers=_headers(USER_B)).status_code == 404


def test_additional_client_information_rejects_unknown_and_blank_fields() -> None:
    with TestClient(create_app()) as client:
        unknown = client.post(
            "/opportunities",
            headers=_headers(),
            json={
                "client_name": "Acme",
                "opportunity_name": "Automation",
                "department": "Finance",
                "additional_client_information": {
                    "notes": "ok",
                    "secret_strategy": "must not be stored",
                },
            },
        )
        assert unknown.status_code == 422
        blank = client.post(
            "/opportunities",
            headers=_headers(),
            json={
                "client_name": "Acme",
                "opportunity_name": "Automation",
                "department": "Finance",
                "additional_client_information": {"priorities": ["  "]},
            },
        )
        assert blank.status_code == 422


def test_logo_rejects_unsupported_mime_mismatched_bytes_and_oversize() -> None:
    with TestClient(create_app()) as client:
        opportunity = _create(client)
        path = f"/opportunities/{opportunity['id']}/client-logo"
        cases = [
            (("brand.svg", io.BytesIO(b"<svg/>"), "image/svg+xml"), "INVALID_CLIENT_LOGO_FORMAT"),
            (("brand.png", io.BytesIO(b"not-an-image"), "image/png"), "INVALID_CLIENT_LOGO_CONTENT"),
            (
                (
                    "brand.png",
                    io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * MAX_CLIENT_LOGO_BYTES),
                    "image/png",
                ),
                "CLIENT_LOGO_TOO_LARGE",
            ),
            (
                ("tiny.png", io.BytesIO(_png(32, 32)), "image/png"),
                "CLIENT_LOGO_DIMENSIONS_INVALID",
            ),
            (
                ("huge.png", io.BytesIO(_png_header(4097, 64)), "image/png"),
                "CLIENT_LOGO_DIMENSIONS_INVALID",
            ),
        ]
        for file_value, expected_code in cases:
            response = client.put(path, headers=_headers(), files={"file": file_value})
            assert response.status_code == 400
            assert response.json()["error"]["code"] == expected_code
