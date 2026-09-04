#!/usr/bin/env python3
"""Verify Supabase schema after manual migrations.

Uses direct Postgres when DATABASE_URL points at Supabase, otherwise falls back
to the Supabase REST API (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY).
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "services" / "api"))

from app.database_url import resolve_database_url  # noqa: E402

EXPECTED_TABLES = [
    "opportunities",
    "transcripts",
    "transcript_sections",
    "framework_versions",
    "presentation_plans",
    "presentations",
    "presentation_versions",
    "slides",
    "generation_jobs",
    "audit_log",
    "llm_calls",
    "opportunity_client_logos",
    "filed_artifacts",
    "knowledge_corpus_versions",
    "knowledge_documents",
    "knowledge_facts",
]

EXPECTED_COLUMNS = {
    "opportunities": ("pii_redaction_enabled", "additional_client_information"),
    "generation_jobs": (
        "llm_cost_eur",
        "error_retryable",
        "result_json",
        "number_of_ai_calls",
        "ai_input_tokens",
        "ai_output_tokens",
    ),
    "llm_calls": (
        "request_id",
        "job_id",
        "opportunity_id",
        "prompt_version",
        "retry_count",
        "estimated_cost_eur",
    ),
    "filed_artifacts": (
        "idempotency_key",
        "repository_ref",
        "status",
        "approved_by",
        "approved_at",
        "corpus_versions",
        "error_retryable",
    ),
    "opportunity_client_logos": ("width_px", "height_px"),
}

EXPECTED_FOREIGN_KEYS = {
    "transcripts": "opportunities",
    "framework_versions": "opportunities",
    "presentation_plans": "framework_versions",
    "presentations": "presentation_plans",
    "generation_jobs": "opportunities",
    "llm_calls": "generation_jobs",
    "opportunity_client_logos": "opportunities",
    "filed_artifacts": "presentation_versions",
    "knowledge_documents": "knowledge_corpus_versions",
    "knowledge_facts": "knowledge_documents",
}

EXPECTED_INDEXES = (
    "transcripts_opportunity_conversation_id_key",
    "filed_artifacts_opportunity_idx",
    "filed_artifacts_presentation_version_idx",
    "knowledge_corpus_status_idx",
    "knowledge_documents_corpus_idx",
    "knowledge_facts_query_idx",
    "knowledge_facts_service_kind_idx",
)

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def warn(msg: str) -> None:
    print(f"  WARN {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL {msg}")


def check_env() -> tuple[str, str, str, str, int]:
    """Return (db_url, supabase_url, service_role_key, jwt, error_count)."""
    errors = 0
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    db_url = resolve_database_url(
        database_url=os.getenv("DATABASE_URL", "").strip(),
        supabase_url=supabase_url,
        supabase_db_password=os.getenv("SUPABASE_DB_PASSWORD", "").strip(),
        supabase_db_pooler_host=os.getenv("SUPABASE_DB_POOLER_HOST", "").strip(),
    )

    print("1) Environment variables")
    if db_url:
        parsed = urlparse(db_url)
        ok(
            f"DATABASE_URL -> {parsed.hostname}:{parsed.port or 5432}"
            f"/{parsed.path.lstrip('/') or 'postgres'}"
        )
        if parsed.hostname in LOCAL_DB_HOSTS:
            warn(
                "DATABASE_URL points to localhost — set SUPABASE_DB_PASSWORD "
                "or paste the full Supabase URI"
            )
    else:
        warn("DATABASE_URL missing (will try REST fallback if Supabase keys are set)")

    for key in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        if os.getenv(key, "").strip():
            ok(f"{key} is set")
        else:
            warn(f"{key} missing")
            errors += 1

    jwt = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    if jwt and jwt != "your-jwt-secret-from-supabase-dashboard":
        ok("SUPABASE_JWT_SECRET is set (optional; tests/legacy HS256)")
    elif supabase_url:
        ok("Auth will verify real tokens via JWKS from SUPABASE_URL")
    else:
        warn("Set SUPABASE_URL for JWT verification")
        errors += 1

    return db_url, supabase_url, service_role_key, jwt, errors


def verify_via_postgres(db_url: str) -> tuple[int, bool]:
    """Full schema + RLS check. Returns (error_count, connected)."""
    errors = 0
    print("\n2) Postgres connection (DATABASE_URL)")
    try:
        import psycopg
    except ImportError:
        fail("psycopg not installed - run: py -3 -m pip install psycopg[binary]")
        return 1, False

    try:
        with psycopg.connect(db_url, connect_timeout=15, autocommit=True) as conn:
            ok("Connected")
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                ok("Server: " + cur.fetchone()[0].split(",")[0][:80])

            print("\n3) Expected tables")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = %s AND tablename = ANY(%s)
                    ORDER BY tablename
                    """,
                    ("public", EXPECTED_TABLES),
                )
                found = {row[0] for row in cur.fetchall()}
            for table in EXPECTED_TABLES:
                if table in found:
                    ok(table)
                else:
                    fail(f"{table} missing")
                    errors += 1

            print("\n4) Row Level Security")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.relname, c.relrowsecurity
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = %s AND c.relname = ANY(%s)
                    ORDER BY c.relname
                    """,
                    ("public", EXPECTED_TABLES),
                )
                rows = cur.fetchall()
            for name, rls_enabled in rows:
                if rls_enabled:
                    ok(f"{name}: RLS enabled")
                else:
                    fail(f"{name}: RLS disabled")
                    errors += 1

            print("\n5) RLS policies")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tablename, policyname FROM pg_policies
                    WHERE schemaname = %s ORDER BY tablename, policyname
                    """,
                    ("public",),
                )
                policies = cur.fetchall()
            ok(f"{len(policies)} policies found")
            policy_tables = {row[0] for row in policies}
            for table in EXPECTED_TABLES:
                if table not in policy_tables:
                    fail(f"{table}: no policy")
                    errors += 1

            print("\n6) Supabase auth helper")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = %s AND p.proname = %s
                    """,
                    ("auth", "uid"),
                )
                if cur.fetchone():
                    ok("auth.uid() exists")
                else:
                    warn("auth.uid() not found")

            print("\n7) Required columns, foreign keys, and indexes")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = ANY(%s)
                    """,
                    (list(EXPECTED_COLUMNS),),
                )
                present_columns = {(row[0], row[1]) for row in cur.fetchall()}
            for table, columns in EXPECTED_COLUMNS.items():
                for column in columns:
                    if (table, column) in present_columns:
                        ok(f"{table}.{column}")
                    else:
                        fail(f"{table}.{column} missing")
                        errors += 1

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      conrelid::regclass::text,
                      confrelid::regclass::text
                    FROM pg_constraint
                    WHERE contype = 'f'
                      AND connamespace = 'public'::regnamespace
                    """
                )
                fk_pairs = {(row[0], row[1]) for row in cur.fetchall()}
            for child, parent in EXPECTED_FOREIGN_KEYS.items():
                if (child, parent) in fk_pairs:
                    ok(f"{child} -> {parent}")
                else:
                    fail(f"{child} missing FK to {parent}")
                    errors += 1

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = 'public' AND indexname = ANY(%s)
                    """,
                    (list(EXPECTED_INDEXES),),
                )
                found_indexes = {row[0] for row in cur.fetchall()}
            for index_name in EXPECTED_INDEXES:
                if index_name in found_indexes:
                    ok(index_name)
                else:
                    fail(f"{index_name} missing")
                    errors += 1

            print("\n8) Smoke insert/delete")
            test_id = uuid.uuid4()
            user_id = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO opportunities (
                      id, client_name, opportunity_name, department, created_by
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (test_id, "Verify Client", "Verify Opp", "IT", user_id),
                )
                cur.execute("SELECT count(*) FROM opportunities WHERE id = %s", (test_id,))
                if cur.fetchone()[0] == 1:
                    ok("Insert/select as connection role")
                else:
                    fail("Insert/select failed")
                    errors += 1
                cur.execute("DELETE FROM opportunities WHERE id = %s", (test_id,))
                ok("Cleanup delete")

    except Exception as exc:
        fail(f"{type(exc).__name__}: {exc}")
        return errors + 1, False

    return errors, True


def verify_via_rest(supabase_url: str, service_role_key: str) -> int:
    """Table + write checks via Supabase REST API. Returns error_count."""
    errors = 0
    print("\n2) Supabase REST API (SUPABASE_URL + SERVICE_ROLE_KEY)")
    ok(f"Endpoint: {supabase_url}/rest/v1")

    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    print("\n3) Expected tables (REST read probe)")
    with httpx.Client(timeout=20.0) as client:
        for table in EXPECTED_TABLES:
            response = client.get(
                f"{supabase_url}/rest/v1/{table}",
                headers=headers,
                params={"select": "id", "limit": "0"},
            )
            if response.status_code in (200, 206):
                ok(table)
            else:
                fail(f"{table}: HTTP {response.status_code}")
                errors += 1

        print("\n4) Smoke insert/delete (service role bypasses RLS)")
        test_id = str(uuid.uuid4())
        user_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        insert = client.post(
            f"{supabase_url}/rest/v1/opportunities",
            headers=headers,
            json={
                "id": test_id,
                "client_name": "Verify Client",
                "opportunity_name": "Verify Opp",
                "department": "IT",
                "created_by": user_id,
            },
        )
        if insert.status_code not in (200, 201, 204):
            fail(f"Insert failed: HTTP {insert.status_code}")
            errors += 1
        else:
            ok("Insert via REST")

            read = client.get(
                f"{supabase_url}/rest/v1/opportunities",
                headers=headers,
                params={"select": "id", "id": f"eq.{test_id}"},
            )
            if read.status_code == 200 and read.json():
                ok("Read back inserted row")
            else:
                fail("Read back failed")
                errors += 1

            delete = client.delete(
                f"{supabase_url}/rest/v1/opportunities",
                headers=headers,
                params={"id": f"eq.{test_id}"},
            )
            if delete.status_code in (200, 204):
                ok("Cleanup delete")
            else:
                fail(f"Delete failed: HTTP {delete.status_code}")
                errors += 1

    warn("RLS not verified in REST mode (service role bypasses policies)")
    warn("Set DATABASE_URL to Supabase Postgres URI to run full RLS checks")
    return errors


def main() -> int:
    load_dotenv(ROOT / ".env")

    print("=== Borek DB verification ===\n")
    db_url, supabase_url, service_role_key, _jwt, errors = check_env()

    postgres_host = urlparse(db_url).hostname if db_url else None
    use_postgres = bool(db_url) and postgres_host not in LOCAL_DB_HOSTS

    postgres_errors = 0
    postgres_ok = False
    if use_postgres:
        postgres_errors, postgres_ok = verify_via_postgres(db_url)
        errors += postgres_errors

    if not postgres_ok:
        if supabase_url and service_role_key:
            errors += verify_via_rest(supabase_url, service_role_key)
        elif not use_postgres:
            fail("No usable connection: fix DATABASE_URL or set Supabase URL + service role key")
            errors += 1
        else:
            print(
                "\nTip: Postgres failed and REST fallback unavailable. "
                "Ensure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set."
            )
            return 1

    print("\n=== Summary ===")
    if errors:
        print(f"{errors} issue(s) found.")
        return 1

    if postgres_ok:
        print("Database schema and RLS look good (Postgres).")
        print("\nNext: run RLS integration test:")
        print('  $env:RUN_SUPABASE_INTEGRATION = "1"')
        print("  py -3 -m pytest tests/integration/api/test_rls_negative.py -m integration -v")
    else:
        print("Migrations look good via Supabase REST API.")
        print("For AT-40 SQLAlchemy + RLS integration tests, add DATABASE_URL later.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
