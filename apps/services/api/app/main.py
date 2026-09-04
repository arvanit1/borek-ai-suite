"""FastAPI application factory (AT-34)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.error_handler import register_error_handlers
from app.routers import (
    frameworks,
    health,
    jobs,
    knowledge,
    opportunities,
    presentations,
    transcripts,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.runtime_profile import log_runtime_profile
    from app.services.stage_b_providers import install_runtime_stage_b_providers

    log_runtime_profile(component="api")
    install_runtime_stage_b_providers()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Borek AI Suite API",
        version="0.1.0",
        lifespan=lifespan,
    )

    register_error_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(opportunities.router, prefix="/opportunities", tags=["opportunities"])
    app.include_router(transcripts.router, prefix="/opportunities", tags=["transcripts"])
    app.include_router(
        frameworks.opportunity_router,
        prefix="/opportunities",
        tags=["frameworks"],
    )
    app.include_router(frameworks.router, prefix="/frameworks", tags=["frameworks"])
    app.include_router(
        presentations.opportunity_router,
        prefix="/opportunities",
        tags=["presentations"],
    )
    app.include_router(
        presentations.plan_router,
        prefix="/presentation-plans",
        tags=["presentations"],
    )
    app.include_router(presentations.router, prefix="/presentations", tags=["presentations"])
    app.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])

    return app


app = create_app()

__all__ = ["app", "create_app", "settings"]
