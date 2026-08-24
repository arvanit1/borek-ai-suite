#!/usr/bin/env node
/** CLI entry for AT-9 preview pipeline (worker jobs and tests). */

import { resolve } from "node:path";
import { runLibreOfficePreviewPipeline } from "../validation/libreoffice_pipeline.js";

function main(): number {
  const pptxPath = process.argv[2];
  const outputDir = process.argv[3];

  if (!pptxPath || !outputDir) {
    console.error("Usage: run_preview_pipeline.ts <pptxPath> <outputDir>");
    return 1;
  }

  try {
    const result = runLibreOfficePreviewPipeline(resolve(pptxPath), {
      outputDir: resolve(outputDir),
    });
    process.stdout.write(`${JSON.stringify(result)}\n`);
    return 0;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(message);
    return 1;
  }
}

process.exit(main());
