/**
 * AT-55: Approved reference slide fixture for golden-deck regression.
 * Uses Borek brand tokens — calibrates spacing, typography blocks, and colors.
 */

import { PNG } from "pngjs";

import { BorekColors } from "../../apps/renderer/design_system/tokens/colors.js";

const WIDTH = 320;
const HEIGHT = 180;

function hexToRgb(hex: string): [number, number, number] {
  const normalized = hex.replace("#", "");
  return [
    Number.parseInt(normalized.slice(0, 2), 16),
    Number.parseInt(normalized.slice(2, 4), 16),
    Number.parseInt(normalized.slice(4, 6), 16),
  ];
}

function fillRect(
  png: PNG,
  x: number,
  y: number,
  width: number,
  height: number,
  rgb: [number, number, number],
): void {
  for (let row = y; row < y + height; row += 1) {
    for (let col = x; col < x + width; col += 1) {
      const offset = (row * png.width + col) * 4;
      png.data[offset] = rgb[0];
      png.data[offset + 1] = rgb[1];
      png.data[offset + 2] = rgb[2];
      png.data[offset + 3] = 255;
    }
  }
}

/** Deterministic approved slide-01 rendering used as the golden reference. */
export function buildApprovedSlidePng(): PNG {
  const background = hexToRgb(BorekColors.background);
  const title = hexToRgb(BorekColors.text);
  const accent = hexToRgb(BorekColors.primary);
  const body = hexToRgb(BorekColors.mutedText);

  const png = new PNG({ width: WIDTH, height: HEIGHT });
  fillRect(png, 0, 0, WIDTH, HEIGHT, background);
  fillRect(png, 24, 24, 272, 28, title);
  fillRect(png, 24, 60, 96, 4, accent);
  fillRect(png, 24, 76, 240, 14, body);
  fillRect(png, 24, 98, 200, 14, body);
  fillRect(png, 24, 128, 272, 1, hexToRgb(BorekColors.border));
  fillRect(png, 24, 140, 160, 12, body);
  return png;
}

export const APPROVED_SLIDE_SIZE = { width: WIDTH, height: HEIGHT } as const;
