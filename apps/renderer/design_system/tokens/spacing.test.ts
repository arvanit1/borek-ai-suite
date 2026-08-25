/** AT-13 unit checks executed by pytest via `npm run test:at13 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, normalize, relative } from "node:path";
import { fileURLToPath } from "node:url";

import {
  BOREK_SPACING_TOKENS,
  BorekSpacing,
  BorekSpacingTokens,
  type BorekSpacingToken,
} from "./spacing.js";

/** Technical plan v2 §16 — BorekTheme.spacing seed values (expected values for tests only). */
const TECHNICAL_PLAN_V2_SPACING: Record<BorekSpacingToken, number> = {
  marginX: 0.65,
  marginTop: 0.5,
  footerHeight: 0.35,
};

const INLINE_SPACING_PROPERTY_PATTERN =
  /(?:marginX|marginTop|footerHeight)\s*:\s*[\d.]+/g;

const RENDERER_ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
const CANONICAL_SPACING_FILE = normalize(join(RENDERER_ROOT, "design_system", "tokens", "spacing.ts"));

const GUARDED_ROOTS = [
  join(RENDERER_ROOT, "layouts"),
  join(RENDERER_ROOT, "design_system"),
];

function shouldScanFile(filePath: string): boolean {
  const normalized = normalize(filePath);
  if (!normalized.endsWith(".ts") || normalized.endsWith(".test.ts")) {
    return false;
  }
  return normalized !== CANONICAL_SPACING_FILE;
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

export function findInlineSpacingPropertyInContent(content: string): string[] {
  return [...content.matchAll(INLINE_SPACING_PROPERTY_PATTERN)].map((match) => match[0]);
}

function findSpacingViolations(roots: string[]): Array<{ file: string; match: string }> {
  const violations: Array<{ file: string; match: string }> = [];
  const seen = new Set<string>();

  for (const root of roots) {
    for (const file of listGuardedTypeScriptSources(root)) {
      if (seen.has(file)) {
        continue;
      }
      seen.add(file);

      const content = readFileSync(file, "utf8");
      for (const match of findInlineSpacingPropertyInContent(content)) {
        violations.push({ file: relative(RENDERER_ROOT, file), match });
      }
    }
  }

  return violations;
}

for (const token of Object.keys(TECHNICAL_PLAN_V2_SPACING) as BorekSpacingToken[]) {
  assert.equal(
    BorekSpacing[token],
    TECHNICAL_PLAN_V2_SPACING[token],
    `spacing token ${token} must match technical plan v2 §16`,
  );
}

for (const value of Object.values(BorekSpacing)) {
  assert.equal(typeof value, "number");
  assert.ok(value > 0, "spacing values must be positive inches");
}

assert.deepEqual(BorekSpacingTokens, { spacing: BorekSpacing });
assert.deepEqual(BOREK_SPACING_TOKENS, BorekSpacingTokens);

assert.ok(findInlineSpacingPropertyInContent("marginX: 0.65").length > 0);
assert.deepEqual(findInlineSpacingPropertyInContent("import { BorekSpacing } from './spacing.js'"), []);

const spacingViolations = findSpacingViolations(GUARDED_ROOTS);
assert.equal(
  spacingViolations.length,
  0,
  spacingViolations.map((v) => `${v.file}: ${v.match}`).join("\n") ||
    "layout and design_system files must not hardcode spacing (use BorekSpacing tokens)",
);

process.stdout.write("AT-13 renderer unit checks passed\n");
