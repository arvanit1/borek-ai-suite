/**
 * JJ-23: Approved EXECUTIVE_SUMMARY_01 golden-deck reference fixture.
 * Schematic PNG is token-derived from the live layout compute function.
 */

import { PNG } from "pngjs";

import type { LayoutId, SlideSpecBase } from "../../../apps/renderer/src/contracts.js";
import { BorekSlide } from "../../../apps/renderer/design_system/tokens/branding.js";
import { BorekColors } from "../../../apps/renderer/design_system/tokens/colors.js";
import { computeExecutiveSummary01Layout } from "../../../apps/renderer/layouts/summary/renderExecutiveSummary01.js";
import executiveSummaryFixtureJson from "../../../packages/contracts/fixtures/slide_spec/summary/executive_summary_01.realistic.json" with { type: "json" };

export const SUMMARY_GOLDEN_WIDTH = 320;
export const SUMMARY_GOLDEN_HEIGHT = 180;
export const SUMMARY_GOLDEN_SCALE = SUMMARY_GOLDEN_HEIGHT / BorekSlide.heightInches;
export const SUMMARY_GOLDEN_FILE = "executive_summary_01.png" as const;

export type SummaryGoldenCase = {
  id: string;
  layoutId: LayoutId;
  referenceFileName: typeof SUMMARY_GOLDEN_FILE;
  sourceFixture: string;
  spec: SlideSpecBase;
};

export const SUMMARY_GOLDEN_CASE: SummaryGoldenCase = {
  id: "executive-summary-01",
  layoutId: "EXECUTIVE_SUMMARY_01",
  referenceFileName: SUMMARY_GOLDEN_FILE,
  sourceFixture: "executive_summary_01.realistic.json",
  spec: executiveSummaryFixtureJson as unknown as SlideSpecBase,
};

type Rgb = [number, number, number];

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
  return inches * SUMMARY_GOLDEN_SCALE;
}

function fillInchRect(
  png: PNG,
  rect: { x: number; y: number; w: number; h: number },
  rgb: Rgb,
  inset = 0,
): void {
  fillRect(
    png,
    px(rect.x) + inset,
    px(rect.y) + inset,
    Math.max(1, px(rect.w) - inset * 2),
    Math.max(1, px(rect.h) - inset * 2),
    rgb,
  );
}

export function buildExecutiveSummary01Png(): PNG {
  const png = new PNG({ width: SUMMARY_GOLDEN_WIDTH, height: SUMMARY_GOLDEN_HEIGHT });
  fillRect(png, 0, 0, png.width, png.height, hexToRgb(BorekColors.background));
  fillRect(png, px(0.65), px(1.1), px(12.0), px(0.28), hexToRgb(BorekColors.text));
  fillRect(png, px(0.65), px(1.45), px(2.4), px(0.08), hexToRgb(BorekColors.primary));
  fillRect(png, px(0.65), px(7.15), px(12.0), px(0.04), hexToRgb(BorekColors.border));
  const layout = computeExecutiveSummary01Layout(true, 4);
  fillInchRect(png, layout.headline, hexToRgb(BorekColors.text));
  for (const card of layout.highlights) {
    fillInchRect(png, card, hexToRgb(BorekColors.border));
    fillInchRect(png, card, hexToRgb(BorekColors.background), 2);
  }
  return png;
}
