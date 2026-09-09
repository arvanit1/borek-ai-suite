"""JJ-29: Gamma fetches a quality-gated client logo from an owned HTTPS URL."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.config import settings
from app.services.api_errors import not_found
from services.gamma.signed_logo import verify_signed_client_logo_request

router = APIRouter(tags=["public"])

_UNAVAILABLE = "Client logo is not available"


@router.get("/public/client-logos/{opportunity_id}")
def get_signed_client_logo(
    opportunity_id: UUID,
    exp: str = Query(default=""),
    sig: str = Query(default=""),
) -> Response:
    secret = settings.CLIENT_LOGO_SIGNING_SECRET or settings.SUPABASE_JWT_SECRET
    if not verify_signed_client_logo_request(
        opportunity_id,
        exp=exp,
        signature=sig,
        secret=secret,
    ):
        raise not_found("CLIENT_LOGO_NOT_FOUND", _UNAVAILABLE)

    from app.services.data import build_worker_data_store

    store = build_worker_data_store()
    try:
        row, content = store.get_client_logo_for_signed_fetch(opportunity_id=opportunity_id)
    except Exception:
        raise not_found("CLIENT_LOGO_NOT_FOUND", _UNAVAILABLE) from None
    safe_name = str(row.get("file_name") or "client-logo").replace('"', "")
    return Response(
        content=content,
        media_type=str(row.get("mime_type") or "application/octet-stream"),
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "Cache-Control": "private, max-age=60",
        },
    )
