/** Border token unit checks executed by pytest via `npm run test:borders --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, normalize, relative } from "node:path";
import { fileURLToPath } from "node:url";

import {
  BOREK_BORDER_TOKENS,
  BorekBorderLineWidths,
  BorekBorders,
  BorekBorderTokens,
} from "./borders.js";
import { BorekColors } from "./colors.js";
import { BorekGrid } from "./grid.js";

const INLINE_BORDER_PROPERTY_PATTERN =
  /(?:borderRadiusInches|lineWidthPt)\s*:\s*[\d.]+/g;

const RENDERER_ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
const CANONICAL_BORDERS_FILE = normalize(join(RENDERER_ROOT, "design_system", "tokens", "borders.ts"));

const GUARDED_ROOTS = [
  join(RENDERER_ROOT, "layouts"),
  join(RENDERER_ROOT, "design_system"),
];

function shouldScanFile(filePath: string): boolean {
  const normalized = normalize(filePath);
  if (!normalized.endsWith(".ts") || normalized.endsWith(".test.ts")) {
    return false;
  }
  return normalized !== CANONICAL_BORDERS_FILE;
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

export function findInlineBorderPropertyInContent(content: string): string[] {
  return [...content.matchAll(INLINE_BORDER_PROPERTY_PATTERN)].map((match) => match[0]);
}

function findBorderViolations(roots: string[]): Array<{ file: string; match: string }> {
  const violations: Array<{ file: string; match: string }> = [];
  const seen = new Set<string>();

  for (const root of roots) {
    for (const file of listGuardedTypeScriptSources(root)) {
      if (seen.has(file)) {
        continue;
      }
      seen.add(file);

      const content = readFileSync(file, "utf8");
      for (const match of findInlineBorderPropertyInContent(content)) {
        violations.push({ file: relative(RENDERER_ROOT, file), match });
      }
    }
  }

  return violations;
}

assert.equal(BorekBorders.card.borderColor, BorekColors.border);
assert.equal(BorekBorders.divider.color, BorekColors.border);
assert.equal(BorekBorders.card.borderRadiusInches, BorekGrid.rowGap / 2);
assert.equal(BorekBorderLineWidths.card, 1);
assert.equal(BorekBorderLineWidths.divider, 1);
assert.equal(BorekBorders.card.lineWidthPt, BorekBorderLineWidths.card);
assert.equal(BorekBorders.divider.lineWidthPt, BorekBorderLineWidths.divider);

for (const value of [BorekBorders.card.borderRadiusInches, BorekBorders.card.lineWidthPt, BorekBorders.divider.lineWidthPt]) {
  assert.equal(typeof value, "number");
  assert.ok(value > 0, "border measurements must be positive");
}

assert.deepEqual(BorekBorderTokens, { borders: BorekBorders, lineWidths: BorekBorderLineWidths });
assert.deepEqual(BOREK_BORDER_TOKENS, BorekBorderTokens);

assert.ok(findInlineBorderPropertyInContent("borderRadiusInches: 0.125").length > 0);
assert.deepEqual(findInlineBorderPropertyInContent("import { BorekBorders } from './borders.js'"), []);

const borderViolations = findBorderViolations(GUARDED_ROOTS);
assert.equal(
  borderViolations.length,
  0,
  borderViolations.map((v) => `${v.file}: ${v.match}`).join("\n") ||
    "layout and design_system files must not hardcode border radius/width (use BorekBorders tokens)",
);

process.stdout.write("border token unit checks passed\n");
