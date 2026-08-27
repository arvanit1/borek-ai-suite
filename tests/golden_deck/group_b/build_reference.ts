#!/usr/bin/env node
/** Write approved Group B golden-deck reference PNGs (JJ-22). */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { PNG } from "pngjs";

import {
  GROUP_B_GOLDEN_FILES,
  buildGroupBGoldenPng,
} from "./fixtures.js";

const referenceDir = dirname(fileURLToPath(import.meta.url));
mkdirSync(referenceDir, { recursive: true });

for (const fileName of GROUP_B_GOLDEN_FILES) {
  const outputPath = join(referenceDir, fileName);
  writeFileSync(outputPath, PNG.sync.write(buildGroupBGoldenPng(fileName)));
  console.log(`Wrote ${outputPath}`);
}
