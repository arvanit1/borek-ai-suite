# Ownership & scope

This repo is built ticket-by-ticket. **Do not implement code outside your assigned tickets.**

| Area | Owner | Tickets |
|------|-------|---------|
| `packages/contracts/` (core schemas) | Arvanit Telaku | AT-1..AT-6 |
| `apps/api/services/validation/`, `apps/renderer/design_system/`, `dispatcher` | Arvanit | AT-7..AT-33 |
| `apps/api/` platform, `apps/worker/`, `apps/web/`, `supabase/` | Arvanit | AT-34..AT-55 |
| `apps/api/services/transcript/`, `knowledge_model/`, `framework/` | Endrit Shemsedini | ES-* |
| `slide_spec/group_a/`, content + render group A | Blenard Tahiraj | BT-* |
| `slide_spec/group_b/`, content + render group B | Jaya Joshi | JJ-* |
| `slide_spec/group_c/`, content + render group C | Mayank Somwani | MS-* |
| Content grounding and deck fidelity: corpus, grounded facts, payload, slots, logo, previews | Jaya Joshi | AT-59, ES-39, ES-40, JJ-29..JJ-31 (JJ-26..JJ-28 closed) |
| User surface and filed history: intake, recovery, archive, demo data, stage selector | Mayank Somwani | AT-61, MS-27..MS-31 |
| Pipeline stages and release: provider contract, orchestration, labels, prerequisites, egress, E2E | Blenard Tahiraj | AT-60, BT-28..BT-32 |

Six live tickets each. Each owner holds the one earlier-range leftover whose only
consumers are their own tickets, so nobody waits on another owner for their own
inputs. Remaining cross-owner handoffs are contract-first: freeze the shape,
then both sides build against a fixture. See
[`docs/tickets/README.md`](tickets/README.md).

Empty directories are intentional placeholders until the owning developer's ticket is active.
