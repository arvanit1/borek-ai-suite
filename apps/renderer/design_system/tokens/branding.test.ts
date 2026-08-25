/** Branding token unit checks executed by pytest via `npm run test:branding --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, normalize, relative } from "node:path";
import { fileURLToPath } from "node:url";

import {
  BOREK_BRANDING_TOKENS,
  BorekBranding,
  BorekBrandingTokens,
  BorekSlide,
  computeBrandingLayout,
} from "./branding.js";
import { BorekColors } from "./colors.js";
import { BorekSpacing } from "./spacing.js";
import { BorekTypography } from "./typography.js";

const INLINE_BRANDING_PLACEHOLDER_PATTERN =
  /placeholderName\s*:\s*["'](?:logo|footer)["']/g;

const INLINE_BRANDING_SLIDE_SIZE_PATTERN =
  /(?:widthInches|heightInches)\s*:\s*[\d.]+/g;

const RENDERER_ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
const CANONICAL_BRANDING_FILE = normalize(join(RENDERER_ROOT, "design_system", "tokens", "branding.ts"));

const GUARDED_ROOTS = [
  join(RENDERER_ROOT, "layouts"),
  join(RENDERER_ROOT, "design_system"),
];

function shouldScanFile(filePath: string): boolean {
  const normalized = normalize(filePath);
  if (!normalized.endsWith(".ts") || normalized.endsWith(".test.ts")) {
    return false;
  }
  return normalized !== CANONICAL_BRANDING_FILE;
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

export function findInlineBrandingPlaceholderInContent(content: string): string[] {
  return [...content.matchAll(INLINE_BRANDING_PLACEHOLDER_PATTERN)].map((match) => match[0]);
}

export function findInlineBrandingSlideSizeInContent(content: string): string[] {
  return [...content.matchAll(INLINE_BRANDING_SLIDE_SIZE_PATTERN)].map((match) => match[0]);
}

function findBrandingViolations(roots: string[]): Array<{ file: string; match: string }> {
  const violations: Array<{ file: string; match: string }> = [];
  const seen = new Set<string>();

  for (const root of roots) {
    for (const file of listGuardedTypeScriptSources(root)) {
      if (seen.has(file)) {
        continue;
      }
      seen.add(file);

      const content = readFileSync(file, "utf8");
      for (const match of findInlineBrandingPlaceholderInContent(content)) {
        violations.push({ file: relative(RENDERER_ROOT, file), match });
      }
      for (const match of findInlineBrandingSlideSizeInContent(content)) {
        violations.push({ file: relative(RENDERER_ROOT, file), match });
      }
    }
  }

  return violations;
}

const layout = computeBrandingLayout();

assert.equal(BorekSlide.widthInches, 13.333);
assert.equal(BorekSlide.heightInches, 7.5);

assert.equal(BorekBranding.logo.placeholderName, "logo");
assert.equal(BorekBranding.footer.placeholderName, "footer");
assert.equal(BorekBranding.slideNumber.format, "number");

assert.equal(layout.logo.x, BorekSpacing.marginX);
assert.equal(layout.logo.y, BorekSpacing.marginTop);
assert.equal(layout.logo.w, BorekSpacing.marginX * 2);
assert.equal(layout.logo.h, BorekSpacing.footerHeight);

assert.equal(layout.footer.x, BorekSpacing.marginX);
assert.equal(layout.footer.y, BorekSlide.heightInches - BorekSpacing.footerHeight);
assert.equal(layout.footer.h, BorekSpacing.footerHeight);
assert.equal(
  layout.footer.w,
  BorekSlide.widthInches - BorekSpacing.marginX * 2 - BorekSpacing.marginX,
);

assert.equal(layout.slideNumber.y, layout.footer.y);
assert.equal(layout.slideNumber.h, BorekSpacing.footerHeight);
assert.equal(layout.slideNumber.color, BorekColors.mutedText);
assert.equal(layout.slideNumber.fontFace, BorekTypography.fonts.body);
assert.equal(layout.slideNumber.fontSize, BorekTypography.defaultSizes.body);
assert.equal(layout.slideNumber.align, "right");
assert.equal(layout.slideNumber.format, "number");

assert.deepEqual(BorekBrandingTokens, { slide: BorekSlide, branding: BorekBranding });
assert.deepEqual(BOREK_BRANDING_TOKENS, BorekBrandingTokens);

assert.ok(findInlineBrandingPlaceholderInContent('placeholderName: "logo"').length > 0);
assert.ok(findInlineBrandingSlideSizeInContent("widthInches: 13.333").length > 0);
assert.deepEqual(findInlineBrandingPlaceholderInContent("import { BorekBranding } from './branding.js'"), []);

const brandingViolations = findBrandingViolations(GUARDED_ROOTS);
assert.equal(
  brandingViolations.length,
  0,
  brandingViolations.map((v) => `${v.file}: ${v.match}`).join("\n") ||
    "layout and design_system files must not hardcode branding placeholders or slide size (use BorekBranding tokens)",
);

process.stdout.write("branding token unit checks passed\n");
