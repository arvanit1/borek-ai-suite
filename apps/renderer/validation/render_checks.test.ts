/** AT-10 unit checks executed by pytest via `npm run test:at10 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { PNG } from "pngjs";

import type { PresentationPlan } from "../src/contracts.js";
import type { LibreOfficePreviewResult } from "./libreoffice_pipeline.js";
import {
  isBlankSlideImage,
  parseSlideImageNumber,
  runRenderChecks,
} from "./render_checks.js";

const PLAN_WITH_THREE_SLIDES: PresentationPlan = {
  schema_version: "1.0",
  title: "Test deck",
  slides: [
    {
      order: 1,
      purpose: "cover",
      layoutId: "COVER_01",
      frameworkReferences: ["opportunity"],
    },
    {
      order: 2,
      purpose: "context",
      layoutId: "CONTEXT_01",
      frameworkReferences: ["chapter_1"],
    },
    {
      order: 3,
      purpose: "scope",
      layoutId: "SCOPE_01",
      frameworkReferences: ["chapter_3"],
    },
  ],
};

function writePng(path: string, fill: [number, number, number, number]): void {
  const png = new PNG({ width: 8, height: 8 });
  for (let offset = 0; offset < png.data.length; offset += 4) {
    png.data[offset] = fill[0];
    png.data[offset + 1] = fill[1];
    png.data[offset + 2] = fill[2];
    png.data[offset + 3] = fill[3];
  }
  writeFileSync(path, PNG.sync.write(png));
}

const tempDir = mkdtempSync(join(tmpdir(), "at10-checks-"));
const pdfPath = join(tempDir, "deck.pdf");
const slideOne = join(tempDir, "slide-01.png");
const slideTwo = join(tempDir, "slide-02.png");
const slideThree = join(tempDir, "slide-03.png");

writeFileSync(pdfPath, "%PDF-1.4 test");
writePng(slideOne, [20, 40, 200, 255]);
writePng(slideTwo, [30, 90, 120, 255]);
writePng(slideThree, [10, 10, 10, 255]);

const validPreview: LibreOfficePreviewResult = {
  pdfPath,
  slideImagePaths: [slideOne, slideTwo, slideThree],
};

assert.equal(parseSlideImageNumber(slideTwo), 2);
assert.equal(isBlankSlideImage(slideOne), false);

assert.equal(runRenderChecks({ presentationPlan: PLAN_WITH_THREE_SLIDES, preview: validPreview }).status, "VALID");

const blankSlide = join(tempDir, "slide-02.png");
writePng(blankSlide, [255, 255, 255, 255]);
assert.equal(isBlankSlideImage(blankSlide), true);

const wrongCount = runRenderChecks({
  presentationPlan: PLAN_WITH_THREE_SLIDES,
  preview: { pdfPath, slideImagePaths: [slideOne, slideTwo] },
});
assert.equal(wrongCount.status, "VALIDATION_FAILED");
assert.ok(wrongCount.issues.some((issue) => issue.code === "SLIDE_COUNT_MISMATCH"));

const blankResult = runRenderChecks({
  presentationPlan: PLAN_WITH_THREE_SLIDES,
  preview: { pdfPath, slideImagePaths: [slideOne, blankSlide, slideThree] },
});
assert.equal(blankResult.status, "VALIDATION_FAILED");
assert.ok(blankResult.issues.some((issue) => issue.code === "BLANK_SLIDE"));

const renderException = runRenderChecks({
  presentationPlan: PLAN_WITH_THREE_SLIDES,
  preview: null,
  renderError: "LibreOffice failed",
});
assert.equal(renderException.status, "VALIDATION_FAILED");
assert.ok(renderException.issues.some((issue) => issue.code === "RENDER_EXCEPTION"));

process.stdout.write("AT-10 renderer unit checks passed\n");
