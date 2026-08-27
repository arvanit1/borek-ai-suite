/** AT-55: Golden-deck regression runner tests. */

import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { PNG } from "pngjs";

import {
  compareGoldenDeck,
  compareSlidePng,
  formatGoldenDeckReport,
  readPng,
} from "./compare.js";

const referenceDir = join(import.meta.dirname, "reference");
const referencePath = join(referenceDir, "slide-01.png");

function writePng(path: string, png: PNG): void {
  writeFileSync(path, PNG.sync.write(png));
}

function clonePng(source: PNG): PNG {
  const copy = new PNG({ width: source.width, height: source.height });
  source.data.copy(copy.data);
  return copy;
}

function shiftHorizontally(source: PNG, pixels: number): PNG {
  const shifted = clonePng(source);
  shifted.data.fill(255);
  for (let row = 0; row < source.height; row += 1) {
    for (let col = 0; col < source.width; col += 1) {
      const targetCol = col + pixels;
      if (targetCol >= source.width) {
        continue;
      }
      const sourceOffset = (row * source.width + col) * 4;
      const targetOffset = (row * shifted.width + targetCol) * 4;
      shifted.data[targetOffset] = source.data[sourceOffset] ?? 255;
      shifted.data[targetOffset + 1] = source.data[sourceOffset + 1] ?? 255;
      shifted.data[targetOffset + 2] = source.data[sourceOffset + 2] ?? 255;
      shifted.data[targetOffset + 3] = source.data[sourceOffset + 3] ?? 255;
    }
  }
  return shifted;
}

function recolorTitleBar(source: PNG, rgb: [number, number, number]): PNG {
  const recolored = clonePng(source);
  for (let row = 24; row < 52; row += 1) {
    for (let col = 24; col < 296; col += 1) {
      const offset = (row * recolored.width + col) * 4;
      recolored.data[offset] = rgb[0];
      recolored.data[offset + 1] = rgb[1];
      recolored.data[offset + 2] = rgb[2];
    }
  }
  return recolored;
}

function widenVerticalGap(source: PNG, extraGap: number): PNG {
  const spaced = clonePng(source);
  spaced.data.fill(255);
  for (let row = 0; row < source.height; row += 1) {
    const targetRow = row >= 90 ? row + extraGap : row;
    if (targetRow >= source.height) {
      continue;
    }
    for (let col = 0; col < source.width; col += 1) {
      const sourceOffset = (row * source.width + col) * 4;
      const targetOffset = (targetRow * spaced.width + col) * 4;
      spaced.data[targetOffset] = source.data[sourceOffset] ?? 255;
      spaced.data[targetOffset + 1] = source.data[sourceOffset + 1] ?? 255;
      spaced.data[targetOffset + 2] = source.data[sourceOffset + 2] ?? 255;
      spaced.data[targetOffset + 3] = source.data[sourceOffset + 3] ?? 255;
    }
  }
  return spaced;
}

function thickenBodyBand(source: PNG, extraHeight: number): PNG {
  const adjusted = clonePng(source);
  for (let row = 76; row < 76 + 14 + extraHeight; row += 1) {
    for (let col = 24; col < 264; col += 1) {
      const offset = (row * adjusted.width + col) * 4;
      adjusted.data[offset] = 102;
      adjusted.data[offset + 1] = 112;
      adjusted.data[offset + 2] = 133;
      adjusted.data[offset + 3] = 255;
    }
  }
  return adjusted;
}

assert.ok(readFileSync(referencePath).length > 0, "approved reference slide must exist");

{
  const reference = readPng(referencePath);
  const actual = readPng(referencePath);
  const result = compareGoldenDeck(referenceDir, referenceDir, ["slide-01.png"]);
  assert.equal(result.status, "PASS");
  assert.deepEqual(result.diffs, []);
}

{
  const reference = readPng(referencePath);
  const shifted = shiftHorizontally(reference, 6);
  const diffs = compareSlidePng(reference, shifted, 1);
  assert.ok(diffs.some((diff) => diff.category === "alignment"));
}

{
  const reference = readPng(referencePath);
  const recolored = recolorTitleBar(reference, [0, 87, 184]);
  const diffs = compareSlidePng(reference, recolored, 1);
  assert.ok(diffs.some((diff) => diff.category === "color"));
}

{
  const reference = readPng(referencePath);
  const spaced = widenVerticalGap(reference, 8);
  const diffs = compareSlidePng(reference, spaced, 1);
  assert.ok(diffs.some((diff) => diff.category === "spacing"));
}

{
  const reference = readPng(referencePath);
  const fontDrift = thickenBodyBand(reference, 4);
  const diffs = compareSlidePng(reference, fontDrift, 1);
  assert.ok(diffs.some((diff) => diff.category === "font"));
}

{
  const tempDir = mkdtempSync(join(tmpdir(), "at55-golden-"));
  const actualPath = join(tempDir, "slide-01.png");
  writePng(actualPath, shiftHorizontally(readPng(referencePath), 5));
  const result = compareGoldenDeck(referenceDir, tempDir, ["slide-01.png"]);
  assert.equal(result.status, "FAIL");
  const report = formatGoldenDeckReport(result);
  assert.match(report, /alignment/);
}

console.log("AT-55 golden-deck regression tests passed");
