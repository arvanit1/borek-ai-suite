#!/usr/bin/env node
/** Write the approved EXECUTIVE_SUMMARY_01 golden-deck reference PNG (JJ-23). */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { PNG } from "pngjs";

import { SUMMARY_GOLDEN_FILE, buildExecutiveSummary01Png } from "./fixtures.js";

const referenceDir = dirname(fileURLToPath(import.meta.url));
mkdirSync(referenceDir, { recursive: true });
const outputPath = join(referenceDir, SUMMARY_GOLDEN_FILE);
writeFileSync(outputPath, PNG.sync.write(buildExecutiveSummary01Png()));
console.log(`Wrote ${outputPath}`);
