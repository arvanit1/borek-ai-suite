#!/usr/bin/env node
/**
 * AT-55: Golden-deck regression runner — compare rendered PNGs to approved references.
 *
 * Usage:
 *   tsx run_regression.ts --actual <dir> [--reference <dir>] [--expected-count <n>]
 *   tsx run_regression.ts --pptx <path> --output <dir> [--reference <dir>] [--expected-count <n>]
 */

import { writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { runLibreOfficePreviewPipeline } from "../../apps/renderer/validation/libreoffice_pipeline.js";
import {
  compareGoldenDeck,
  formatGoldenDeckReport,
  listGoldenDeckFiles,
  listReferenceSlideFiles,
} from "./compare.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_REFERENCE_DIR = join(HERE, "reference");
const DEFAULT_PPTX = join(HERE, "..", "fixtures", "renderer", "minimal.pptx");

type CliOptions = {
  referenceDir: string;
  actualDir: string | null;
  pptxPath: string | null;
  outputDir: string | null;
  expectedCount: number;
};

function parseArgs(argv: string[]): CliOptions {
  const options: CliOptions = {
    referenceDir: DEFAULT_REFERENCE_DIR,
    actualDir: null,
    pptxPath: null,
    outputDir: null,
    expectedCount: 1,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    const value = argv[index + 1];
    if (token === "--reference" && value) {
      options.referenceDir = resolve(value);
      index += 1;
    } else if (token === "--actual" && value) {
      options.actualDir = resolve(value);
      index += 1;
    } else if (token === "--pptx" && value) {
      options.pptxPath = resolve(value);
      index += 1;
    } else if (token === "--output" && value) {
      options.outputDir = resolve(value);
      index += 1;
    } else if (token === "--expected-count" && value) {
      const expectedCount = Number.parseInt(value, 10);
      if (!Number.isSafeInteger(expectedCount) || expectedCount < 1) {
        throw new Error(`--expected-count must be a positive integer, received: ${value}`);
      }
      options.expectedCount = expectedCount;
      index += 1;
    }
  }

  return options;
}

function main(): number {
  const options = parseArgs(process.argv.slice(2));
  let actualDir = options.actualDir;

  if (!actualDir) {
    const pptxPath = options.pptxPath ?? DEFAULT_PPTX;
    const outputDir = options.outputDir ?? join(HERE, ".tmp", "rendered");
    const preview = runLibreOfficePreviewPipeline(pptxPath, { outputDir });
    writeFileSync(join(outputDir, "preview-manifest.json"), JSON.stringify(preview, null, 2));
    actualDir = outputDir;
  }

  const slideFiles =
    options.expectedCount === 1
      ? listGoldenDeckFiles(options.referenceDir)
      : listReferenceSlideFiles(options.referenceDir, options.expectedCount);
  const result = compareGoldenDeck(options.referenceDir, actualDir, slideFiles);
  const report = formatGoldenDeckReport(result);
  if (result.status === "PASS") {
    process.stdout.write(`${report}\n`);
    return 0;
  }
  process.stderr.write(`${report}\n`);
  return 1;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  process.exit(main());
}

export { main as runGoldenDeckRegression };
