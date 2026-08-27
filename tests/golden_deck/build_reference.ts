#!/usr/bin/env node
/** Write approved golden-deck reference PNGs (run once when calibrating references). */

import {
  copyFileSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { PNG } from "pngjs";

import { runLibreOfficePreviewPipeline } from "../../apps/renderer/validation/libreoffice_pipeline.js";
import { buildApprovedSlidePng } from "./fixtures.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const referenceDir = join(HERE, "reference");

/** Render a PPTX with AT-9 and copy only its normalized slide PNGs into a reference directory. */
export function buildPptxReferenceDeck(pptxPath: string, outputDir: string): string[] {
  const temporaryPreviewDir = mkdtempSync(join(tmpdir(), "golden-reference-"));
  const resolvedOutputDir = resolve(outputDir);
  mkdirSync(resolvedOutputDir, { recursive: true });

  try {
    const preview = runLibreOfficePreviewPipeline(resolve(pptxPath), {
      outputDir: temporaryPreviewDir,
    });
    return preview.slideImagePaths.map((sourcePath) => {
      const outputPath = join(resolvedOutputDir, basename(sourcePath));
      copyFileSync(sourcePath, outputPath);
      return outputPath;
    });
  } finally {
    rmSync(temporaryPreviewDir, { recursive: true, force: true });
  }
}

function writeSyntheticAt55Reference(): string {
  const outputPath = join(referenceDir, "slide-01.png");
  writeFileSync(outputPath, PNG.sync.write(buildApprovedSlidePng()));
  return outputPath;
}

function main(): void {
  const args = process.argv.slice(2);
  const pptxIndex = args.indexOf("--pptx");
  const referenceIndex = args.indexOf("--reference");

  if (pptxIndex >= 0) {
    const pptxPath = args[pptxIndex + 1];
    const outputDir = referenceIndex >= 0 ? args[referenceIndex + 1] : undefined;
    if (!pptxPath || !outputDir) {
      throw new Error("Usage: build_reference.ts --pptx <path> --reference <dir>");
    }
    const outputPaths = buildPptxReferenceDeck(pptxPath, outputDir);
    outputPaths.forEach((outputPath) => console.log(`Wrote ${outputPath}`));
    return;
  }

  console.log(`Wrote ${writeSyntheticAt55Reference()}`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  main();
}
