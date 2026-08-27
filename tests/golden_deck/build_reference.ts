#!/usr/bin/env node
/** Write approved golden-deck reference PNGs (run once when calibrating references). */

import { writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { PNG } from "pngjs";

import { buildApprovedSlidePng } from "./fixtures.js";

const referenceDir = join(dirname(fileURLToPath(import.meta.url)), "reference");
const outputPath = join(referenceDir, "slide-01.png");

writeFileSync(outputPath, PNG.sync.write(buildApprovedSlidePng()));
console.log(`Wrote ${outputPath}`);
