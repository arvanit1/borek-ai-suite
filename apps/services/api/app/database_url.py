"""Resolve Supabase Postgres DATABASE_URL from env vars."""

from __future__ import annotations

from urllib.parse import quote_plus, urlparse

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}


def project_ref_from_supabase_url(supabase_url: str) -> str | None:
    host = urlparse(supabase_url).hostname or ""
    if host.endswith(".supabase.co"):
        return host.removesuffix(".supabase.co")
    return None


def resolve_database_url(
    *,
    database_url: str,
    supabase_url: str,
    supabase_db_password: str = "",
    supabase_db_pooler_host: str = "",
) -> str:
    """Use DATABASE_URL when remote; otherwise build from Supabase project + password."""
    parsed = urlparse(database_url)
    if parsed.hostname not in LOCAL_DB_HOSTS:
        return database_url

    password = supabase_db_password.strip()
    if not password:
        return database_url

    project_ref = project_ref_from_supabase_url(supabase_url)
    if project_ref is None:
        return database_url

    encoded_password = quote_plus(password)
    pooler_host = supabase_db_pooler_host.strip()
    if pooler_host:
        return (
            f"postgresql://postgres.{project_ref}:{encoded_password}"
            f"@{pooler_host}:5432/postgres?sslmode=require"
        )

    return (
        f"postgresql://postgres:{encoded_password}"
        f"@db.{project_ref}.supabase.co:5432/postgres?sslmode=require"
    )
