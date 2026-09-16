# CI: Borek Brand Guide 2.0 presentation implementation

Implements presentation CI across Gamma, Stage B content generation, deterministic
validation, and the internal renderer. Separate from BT-30 German localization
acceptance (see `docs/tickets/BT30_E2E_GATE_V2.md` for historical BT-30 only).

## Source authority

| Document | Role |
| --- | --- |
| BOREK Brand Guide 2.0 | Normative rules (precedence 1) |
| Borek Master Slides | Visual reference (precedence 2) |
| Borek White Paper Master | Editorial patterns where slide-compatible (precedence 3) |

**Precedence:** Brand Guide explicit rules override Master Slides examples.

## Resolved conflicts (Brand Guide wins)

- Content slides: **no Borek logo**
- Corner radius: **0 px**
- Official Gamma theme: **`y7pjh5eetjgbiym`**

## Machine-readable contract

`packages/contracts/presentation_ci.json`

Encodes colors, typography, geometry, logo policy, voice, and editorial rules.

## Gamma

- `GAMMA_THEME_ID` default: `y7pjh5eetjgbiym` (env override retained)
- Scratch generation no longer sends deck-wide `themeLogo` in `headerFooter`
- Client logo signing/placement unchanged (cover/closing bottom-right when fetchable)
- Footer date/page delegated to approved Gamma theme

## Stage B

- Planner prompt: takeaway-oriented titles, one idea per slide, CI voice bans
- Group A/B/C generation: shared `ci_voice_instruction_block()` in instructions
- Deterministic `presentation_voice` validator on customer-facing SlideSpec prose

## Internal renderer

- Indigo `#0D1240`, Inter, 120px margins, 0px card radius
- Borek logo injected on cover/closing only (`applySlideChrome`)

## Deterministic tests

- `tests/unit/contracts/test_presentation_ci.py`
- `tests/unit/validation/test_presentation_voice.py`
- `tests/unit/gamma/test_ci_theme_and_logo.py`
- `tests/unit/presentation/test_planner_ci_guidance.py`
- Renderer token tests (colors, typography, spacing, borders, content master)

## Live CI smoke

Run manually when `GAMMA_API_KEY` and `GAMMA_EXECUTION_MODE=live` are available.
Do not conflate with BT-30 paid German E2E.

## Remaining manual visual review

- Gamma theme pixel fidelity (splash usage, footer typography) requires human preview
- Provider API cannot deterministically assert per-card logo scope beyond theme trust

## Intentionally not encoded

- Founding year (1781 vs 1790)
- HRB / legal strings marked tbd in source documents
