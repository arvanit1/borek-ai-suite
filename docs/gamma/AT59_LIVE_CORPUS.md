# AT-59 — Live corpus and rate cards

Phase 3. Owner: Jaya Joshi. Priority: P0. Carried over from the AT range.

The retrieval corpus is the live Borek facts store, not the Phase 2 dummy.
Rate-card **content** updates sit with Fiona / Commercial; this ticket is the
pipeline: ingest, version, retrieve, cite.

Machine-readable identity:
[`packages/contracts/knowledge_corpus.json`](../../packages/contracts/knowledge_corpus.json).

| Frozen field | Value | Consumer |
| --- | --- | --- |
| Live corpus id | `borek-internal` | ES-39, ES-40 |
| Demo corpus id | `borek-demo` | MS-30 |
| Live provenance marker | `es39` | ES-39, MS-30 |
| Demo provenance marker | `demo` | MS-30 |
| Retrieval stage name | `BOREK_RETRIEVAL` | BT-29 |
| Customer-facing name | Retrieving Borek information | BT-29, shown when reported |

## Done when

ES-39 and ES-40 read `borek-internal` (store if ingested, otherwise the bundled
seed) rather than a fixture corpus. Demo facts on `borek-demo` never answer a
live retrieve. Blenard needs only the stage name, so BT-29 is not blocked.

O2 (SharePoint) remains the future file store. O3 ownership stays Commercial;
Fiona updates the structured rate card and this pipeline versions it.
