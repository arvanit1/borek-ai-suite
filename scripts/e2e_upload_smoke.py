#!/usr/bin/env python3
"""AT-46 end-to-end smoke test: auth → opportunity → transcript upload."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def http_json(method: str, url: str, headers: dict[str, str], body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def http_multipart(url: str, headers: dict[str, str], file_name: str, content: bytes) -> dict:
    boundary = f"----borek-e2e-{uuid.uuid4().hex}"
    parts = [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'.encode(),
        b"Content-Type: text/plain\r\n\r\n",
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    request = Request(
        url,
        data=body,
        headers={
            **headers,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def supabase_token(supabase_url: str, anon_key: str) -> str | None:
    auth_headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
    }
    email = os.environ.get("E2E_TEST_EMAIL", "").strip()
    password = os.environ.get("E2E_TEST_PASSWORD", "").strip()
    if not email or not password:
        return None
    signin = http_json(
        "POST",
        f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        auth_headers,
        {"email": email, "password": password},
    )
    return signin.get("access_token")


def main() -> int:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "apps" / "web" / ".env.local")

    api_base = os.environ.get("NEXT_PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    web_base = os.environ.get("NEXT_PUBLIC_WEB_URL", "http://localhost:3000").rstrip("/")
    supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
    anon_key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")

    print("=== AT-46 E2E smoke test ===")

    health = http_json("GET", f"{api_base}/health", {})
    assert health.get("status") == "ok", health
    print("[OK] API health")

    with urlopen(f"{web_base}/upload", timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    for needle in ("Transcript ingestion", "Browse files", "Create opportunity"):
        assert needle in html, f"Missing UI marker: {needle}"
    print("[OK] Upload page HTML")

    with urlopen(f"{web_base}/login", timeout=30) as response:
        login_html = response.read().decode("utf-8", errors="replace")
    assert "Sign in" in login_html and "Register" in login_html
    print("[OK] Login page HTML")

    token: str | None = None
    if supabase_url and anon_key:
        try:
            token = supabase_token(supabase_url, anon_key)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            print(f"[FAIL] Supabase sign-in: {body}")
            return 1

    if not token:
        print(
            "[SKIP] Authenticated API flow — set E2E_TEST_EMAIL and E2E_TEST_PASSWORD in .env "
            "(use the account you registered in the browser)."
        )
        print("[OK] Client-side validation covered by npm run test:at46")
        return 0

    print("[OK] Supabase sign-in")

    bearer = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    opportunity = http_json(
        "POST",
        f"{api_base}/opportunities",
        bearer,
        {
            "client_name": "E2E Client",
            "opportunity_name": f"Smoke {uuid.uuid4().hex[:6]}",
            "department": "Sales Engineering",
            "language": "en",
        },
    )
    opportunity_id = opportunity["id"]
    print(f"[OK] POST /opportunities -> {opportunity_id}")

    upload = http_multipart(
        f"{api_base}/opportunities/{opportunity_id}/transcripts",
        {"Authorization": f"Bearer {token}"},
        "e2e-sample.txt",
        b"Discovery call transcript for E2E smoke test.\n",
    )
    assert upload.get("transcript", {}).get("id"), upload
    print(f"[OK] POST /transcripts -> {upload['transcript']['id']}")

    try:
        http_multipart(
            f"{api_base}/opportunities/{opportunity_id}/transcripts",
            {"Authorization": f"Bearer {token}"},
            "bad.pdf",
            b"%PDF-1.4",
        )
        print("[FAIL] API should reject .pdf upload")
        return 1
    except HTTPError as exc:
        assert exc.code == 400, exc.code
        print("[OK] API rejects .pdf (400)")

    print("\n=== ALL E2E CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
