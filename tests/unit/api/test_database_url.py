"""Unit tests for Supabase DATABASE_URL resolution."""

from __future__ import annotations

from app.database_url import project_ref_from_supabase_url, resolve_database_url


def test_project_ref_from_supabase_url() -> None:
    assert (
        project_ref_from_supabase_url("https://jygjrztkgyqgkzicmwsh.supabase.co")
        == "jygjrztkgyqgkzicmwsh"
    )


def test_resolve_database_url_builds_from_password() -> None:
    url = resolve_database_url(
        database_url="postgresql://postgres:postgres@localhost:5432/borek",
        supabase_url="https://jygjrztkgyqgkzicmwsh.supabase.co",
        supabase_db_password="p@ss/w+rd",
    )
    assert (
        url
        == "postgresql://postgres:p%40ss%2Fw%2Brd@db.jygjrztkgyqgkzicmwsh.supabase.co:5432/postgres?sslmode=require"
    )


def test_resolve_database_url_builds_pooler_url() -> None:
    url = resolve_database_url(
        database_url="postgresql://postgres:postgres@localhost:5432/borek",
        supabase_url="https://jygjrztkgyqgkzicmwsh.supabase.co",
        supabase_db_password="secret",
        supabase_db_pooler_host="aws-0-eu-central-1.pooler.supabase.com",
    )
    assert (
        url
        == "postgresql://postgres.jygjrztkgyqgkzicmwsh:secret"
        "@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require"
    )


def test_resolve_database_url_keeps_explicit_remote_url() -> None:
    explicit = "postgresql://postgres:secret@db.example.supabase.co:5432/postgres"
    assert (
        resolve_database_url(
            database_url=explicit,
            supabase_url="https://jygjrztkgyqgkzicmwsh.supabase.co",
            supabase_db_password="ignored",
        )
        == explicit
    )
