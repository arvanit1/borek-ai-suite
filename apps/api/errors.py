from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from services.framework.cross_chapter_rules import MultiProcessError
from services.framework.eligibility import EligibilityError, RenderBlocked
from services.framework.chapter_validators.base import ChapterValidationError
from services.framework.guardrails import GuardrailError
from services.framework.pre_confirm_check import PreConfirmError
from services.framework.regenerate_chapter import ChapterRegenError
from services.framework.synthesis import FrameworkSynthesisError
from services.knowledge_model.extraction import KnowledgeExtractionError
from services.transcript.ingestion import TranscriptIngestionError
from llm.claude.client import ClaudeClientError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(EligibilityError)
    async def eligibility(_: Request, exc: EligibilityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": "eligibility_failed", "message": exc.user_message, "gaps": exc.gaps},
        )

    @app.exception_handler(RenderBlocked)
    async def blocked(_: Request, exc: RenderBlocked) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": "render_blocked", "message": exc.user_message, "readiness": exc.readiness, "gaps": exc.gaps},
        )

    @app.exception_handler(MultiProcessError)
    async def multi_process(_: Request, exc: MultiProcessError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": "multi_process", "message": exc.user_message})

    @app.exception_handler(ChapterValidationError)
    async def chapter(_: Request, exc: ChapterValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": "chapter_validation", "message": exc.user_message})

    @app.exception_handler(GuardrailError)
    async def guardrail(_: Request, exc: GuardrailError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": "guardrail", "message": exc.user_message})

    @app.exception_handler(PreConfirmError)
    async def preconfirm(_: Request, exc: PreConfirmError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": "pre_confirm", "message": exc.user_message})

    @app.exception_handler(ChapterRegenError)
    async def regen(_: Request, exc: ChapterRegenError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": "chapter_regen", "message": exc.user_message})

    @app.exception_handler(FrameworkSynthesisError)
    async def synth(_: Request, exc: FrameworkSynthesisError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": "synthesis", "message": exc.user_message})

    @app.exception_handler(KnowledgeExtractionError)
    async def extract(_: Request, exc: KnowledgeExtractionError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": "extraction", "message": exc.user_message})

    @app.exception_handler(TranscriptIngestionError)
    async def ingest(_: Request, exc: TranscriptIngestionError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": "transcript", "message": str(exc)})

    @app.exception_handler(ClaudeClientError)
    async def claude(_: Request, exc: ClaudeClientError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": "claude", "message": exc.user_message})

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": "server", "message": str(exc)})
