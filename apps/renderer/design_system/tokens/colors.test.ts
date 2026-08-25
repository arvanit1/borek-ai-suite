/** AT-11 unit checks executed by pytest via `npm run test:at11 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, normalize, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { BOREK_COLOR_TOKENS, BorekColors, type BorekColorToken } from "./colors.js";

/** Technical plan v2 §16 — BorekTheme.colors seed palette (expected values for tests only). */
const TECHNICAL_PLAN_V2_COLORS: Record<BorekColorToken, string> = {
  background: "FFFFFF",
  text: "182230",
  mutedText: "667085",
  border: "E4E7EC",
  primary: "0057B8",
};

const HEX_WITHOUT_HASH = /^[0-9A-Fa-f]{6}$/;

export const HARDCODED_HEX_PATTERN = /#?[0-9A-Fa-f]{6}\b/g;

const RENDERER_ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
const CANONICAL_COLORS_FILE = normalize(join(RENDERER_ROOT, "design_system", "tokens", "colors.ts"));

/** Layouts plus design-system components/masters — everywhere styling code will live. */
const GUARDED_ROOTS = [
  join(RENDERER_ROOT, "layouts"),
  join(RENDERER_ROOT, "design_system"),
];

export function findHardcodedHexInContent(content: string): string[] {
  return [...content.matchAll(HARDCODED_HEX_PATTERN)].map((match) => match[0]);
}

function shouldScanFile(filePath: string): boolean {
  const normalized = normalize(filePath);
  if (!normalized.endsWith(".ts") || normalized.endsWith(".test.ts")) {
    return false;
  }
  return normalized !== CANONICAL_COLORS_FILE;
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

export function findHardcodedHexViolations(roots: string[]): Array<{ file: string; match: string }> {
  const violations: Array<{ file: string; match: string }> = [];
  const seen = new Set<string>();

  for (const root of roots) {
    for (const file of listGuardedTypeScriptSources(root)) {
      if (seen.has(file)) {
        continue;
      }
      seen.add(file);

      const content = readFileSync(file, "utf8");
      for (const match of findHardcodedHexInContent(content)) {
        violations.push({
          file: relative(RENDERER_ROOT, file),
          match,
        });
      }
    }
  }

  return violations;
}

for (const token of Object.keys(TECHNICAL_PLAN_V2_COLORS) as BorekColorToken[]) {
  assert.equal(BorekColors[token], TECHNICAL_PLAN_V2_COLORS[token], `token ${token} must match technical plan v2 §16`);
}

for (const value of Object.values(BOREK_COLOR_TOKENS)) {
  assert.match(value, HEX_WITHOUT_HASH, `color ${value} must be 6-char hex without #`);
}

assert.ok(findHardcodedHexInContent('fill: { color: "0057B8" }').includes("0057B8"));
assert.ok(findHardcodedHexInContent("stroke: '#182230'").includes("#182230"));
assert.deepEqual(findHardcodedHexInContent("import { BorekColors } from './colors.js'"), []);

const hexViolations = findHardcodedHexViolations(GUARDED_ROOTS);
assert.equal(
  hexViolations.length,
  0,
  hexViolations.map((v) => `${v.file}: ${v.match}`).join("\n") ||
    "layout and design_system files must not contain hardcoded hex (use BorekColors tokens)",
);

process.stdout.write("AT-11 renderer unit checks passed\n");
