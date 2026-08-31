#!/usr/bin/env node
/** Write approved Group C golden-deck reference PNGs (MS-23). Token-derived schematics. */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { PNG } from "pngjs";

import { computeArchitecture01Layout } from "../../../apps/renderer/layouts/group_c/renderArchitecture01.js";
import { computeCardGridLayout } from "../../../apps/renderer/layouts/group_c/cardGrid.js";
import { computeNextSteps01Layout } from "../../../apps/renderer/layouts/group_c/renderNextSteps01.js";
import { computeOpenQuestions01Layout } from "../../../apps/renderer/layouts/group_c/renderOpenQuestions01.js";
import { BorekSlide } from "../../../apps/renderer/design_system/tokens/branding.js";
import { BorekColors } from "../../../apps/renderer/design_system/tokens/colors.js";
import { BorekSpacing } from "../../../apps/renderer/design_system/tokens/spacing.js";
import { GROUP_C_GOLDEN_CASES } from "./fixtures.js";

export const GROUP_C_GOLDEN_WIDTH = 2001;
export const GROUP_C_GOLDEN_HEIGHT = 1125;
const SCALE = GROUP_C_GOLDEN_WIDTH / BorekSlide.widthInches;

type Rgb = [number, number, number];
type InchRect = { x: number; y: number; w: number; h: number };

function hexToRgb(hex: string): Rgb {
  const normalized = hex.replace("#", "");
  return [
    Number.parseInt(normalized.slice(0, 2), 16),
    Number.parseInt(normalized.slice(2, 4), 16),
    Number.parseInt(normalized.slice(4, 6), 16),
  ];
}

function fillRect(png: PNG, x: number, y: number, width: number, height: number, rgb: Rgb): void {
  const x0 = Math.max(0, Math.floor(x));
  const y0 = Math.max(0, Math.floor(y));
  const x1 = Math.min(png.width, Math.ceil(x + width));
  const y1 = Math.min(png.height, Math.ceil(y + height));
  for (let row = y0; row < y1; row += 1) {
    for (let col = x0; col < x1; col += 1) {
      const offset = (row * png.width + col) * 4;
      png.data[offset] = rgb[0];
      png.data[offset + 1] = rgb[1];
      png.data[offset + 2] = rgb[2];
      png.data[offset + 3] = 255;
    }
  }
}

function px(inches: number): number {
  return inches * SCALE;
}

function fillInchRect(png: PNG, rect: InchRect, rgb: Rgb, inset = 0): void {
  fillRect(
    png,
    px(rect.x) + inset,
    px(rect.y) + inset,
    Math.max(1, px(rect.w) - inset * 2),
    Math.max(1, px(rect.h) - inset * 2),
    rgb,
  );
}

function isDarkSpec(spec: { darkBackground?: boolean }): boolean {
  return Boolean(spec.darkBackground);
}

function blankSlide(dark: boolean): PNG {
  const png = new PNG({ width: GROUP_C_GOLDEN_WIDTH, height: GROUP_C_GOLDEN_HEIGHT });
  fillRect(
    png,
    0,
    0,
    png.width,
    png.height,
    hexToRgb(dark ? BorekColors.coverBackground : BorekColors.background),
  );
  const titleColor = hexToRgb(dark ? BorekColors.background : BorekColors.text);
  fillRect(png, px(BorekSpacing.marginX), px(1.1), px(12.0), px(0.28), titleColor);
  fillRect(png, px(BorekSpacing.marginX), px(1.45), px(2.4), px(0.08), hexToRgb(BorekColors.primary));
  fillRect(
    png,
    px(BorekSpacing.marginX),
    px(7.15),
    px(12.0),
    px(0.04),
    hexToRgb(dark ? BorekColors.mutedText : BorekColors.border),
  );
  return png;
}

function paintCards(png: PNG, cards: readonly InchRect[], dark: boolean): void {
  const border = hexToRgb(dark ? BorekColors.mutedText : BorekColors.border);
  const fill = hexToRgb(dark ? BorekColors.coverBackground : BorekColors.background);
  for (const card of cards) {
    fillInchRect(png, card, border);
    fillInchRect(png, card, fill, 3);
  }
}

export function buildGroupCGoldenPng(layoutId: string, spec: Record<string, unknown>): PNG {
  const dark = isDarkSpec(spec);
  const png = blankSlide(dark);

  if (layoutId === "ARCHITECTURE_01") {
    const components = spec.components as unknown[];
    const layout = computeArchitecture01Layout(Boolean(spec.subtitle), components.length);
    paintCards(png, layout.nodes, false);
    for (const node of layout.nodes) {
      fillRect(
        png,
        px(node.x) - 6,
        px(node.y) - 6,
        12,
        12,
        hexToRgb(BorekColors.primary),
      );
    }
    return png;
  }

  if (layoutId === "COMPLIANCE_01") {
    const items = spec.items as unknown[];
    const layout = computeCardGridLayout(Boolean(spec.subtitle), items.length, dark);
    paintCards(png, layout.cards, dark);
    return png;
  }

  if (layoutId === "SUCCESS_METRICS_01") {
    const criteria = spec.criteria as unknown[];
    const layout = computeCardGridLayout(Boolean(spec.subtitle), criteria.length);
    paintCards(png, layout.cards, false);
    for (const card of layout.cards) {
      fillRect(
        png,
        px(card.x) + 8,
        px(card.y) + 8,
        Math.max(12, px(card.w) - 16),
        10,
        hexToRgb(BorekColors.primary),
      );
    }
    return png;
  }

  if (layoutId === "OPEN_QUESTIONS_01") {
    const layout = computeOpenQuestions01Layout(Boolean(spec.subtitle));
    fillInchRect(png, layout.left.heading, hexToRgb(BorekColors.text));
    fillInchRect(png, layout.right.heading, hexToRgb(BorekColors.text));
    fillInchRect(png, layout.left.list, hexToRgb(BorekColors.border));
    fillInchRect(png, layout.right.list, hexToRgb(BorekColors.border));
    fillInchRect(png, layout.left.list, hexToRgb(BorekColors.background), 3);
    fillInchRect(png, layout.right.list, hexToRgb(BorekColors.background), 3);
    return png;
  }

  if (layoutId === "NEXT_STEPS_01") {
    const steps = spec.steps as unknown[];
    const layout = computeNextSteps01Layout(Boolean(spec.subtitle), dark, steps.length);
    fillInchRect(png, layout.checklist, hexToRgb(BorekColors.mutedText));
    fillInchRect(png, layout.checklist, hexToRgb(BorekColors.coverBackground), 3);
    for (const row of layout.stepRows) {
      fillInchRect(png, row.badge, hexToRgb(BorekColors.primary));
      fillInchRect(png, row.text, hexToRgb(BorekColors.background));
    }
    return png;
  }

  throw new Error(`Unsupported Group C golden layout: ${layoutId}`);
}

const referenceDir = dirname(fileURLToPath(import.meta.url));
mkdirSync(referenceDir, { recursive: true });

for (const goldenCase of GROUP_C_GOLDEN_CASES) {
  const outputPath = join(referenceDir, goldenCase.referenceFileName);
  const png = buildGroupCGoldenPng(
    goldenCase.layoutId,
    goldenCase.spec as unknown as Record<string, unknown>,
  );
  writeFileSync(outputPath, PNG.sync.write(png));
  console.log(`Wrote ${outputPath}`);
}
