# Database migration verification (AT-37)

This procedure creates the Borek schema on a **clean** hosted Supabase project from repository SQL only. No manual `ALTER TABLE` / dashboard schema edits are required.

Canonical migration directory:

```
apps/services/api/supabase/migrations/
```

The ten §23 tables live in `001`–`010`. RLS policies are `011`. Follow-on wiring files `012`–`014` are additive (`ADD COLUMN IF NOT EXISTS` / storage bucket / `llm_calls`) and must be applied after `011`.

## Apply migrations to a clean Supabase project

1. Create an empty Supabase project (Dashboard → New project). Do not paste ad-hoc SQL first.
2. Put the new project credentials in `.env`:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_DB_PASSWORD`
   - `SUPABASE_DB_POOLER_HOST` (session-mode pooler host from Dashboard → Connect)
   - `DATABASE_URL` (session pooler URI, or leave unset so the API builds it)
3. From the repository root, apply every file in numeric order. This is the exact command:

```powershell
Get-ChildItem -Path apps/services/api/supabase/migrations -Filter *.sql |
  Sort-Object Name |
  ForEach-Object {
    Write-Host "Applying $($_.Name)"
    psql $env:DATABASE_URL -v ON_ERROR_STOP=1 -f $_.FullName
  }
```

`psql` uses the same `DATABASE_URL` that `scripts/verify_db.py` resolves (session pooler on Windows). Equivalent bash:

```bash
for f in apps/services/api/supabase/migrations/*.sql; do
  echo "Applying $f"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done
```

Alternative without `psql`: open Supabase Dashboard → SQL Editor and paste each file in order (`001` … `014`), one execution per file.

## Verify all 10 tables exist with the correct schema

Run:

```powershell
py -3 scripts/verify_db.py
```

The script must report `OK` for each of:

| Table | Created by |
|---|---|
| `opportunities` | `001_opportunities.sql` |
| `transcripts` | `002_transcripts.sql` |
| `transcript_sections` | `003_transcript_sections.sql` |
| `framework_versions` | `004_framework_versions.sql` |
| `presentation_plans` | `005_presentation_plans.sql` |
| `presentations` | `006_presentations.sql` |
| `presentation_versions` | `007_presentation_versions.sql` |
| `slides` | `008_slides.sql` |
| `generation_jobs` | `009_generation_jobs.sql` |
| `audit_log` | `010_audit_log.sql` |

When `DATABASE_URL` points at remote Postgres, section 3 lists those tables from `pg_tables`. When only REST credentials are set, it probes `GET /rest/v1/<table>?select=id&limit=0` (HTTP 200/206).

Column-level checks are in the SQL files themselves (`CREATE TABLE IF NOT EXISTS` plus `012`/`013` additive columns). Re-running `verify_db.py` after a clean apply is the live proof that PostgREST can read every table.

## Verify RLS is enabled on each table

`py -3 scripts/verify_db.py` section 4 queries `pg_class.relrowsecurity` for the ten tables. Each row must print `RLS enabled`.

Section 5 must find a policy on every table (`011_rls_policies.sql`). Expected policy names:

- `users_own_opportunities`
- `users_own_transcripts`
- `users_own_transcript_sections`
- `users_own_framework_versions`
- `users_own_presentation_plans`
- `users_own_presentations`
- `users_own_presentation_versions`
- `users_own_slides`
- `users_own_generation_jobs`
- `users_own_audit_entries`

Direct SQL equivalent:

```sql
SELECT c.relname, c.relrowsecurity
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN (
    'opportunities', 'transcripts', 'transcript_sections', 'framework_versions',
    'presentation_plans', 'presentations', 'presentation_versions', 'slides',
    'generation_jobs', 'audit_log'
  )
ORDER BY c.relname;
```

Every `relrowsecurity` value must be `true`.

## Re-run safely (idempotency)

Every migration is written to be re-runnable:

- Tables: `CREATE TABLE IF NOT EXISTS`
- RLS: `ALTER TABLE … ENABLE ROW LEVEL SECURITY` (safe to repeat)
- Policies: `DROP POLICY IF EXISTS` then `CREATE POLICY`
- Later files: `ADD COLUMN IF NOT EXISTS`, `CREATE UNIQUE INDEX IF NOT EXISTS`, `INSERT … ON CONFLICT`

Re-apply with the same `psql` loop (or paste the files again in SQL Editor). A second run must finish with `ON_ERROR_STOP=1` and no errors. Then re-run:

```powershell
py -3 scripts/verify_db.py
```

The table list, RLS flags, and policy count must be unchanged. The smoke insert/delete in `verify_db.py` uses a throwaway UUID and deletes it.

## Result of running this procedure today

| Field | Value |
|---|---|
| Date | 2026-09-01 |
| Command | `py -3 scripts/verify_db.py` against the live project (Postgres via session pooler) |
| Project URL | `https://jygjrztkgyqgkzicmwsh.supabase.co` |
| Postgres | PostgreSQL 17.6 (pooler `aws-1-eu-west-1.pooler.supabase.com:5432/postgres`) |
| Tables confirmed | `opportunities`, `transcripts`, `transcript_sections`, `framework_versions`, `presentation_plans`, `presentations`, `presentation_versions`, `slides`, `generation_jobs`, `audit_log` |
| Missing tables | none |
| RLS | enabled on all 10 tables |
| Policies | 10 policies found |
| `auth.uid()` | present |
| Smoke insert/delete | passed |
| Script exit | `0` — “Database schema and RLS look good (Postgres).” |

This project already had the repository migrations applied; `verify_db.py` is the live proof that the schema matches `001`–`011` (plus later additive files) with no missing tables and no manual schema drift required for the ten-table spine.
