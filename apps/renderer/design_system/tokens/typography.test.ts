/** AT-12 unit checks executed by pytest via `npm run test:at12 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, normalize, relative } from "node:path";
import { fileURLToPath } from "node:url";

import {
  BOREK_TYPOGRAPHY_TOKENS,
  BorekDefaultFontSizes,
  BorekFontFamilies,
  BorekTypography,
  type BorekFontRole,
} from "./typography.js";

/** Technical plan v2 §16 — BorekTheme.fonts seed families (expected values for tests only). */
const TECHNICAL_PLAN_V2_FONT_FAMILIES: Record<BorekFontRole, string> = {
  heading: "Aptos Display",
  body: "Aptos",
};

const FONT_FAMILY_PATTERNS = [
  /["']Aptos Display["']/g,
  /["']Aptos["'](?!\s*Display)/g,
];

export const INLINE_FONT_SIZE_PATTERN = /fontSize\s*:\s*\d+(?:\.\d+)?/g;

const RENDERER_ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
const CANONICAL_TYPOGRAPHY_FILE = normalize(join(RENDERER_ROOT, "design_system", "tokens", "typography.ts"));

const GUARDED_ROOTS = [
  join(RENDERER_ROOT, "layouts"),
  join(RENDERER_ROOT, "design_system"),
];

function shouldScanFile(filePath: string): boolean {
  const normalized = normalize(filePath);
  if (!normalized.endsWith(".ts") || normalized.endsWith(".test.ts")) {
    return false;
  }
  return normalized !== CANONICAL_TYPOGRAPHY_FILE;
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

export function findHardcodedFontFamilyInContent(content: string): string[] {
  const matches: string[] = [];
  for (const pattern of FONT_FAMILY_PATTERNS) {
    for (const match of content.matchAll(pattern)) {
      matches.push(match[0]);
    }
  }
  return matches;
}

export function findInlineFontSizeInContent(content: string): string[] {
  return [...content.matchAll(INLINE_FONT_SIZE_PATTERN)].map((match) => match[0]);
}

function findTypographyViolations(roots: string[]): Array<{ file: string; match: string }> {
  const violations: Array<{ file: string; match: string }> = [];
  const seen = new Set<string>();

  for (const root of roots) {
    for (const file of listGuardedTypeScriptSources(root)) {
      if (seen.has(file)) {
        continue;
      }
      seen.add(file);

      const content = readFileSync(file, "utf8");
      for (const match of findHardcodedFontFamilyInContent(content)) {
        violations.push({ file: relative(RENDERER_ROOT, file), match });
      }
      for (const match of findInlineFontSizeInContent(content)) {
        violations.push({ file: relative(RENDERER_ROOT, file), match });
      }
    }
  }

  return violations;
}

for (const role of Object.keys(TECHNICAL_PLAN_V2_FONT_FAMILIES) as BorekFontRole[]) {
  assert.equal(
    BorekFontFamilies[role],
    TECHNICAL_PLAN_V2_FONT_FAMILIES[role],
    `font family ${role} must match technical plan v2 §16`,
  );
}

assert.deepEqual(Object.keys(BorekDefaultFontSizes).sort(), Object.keys(BorekFontFamilies).sort());
for (const size of Object.values(BorekDefaultFontSizes)) {
  assert.equal(typeof size, "number");
  assert.ok(size > 0, "default font sizes must be positive point values");
}

assert.equal(BorekTypography.fonts, BorekFontFamilies);
assert.equal(BorekTypography.defaultSizes, BorekDefaultFontSizes);
assert.deepEqual(BOREK_TYPOGRAPHY_TOKENS, BorekTypography);

assert.ok(findHardcodedFontFamilyInContent('fontFace: "Aptos Display"').length > 0);
assert.ok(findHardcodedFontFamilyInContent("fontFace: 'Aptos'").length > 0);
assert.deepEqual(findHardcodedFontFamilyInContent("import { BorekFontFamilies } from './typography.js'"), []);
assert.ok(findInlineFontSizeInContent("fontSize: 18").length > 0);
assert.deepEqual(findInlineFontSizeInContent("import { BorekDefaultFontSizes } from './typography.js'"), []);

const typographyViolations = findTypographyViolations(GUARDED_ROOTS);
assert.equal(
  typographyViolations.length,
  0,
  typographyViolations.map((v) => `${v.file}: ${v.match}`).join("\n") ||
    "layout and design_system files must not hardcode font families or fontSize (use BorekTypography tokens)",
);

process.stdout.write("AT-12 renderer unit checks passed\n");
