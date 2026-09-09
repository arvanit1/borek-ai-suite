# ES-39 — Grounded prices and staffing

Phase 3. Owner: Jaya Joshi. Priority: P0. Carried over from the ES range.

Prices and staffing come from AT-59 retrieve or they do not appear. The system
may explain an approved rate-card figure; it may never originate one.

Frozen for MS-30, in
[`packages/contracts/knowledge_corpus.json`](../../packages/contracts/knowledge_corpus.json):

- Demo corpus id: `borek-demo`
- Provenance marker: `es39` (live) / `demo` (seed)

A demo rate card must be impossible to mistake for a grounded commercial fact.
`has_live_provenance` rejects the demo marker and the demo corpus id.

## Done when

Every figure that reaches Concretisation (JJ-31 / ES-40) carries corpus version,
document id, fact id, and the `es39` marker. An ungrounded price raises
`UngroundedPriceError` / `GAMMA_PAYLOAD_INVALID`. It is not labelled indicative
as a workaround.
