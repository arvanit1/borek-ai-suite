# Team handoff — validation pipeline (AT-7, AT-8, AT-9)

**PR targeting `main`:** see the open pull request from branch `arvanit` (Arvanit Telaku).

## What landed

| Ticket | Summary | Key paths |
|--------|---------|-----------|
| **AT-7** | Generic config-driven SlideSpec constraint validator | `apps/api/services/validation/constraint_validator.py` |
| **AT-8** | Up to 2 AI-shortening passes + revalidate; never silent truncate | `apps/api/services/validation/compression_retry.py` |
| **AT-9** | LibreOffice headless: `.pptx` → `.pdf` + per-slide `.png` | `apps/renderer/validation/libreoffice_pipeline.ts` |

**Gate:** `py -3 scripts/validate_all.py` — **104 tests**, all passing.

## Action for all developers

```bash
git pull origin main          # after PR is merged
git checkout -b your-branch
npm install
py -3 scripts/validate_all.py
```

## Dependencies unlocked for other workstreams

| Owner | Can start (after merge) | Depends on |
|-------|-------------------------|------------|
| **Blenard (BT-*)** | BT-15 constraint configs, BT-16 compression wiring | AT-7, AT-8 |
| **Jaya (JJ-*)** | JJ-10, JJ-14 | AT-7, AT-8 |
| **Mayank (MS-*)** | MS-12, MS-15 | AT-7, AT-8 |
| **Endrit (ES-*)** | ES-31 (uses AT-7 validator) | AT-7 |
| **Arvanit** | AT-10 render checks | AT-9 |

## AT-9 E2E note

Full LibreOffice integration test runs via Docker when LO is not installed locally (`scripts/docker/at9-e2e/Dockerfile`). Production renderer Docker (AT-50) should include **poppler-utils** alongside LibreOffice.

## Do not edit

- `apps/api/services/validation/` — owned by AT-7/8; layout groups register configs only
- `apps/renderer/validation/` — owned by AT-9/10

Questions: Arvanit Telaku.
