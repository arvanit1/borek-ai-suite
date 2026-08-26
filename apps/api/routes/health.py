from fastapi import APIRouter

from config import settings
from llm.claude.client import sonnet_model

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "borek-customer-report",
        "model": sonnet_model(),
        "key_configured": "yes" if settings.anthropic_api_key else "no",
    }
