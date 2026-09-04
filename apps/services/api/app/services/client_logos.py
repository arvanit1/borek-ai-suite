"""Validation helpers for private opportunity client logos (AT-58)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.api_errors import bad_request

MAX_CLIENT_LOGO_BYTES = 5 * 1024 * 1024
MIN_CLIENT_LOGO_EDGE_PX = 64
MAX_CLIENT_LOGO_EDGE_PX = 4096
SUPPORTED_CLIENT_LOGOS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


@dataclass(frozen=True)
class ValidatedClientLogo:
    mime_type: str
    width_px: int
    height_px: int


def validate_client_logo(
    file_name: str,
    mime_type: str | None,
    content: bytes,
) -> ValidatedClientLogo:
    normalized_mime = (mime_type or "").lower().split(";", 1)[0].strip()
    expected_extension = SUPPORTED_CLIENT_LOGOS.get(normalized_mime)
    if expected_extension is None:
        raise bad_request(
            "INVALID_CLIENT_LOGO_FORMAT",
            "Client logo must be a PNG, JPEG, or WebP image",
        )
    extension = Path(file_name).suffix.lower()
    valid_extensions = {expected_extension}
    if normalized_mime == "image/jpeg":
        valid_extensions.add(".jpeg")
    if extension not in valid_extensions:
        raise bad_request(
            "INVALID_CLIENT_LOGO_FORMAT",
            "Client logo filename extension does not match its MIME type",
        )
    if not content:
        raise bad_request("INVALID_CLIENT_LOGO_CONTENT", "Client logo cannot be empty")
    if len(content) > MAX_CLIENT_LOGO_BYTES:
        raise bad_request(
            "CLIENT_LOGO_TOO_LARGE",
            f"Client logo cannot exceed {MAX_CLIENT_LOGO_BYTES} bytes",
        )
    signatures_valid = {
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/webp": (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        ),
    }
    if not signatures_valid[normalized_mime]:
        raise bad_request(
            "INVALID_CLIENT_LOGO_CONTENT",
            "Client logo bytes do not match the declared image type",
        )
    try:
        width_px, height_px = read_client_logo_dimensions(normalized_mime, content)
    except ValueError as exc:
        raise bad_request("INVALID_CLIENT_LOGO_CONTENT", str(exc)) from exc
    if (
        width_px < MIN_CLIENT_LOGO_EDGE_PX
        or height_px < MIN_CLIENT_LOGO_EDGE_PX
        or width_px > MAX_CLIENT_LOGO_EDGE_PX
        or height_px > MAX_CLIENT_LOGO_EDGE_PX
    ):
        raise bad_request(
            "CLIENT_LOGO_DIMENSIONS_INVALID",
            (
                "Client logo must be between "
                f"{MIN_CLIENT_LOGO_EDGE_PX}x{MIN_CLIENT_LOGO_EDGE_PX} and "
                f"{MAX_CLIENT_LOGO_EDGE_PX}x{MAX_CLIENT_LOGO_EDGE_PX} pixels"
            ),
        )
    return ValidatedClientLogo(
        mime_type=normalized_mime,
        width_px=width_px,
        height_px=height_px,
    )


def read_client_logo_dimensions(mime_type: str, content: bytes) -> tuple[int, int]:
    if mime_type == "image/png":
        return _png_dimensions(content)
    if mime_type == "image/jpeg":
        return _jpeg_dimensions(content)
    if mime_type == "image/webp":
        return _webp_dimensions(content)
    raise ValueError("Client logo dimensions could not be read")


def _png_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 24 or content[12:16] != b"IHDR":
        raise ValueError("Client logo dimensions could not be read")
    width = int.from_bytes(content[16:20], "big")
    height = int.from_bytes(content[20:24], "big")
    if width <= 0 or height <= 0:
        raise ValueError("Client logo dimensions could not be read")
    return width, height


def _jpeg_dimensions(content: bytes) -> tuple[int, int]:
    index = 2
    length = len(content)
    while index < length - 8:
        if content[index] != 0xFF:
            index += 1
            continue
        marker = content[index + 1]
        if marker in {0xC0, 0xC1, 0xC2, 0xC3}:
            height = int.from_bytes(content[index + 5 : index + 7], "big")
            width = int.from_bytes(content[index + 7 : index + 9], "big")
            if width <= 0 or height <= 0:
                raise ValueError("Client logo dimensions could not be read")
            return width, height
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        if marker == 0x00:
            index += 1
            continue
        if index + 4 > length:
            break
        segment_length = int.from_bytes(content[index + 2 : index + 4], "big")
        if segment_length < 2:
            break
        index += 2 + segment_length
    raise ValueError("Client logo dimensions could not be read")


def _webp_dimensions(content: bytes) -> tuple[int, int]:
    if len(content) < 30 or content[12:16] not in {b"VP8 ", b"VP8L", b"VP8X"}:
        raise ValueError("Client logo dimensions could not be read")
    kind = content[12:16]
    if kind == b"VP8X":
        width = int.from_bytes(content[24:27], "little") + 1
        height = int.from_bytes(content[27:30], "little") + 1
        return _positive_dimensions(width, height)
    chunk_size = int.from_bytes(content[16:20], "little")
    payload = content[20 : 20 + chunk_size]
    if kind == b"VP8L":
        if len(payload) < 5 or payload[0] != 0x2F:
            raise ValueError("Client logo dimensions could not be read")
        bits = int.from_bytes(payload[1:5], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return _positive_dimensions(width, height)
    if len(payload) < 10 or payload[3:6] != b"\x9d\x01\x2a":
        raise ValueError("Client logo dimensions could not be read")
    width = int.from_bytes(payload[6:8], "little") & 0x3FFF
    height = int.from_bytes(payload[8:10], "little") & 0x3FFF
    return _positive_dimensions(width, height)


def _positive_dimensions(width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("Client logo dimensions could not be read")
    return width, height
