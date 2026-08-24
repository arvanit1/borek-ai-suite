/** AT-9 unit checks executed by pytest via `npm run test:at9 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  LibreOfficePipelineError,
  expectedPdfPath,
  formatSlideImageFilename,
  normalizeSlideImagePaths,
  runLibreOfficePreviewPipeline,
} from "./libreoffice_pipeline.js";

assert.equal(formatSlideImageFilename(1, 9), "slide-01.png");
assert.equal(formatSlideImageFilename(10, 12), "slide-10.png");
assert.equal(formatSlideImageFilename(1, 120), "slide-001.png");

assert.equal(
  expectedPdfPath("/tmp/deck/presentation.pptx", "/tmp/deck/preview"),
  join("/tmp/deck/preview", "presentation.pdf"),
);

const tempDir = mkdtempSync(join(tmpdir(), "at9-normalize-"));
const rawPaths = [
  join(tempDir, "slide-2.png"),
  join(tempDir, "slide-1.png"),
];
writeFileSync(rawPaths[0], "b");
writeFileSync(rawPaths[1], "a");

const normalized = normalizeSlideImagePaths(tempDir, rawPaths);
assert.deepEqual(
  normalized.map((path) => path.split(/[\\/]/).pop()),
  ["slide-01.png", "slide-02.png"],
);

const multiSlideDir = mkdtempSync(join(tmpdir(), "at9-normalize-many-"));
const multiSlideCount = 12;
const shuffledPaths = Array.from({ length: multiSlideCount }, (_, index) => {
  const path = join(multiSlideDir, `slide-${index + 1}.png`);
  writeFileSync(path, String(index + 1));
  return path;
}).reverse();
const multiNormalized = normalizeSlideImagePaths(multiSlideDir, shuffledPaths);
assert.deepEqual(
  multiNormalized.map((path) => path.split(/[\\/]/).pop()),
  Array.from({ length: multiSlideCount }, (_, index) => `slide-${String(index + 1).padStart(2, "0")}.png`),
);

assert.throws(
  () => runLibreOfficePreviewPipeline(join(tempDir, "missing.pptx")),
  (error: unknown) => {
    assert.ok(error instanceof LibreOfficePipelineError);
    assert.match(error.message, /PPTX input file not found/);
    return true;
  },
);

process.stdout.write("AT-9 renderer unit checks passed\n");
