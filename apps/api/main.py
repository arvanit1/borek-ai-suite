from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
API_ROOT = Path(__file__).resolve().parent
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from errors import register_error_handlers
from routes.customer_report import router as customer_router
from routes.health import router as health_router
from services.framework.store import load_store_from_disk

app = FastAPI(
    title="Borek AI Suite — Customer Framework Report",
    description="Customer report only (14 chapters, DE/EN PDF). Technical framework is out of scope.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\]|192\.168\.\d+\.\d+|172\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)
app.include_router(health_router)
app.include_router(customer_router)


@app.on_event("startup")
def _load_persisted_store() -> None:
    load_store_from_disk()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "customer-framework-report",
        "docs": "/docs",
        "health": "/health",
    }
