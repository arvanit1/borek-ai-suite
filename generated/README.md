# generated/ ù Codegen output (do not hand-edit)

Populated by:

- `scripts/generate_pydantic.py` ? `python/contracts/` (**AT-4**)
- `scripts/generate_typescript.js` ? `typescript/contracts/` (**AT-5**)

These directories are gitignored. After any change in `packages/contracts/`:

```bash
py -3 scripts/generate_pydantic.py
node scripts/generate_typescript.js   # or: npm run generate:typescript
npm install                            # once, for renderer typecheck (AT-5)
py -3 scripts/validate_all.py
```
