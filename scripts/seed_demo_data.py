"""Install the owner-scoped MS-30 demo pack."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    load_dotenv(ROOT / ".env")
    profile = os.getenv("RUNTIME_PROFILE", "development").strip().lower()
    if profile == "production":
        print("Refusing to install demo data under the production runtime profile.", file=sys.stderr)
        return 2
    if not _enabled(os.getenv("DEMO_DATA_ENABLED")):
        print("Demo data is disabled. Set DEMO_DATA_ENABLED=true to install it.", file=sys.stderr)
        return 2
    token = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip()
    if not token:
        print("SUPABASE_ACCESS_TOKEN is required so demo data is scoped to the calling user.", file=sys.stderr)
        return 2

    sys.path.insert(0, str(ROOT / "apps" / "api"))
    sys.path.insert(0, str(ROOT / "apps" / "services" / "api"))
    from app.auth import decode_access_token
    from app.config import settings
    from app.services.demo_data import SupabaseDemoRecordStore, install_demo_data

    user = decode_access_token(token)
    configured_root = Path(settings.ARTIFACT_ROOT)
    artifact_root = configured_root if configured_root.is_absolute() else ROOT / configured_root
    store = SupabaseDemoRecordStore(
        base_url=settings.SUPABASE_URL,
        service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )
    result = install_demo_data(user_id=user.id, store=store, artifact_root=artifact_root)
    print(
        "Installed MS-30 demo data: "
        f"2 opportunities, {len(result.presentation_version_ids)} stage decks, "
        f"{sum(result.record_counts.values())} records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
