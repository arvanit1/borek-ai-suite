/** Grid token unit checks executed by pytest via `npm run test:grid --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, normalize, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { BOREK_GRID_TOKENS, BorekGrid, BorekGridTokens, type BorekGridToken } from "./grid.js";
import { BorekSpacing } from "./spacing.js";

/** Derived grid rhythm from §16 spacing (expected values for tests only). */
const EXPECTED_GRID: Record<BorekGridToken, number> = {
  columnGap: BorekSpacing.marginX / 2,
  rowGap: BorekSpacing.marginTop / 2,
};

const INLINE_GRID_PROPERTY_PATTERN = /(?:columnGap|rowGap)\s*:\s*[\d.]+/g;

const RENDERER_ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
const CANONICAL_GRID_FILE = normalize(join(RENDERER_ROOT, "design_system", "tokens", "grid.ts"));

const GUARDED_ROOTS = [
  join(RENDERER_ROOT, "layouts"),
  join(RENDERER_ROOT, "design_system"),
];

function shouldScanFile(filePath: string): boolean {
  const normalized = normalize(filePath);
  if (!normalized.endsWith(".ts") || normalized.endsWith(".test.ts")) {
    return false;
  }
  return normalized !== CANONICAL_GRID_FILE;
}

function listGuardedTypeScriptSources(root: string): string[] {
  if (!existsSync(root)) {
    return [];
  }

  const files: string[] = [];

  function walk(directory: string): void {
    for (const entry of readdirSync(directory)) {
      const path = join(directory, entry);
      if (statSync(path).isDirectory()) {
        walk(path);
        continue;
      }
      if (shouldScanFile(path)) {
        files.push(path);
      }
    }
  }

  walk(root);
  return files;
}

export function findInlineGridPropertyInContent(content: string): string[] {
  return [...content.matchAll(INLINE_GRID_PROPERTY_PATTERN)].map((match) => match[0]);
}

function findGridViolations(roots: string[]): Array<{ file: string; match: string }> {
  const violations: Array<{ file: string; match: string }> = [];
  const seen = new Set<string>();

  for (const root of roots) {
    for (const file of listGuardedTypeScriptSources(root)) {
      if (seen.has(file)) {
        continue;
      }
      seen.add(file);

      const content = readFileSync(file, "utf8");
      for (const match of findInlineGridPropertyInContent(content)) {
        violations.push({ file: relative(RENDERER_ROOT, file), match });
      }
    }
  }

  return violations;
}

assert.equal(BorekGrid.columnGap, BorekSpacing.marginX / 2);
assert.equal(BorekGrid.rowGap, BorekSpacing.marginTop / 2);

for (const token of Object.keys(EXPECTED_GRID) as BorekGridToken[]) {
  assert.equal(BorekGrid[token], EXPECTED_GRID[token], `grid token ${token} must derive from BorekSpacing`);
}

for (const value of Object.values(BorekGrid)) {
  assert.equal(typeof value, "number");
  assert.ok(value > 0, "grid spacing values must be positive inches");
}

assert.deepEqual(BorekGridTokens, { grid: BorekGrid });
assert.deepEqual(BOREK_GRID_TOKENS, BorekGridTokens);

assert.ok(findInlineGridPropertyInContent("columnGap: 0.325").length > 0);
assert.deepEqual(findInlineGridPropertyInContent("import { BorekGrid } from './grid.js'"), []);

const gridViolations = findGridViolations(GUARDED_ROOTS);
assert.equal(
  gridViolations.length,
  0,
  gridViolations.map((v) => `${v.file}: ${v.match}`).join("\n") ||
    "layout and design_system files must not hardcode grid gaps (use BorekGrid tokens)",
);

process.stdout.write("grid token unit checks passed\n");
