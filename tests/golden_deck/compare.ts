/**
 * AT-55: Compare rendered slide PNGs against approved reference renderings.
 * Flags spacing, font, alignment, and color differences.
 */

import { existsSync, readFileSync } from "node:fs";
import { basename, join } from "node:path";
import { PNG } from "pngjs";

export type GoldenDeckDiffCategory = "spacing" | "font" | "alignment" | "color";

export type GoldenDeckDiff = {
  category: GoldenDeckDiffCategory;
  slideIndex: number;
  message: string;
  diffPixels: number;
};

export type GoldenDeckComparisonResult = {
  status: "PASS" | "FAIL";
  diffs: GoldenDeckDiff[];
};

const COLOR_TOLERANCE = 8;
const ALIGNMENT_SHIFT_THRESHOLD = 2;
const SPACING_GAP_DELTA_THRESHOLD = 3;
const FONT_BAND_HEIGHT_DELTA_THRESHOLD = 2;

type Rgb = [number, number, number];

export function readPng(path: string): PNG {
  return PNG.sync.read(readFileSync(path));
}

export function compareGoldenDeck(
  referenceDir: string,
  actualDir: string,
  slideFileNames: string[],
): GoldenDeckComparisonResult {
  const diffs: GoldenDeckDiff[] = [];

  for (const [index, fileName] of slideFileNames.entries()) {
    const referencePath = join(referenceDir, fileName);
    const actualPath = join(actualDir, fileName);
    const reference = readPng(referencePath);
    const actual = readPng(actualPath);
    diffs.push(...compareSlidePng(reference, actual, index + 1));
  }

  return diffs.length === 0
    ? { status: "PASS", diffs: [] }
    : { status: "FAIL", diffs };
}

export function compareSlidePng(reference: PNG, actual: PNG, slideIndex: number): GoldenDeckDiff[] {
  const diffs: GoldenDeckDiff[] = [];

  if (reference.width !== actual.width || reference.height !== actual.height) {
    diffs.push({
      category: "alignment",
      slideIndex,
      message: `Slide canvas size differs (reference ${reference.width}x${reference.height}, actual ${actual.width}x${actual.height})`,
      diffPixels: Math.abs(reference.width - actual.width) + Math.abs(reference.height - actual.height),
    });
    return diffs;
  }

  const diffMask = buildDiffMask(reference, actual);
  const diffPixels = countTrue(diffMask);
  if (diffPixels === 0) {
    return diffs;
  }

  const samePositionColorDiffs = countSamePositionColorDiffs(reference, actual, diffMask);
  if (samePositionColorDiffs > 0) {
    diffs.push({
      category: "color",
      slideIndex,
      message: `Color mismatch on ${samePositionColorDiffs} pixel(s) at matching coordinates`,
      diffPixels: samePositionColorDiffs,
    });
  }

  const referenceCentroid = contentCentroid(reference);
  const actualCentroid = contentCentroid(actual);
  const horizontalShift = Math.abs(referenceCentroid.x - actualCentroid.x);
  const verticalShift = Math.abs(referenceCentroid.y - actualCentroid.y);
  if (
    horizontalShift > ALIGNMENT_SHIFT_THRESHOLD ||
    verticalShift > ALIGNMENT_SHIFT_THRESHOLD
  ) {
    diffs.push({
      category: "alignment",
      slideIndex,
      message: `Content centroid shifted by ${horizontalShift}px horizontally and ${verticalShift}px vertically`,
      diffPixels,
    });
  }

  const spacingDelta = verticalGapDelta(reference, actual);
  if (spacingDelta >= SPACING_GAP_DELTA_THRESHOLD) {
    diffs.push({
      category: "spacing",
      slideIndex,
      message: `Vertical spacing profile changed by ${spacingDelta}px between content bands`,
      diffPixels,
    });
  }

  const fontBandDelta = textBandHeightDelta(reference, actual);
  if (fontBandDelta >= FONT_BAND_HEIGHT_DELTA_THRESHOLD) {
    diffs.push({
      category: "font",
      slideIndex,
      message: `Text band height changed by ${fontBandDelta}px (possible font size or line-height drift)`,
      diffPixels,
    });
  }

  if (diffs.length === 0) {
    diffs.push({
      category: "color",
      slideIndex,
      message: `Rendered slide differs from reference by ${diffPixels} pixel(s)`,
      diffPixels,
    });
  }

  return diffs;
}

function buildDiffMask(reference: PNG, actual: PNG): boolean[] {
  const mask = new Array<boolean>(reference.width * reference.height).fill(false);
  for (let row = 0; row < reference.height; row += 1) {
    for (let col = 0; col < reference.width; col += 1) {
      const offset = (row * reference.width + col) * 4;
      const referenceRgb: Rgb = [
        reference.data[offset] ?? 0,
        reference.data[offset + 1] ?? 0,
        reference.data[offset + 2] ?? 0,
      ];
      const actualRgb: Rgb = [
        actual.data[offset] ?? 0,
        actual.data[offset + 1] ?? 0,
        actual.data[offset + 2] ?? 0,
      ];
      if (!rgbClose(referenceRgb, actualRgb)) {
        mask[row * reference.width + col] = true;
      }
    }
  }
  return mask;
}

function countSamePositionColorDiffs(reference: PNG, actual: PNG, diffMask: boolean[]): number {
  let count = 0;
  for (let row = 0; row < reference.height; row += 1) {
    for (let col = 0; col < reference.width; col += 1) {
      const index = row * reference.width + col;
      if (!diffMask[index]) {
        continue;
      }
      const offset = index * 4;
      const referenceRgb: Rgb = [
        reference.data[offset] ?? 0,
        reference.data[offset + 1] ?? 0,
        reference.data[offset + 2] ?? 0,
      ];
      const actualRgb: Rgb = [
        actual.data[offset] ?? 0,
        actual.data[offset + 1] ?? 0,
        actual.data[offset + 2] ?? 0,
      ];
      if (!rgbClose(referenceRgb, actualRgb)) {
        count += 1;
      }
    }
  }
  return count;
}

function contentCentroid(png: PNG): { x: number; y: number } {
  let sumX = 0;
  let sumY = 0;
  let count = 0;
  for (let row = 0; row < png.height; row += 1) {
    for (let col = 0; col < png.width; col += 1) {
      const offset = (row * png.width + col) * 4;
      const red = png.data[offset] ?? 255;
      const green = png.data[offset + 1] ?? 255;
      const blue = png.data[offset + 2] ?? 255;
      if (red < 250 || green < 250 || blue < 250) {
        sumX += col;
        sumY += row;
        count += 1;
      }
    }
  }
  if (count === 0) {
    return { x: 0, y: 0 };
  }
  return { x: sumX / count, y: sumY / count };
}

function verticalGapDelta(reference: PNG, actual: PNG): number {
  const referenceGaps = verticalGapPositions(reference);
  const actualGaps = verticalGapPositions(actual);
  const length = Math.max(referenceGaps.length, actualGaps.length);
  let maxDelta = 0;
  for (let index = 0; index < length; index += 1) {
    const referenceGap = referenceGaps[index] ?? 0;
    const actualGap = actualGaps[index] ?? 0;
    maxDelta = Math.max(maxDelta, Math.abs(referenceGap - actualGap));
  }
  return maxDelta;
}

function verticalGapPositions(png: PNG): number[] {
  const gaps: number[] = [];
  let inContent = false;
  let gapStart = 0;
  for (let row = 0; row < png.height; row += 1) {
    const hasContent = rowHasContent(png, row);
    if (!inContent && hasContent) {
      if (gapStart > 0) {
        gaps.push(row - gapStart);
      }
      inContent = true;
    } else if (inContent && !hasContent) {
      gapStart = row;
      inContent = false;
    }
  }
  return gaps;
}

function textBandHeightDelta(reference: PNG, actual: PNG): number {
  const referenceBands = textBandHeights(reference);
  const actualBands = textBandHeights(actual);
  const length = Math.max(referenceBands.length, actualBands.length);
  let maxDelta = 0;
  for (let index = 0; index < length; index += 1) {
    const referenceHeight = referenceBands[index] ?? 0;
    const actualHeight = actualBands[index] ?? 0;
    maxDelta = Math.max(maxDelta, Math.abs(referenceHeight - actualHeight));
  }
  return maxDelta;
}

function textBandHeights(png: PNG): number[] {
  const heights: number[] = [];
  let bandStart = -1;
  for (let row = 0; row < png.height; row += 1) {
    const hasContent = rowHasContent(png, row);
    if (hasContent && bandStart < 0) {
      bandStart = row;
    } else if (!hasContent && bandStart >= 0) {
      heights.push(row - bandStart);
      bandStart = -1;
    }
  }
  if (bandStart >= 0) {
    heights.push(png.height - bandStart);
  }
  return heights;
}

function rowHasContent(png: PNG, row: number): boolean {
  for (let col = 0; col < png.width; col += 1) {
    const offset = (row * png.width + col) * 4;
    const red = png.data[offset] ?? 255;
    const green = png.data[offset + 1] ?? 255;
    const blue = png.data[offset + 2] ?? 255;
    if (red < 250 || green < 250 || blue < 250) {
      return true;
    }
  }
  return false;
}

function rgbClose(left: Rgb, right: Rgb): boolean {
  return (
    Math.abs(left[0] - right[0]) <= COLOR_TOLERANCE &&
    Math.abs(left[1] - right[1]) <= COLOR_TOLERANCE &&
    Math.abs(left[2] - right[2]) <= COLOR_TOLERANCE
  );
}

function countTrue(values: boolean[]): number {
  return values.reduce((count, value) => count + (value ? 1 : 0), 0);
}

export function formatGoldenDeckReport(result: GoldenDeckComparisonResult): string {
  if (result.status === "PASS") {
    return "Golden deck regression passed.";
  }
  const lines = result.diffs.map(
    (diff) =>
      `[${diff.category}] slide ${diff.slideIndex}: ${diff.message} (${diff.diffPixels} diff pixel(s))`,
  );
  return ["Golden deck regression failed:", ...lines].join("\n");
}

export function listReferenceSlideFiles(_referenceDir: string, expectedCount = 1): string[] {
  return Array.from({ length: expectedCount }, (_, index) =>
    `slide-${String(index + 1).padStart(2, "0")}.png`,
  );
}

export const GROUP_B_GOLDEN_FILES = [
  "process_flow_01.png",
  "timeline_01.png",
  "milestones_01.png",
  "team_fte_01.png",
] as const;

export const SUMMARY_GOLDEN_FILES = ["executive_summary_01.png"] as const;

/** Resolve comparison file names for a reference directory (AT-55, JJ-22, or JJ-23). */
export function listGoldenDeckFiles(referenceDir: string): string[] {
  const groupB = GROUP_B_GOLDEN_FILES.filter((fileName) => existsSync(join(referenceDir, fileName)));
  if (groupB.length === GROUP_B_GOLDEN_FILES.length) {
    return [...groupB];
  }
  const summary = SUMMARY_GOLDEN_FILES.filter((fileName) => existsSync(join(referenceDir, fileName)));
  if (summary.length === SUMMARY_GOLDEN_FILES.length) {
    return [...summary];
  }
  return listReferenceSlideFiles(referenceDir);
}

export function slideFileName(slideIndex: number): string {
  return `slide-${String(slideIndex).padStart(2, "0")}.png`;
}

export function parseSlideFileIndex(fileName: string): number {
  const match = basename(fileName).match(/^slide-(\d+)\.png$/);
  if (!match) {
    throw new Error(`Unexpected slide file name: ${fileName}`);
  }
  return Number.parseInt(match[1]!, 10);
}
