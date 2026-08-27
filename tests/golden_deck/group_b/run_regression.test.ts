/** JJ-22: Group B golden-deck regression — approved PNG per layout, wired to AT-55 compare. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { PNG } from "pngjs";

import { compareGoldenDeck, compareSlidePng, readPng } from "../compare.js";
import {
  GROUP_B_GOLDEN_FILES,
  GROUP_B_GOLDEN_HEIGHT,
  GROUP_B_GOLDEN_WIDTH,
  buildGroupBGoldenPng,
} from "./fixtures.js";

const referenceDir = fileURLToPath(new URL(".", import.meta.url));

for (const fileName of GROUP_B_GOLDEN_FILES) {
  const path = join(referenceDir, fileName);
  assert.ok(existsSync(path), `approved Group B reference must exist: ${fileName}`);
  assert.ok(readFileSync(path).length > 0, `${fileName} must be a non-empty PNG`);
  const png = readPng(path);
  assert.equal(png.width, GROUP_B_GOLDEN_WIDTH);
  assert.equal(png.height, GROUP_B_GOLDEN_HEIGHT);
}

{
  const result = compareGoldenDeck(referenceDir, referenceDir, [...GROUP_B_GOLDEN_FILES]);
  assert.equal(result.status, "PASS");
  assert.deepEqual(result.diffs, []);
}

for (const fileName of GROUP_B_GOLDEN_FILES) {
  const generated = buildGroupBGoldenPng(fileName);
  const stored = readPng(join(referenceDir, fileName));
  const generatedCopy = new PNG({ width: generated.width, height: generated.height });
  generated.data.copy(generatedCopy.data);
  const diffs = compareSlidePng(stored, generatedCopy, 1);
  assert.deepEqual(diffs, [], `${fileName} must match the live layout fixture builder`);
}

console.log("JJ-22 Group B golden-deck regression tests passed");
