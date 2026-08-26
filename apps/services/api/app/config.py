"""Application settings — env-only configuration (AT-34)."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.database_url import resolve_database_url


class Settings(BaseSettings):
    """All required backend configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ANTHROPIC_API_KEY: str = Field(..., min_length=1)
    OPENAI_API_KEY: str = Field(..., min_length=1)
    SUPABASE_URL: str = Field(..., min_length=1)
    SUPABASE_ANON_KEY: str = Field(..., min_length=1)
    SUPABASE_SERVICE_ROLE_KEY: str = Field(..., min_length=1)
    SUPABASE_JWT_SECRET: str = Field(
        default="",
        description="Optional legacy HS256 secret; real tokens verify via SUPABASE_URL JWKS",
    )
    SUPABASE_DB_PASSWORD: str = Field(
        default="",
        description="Supabase Postgres password; builds DATABASE_URL when set",
    )
    SUPABASE_DB_POOLER_HOST: str = Field(
        default="",
        description="Optional pooler host (IPv4) from Dashboard > Database > Connection pooling",
    )
    REDIS_URL: str = Field(..., min_length=1)
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/borek",
        min_length=1,
    )
    RENDERER_URL: str = Field(..., min_length=1)
    API_DATA_BACKEND: str = Field(
        default="supabase",
        description="memory for unit tests; supabase for PostgREST with caller JWT",
    )

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    @model_validator(mode="after")
    def apply_resolved_database_url(self) -> Self:
        self.DATABASE_URL = resolve_database_url(
            database_url=self.DATABASE_URL,
            supabase_url=self.SUPABASE_URL,
            supabase_db_password=self.SUPABASE_DB_PASSWORD,
            supabase_db_pooler_host=self.SUPABASE_DB_POOLER_HOST,
        )
        return self


def load_settings() -> Settings:
    """Load settings and fail fast when required env vars are missing."""
    return Settings()


settings = load_settings()
