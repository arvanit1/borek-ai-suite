/** JJ-23: EXECUTIVE_SUMMARY_01 golden-deck discovery, rendering, and AT-55 regression checks. */

import assert from "node:assert/strict";
import {
  copyFileSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import JSZip from "jszip";
import { PNG } from "pngjs";

import { MASTER_CONTENT_NAME } from "../../../apps/renderer/design_system/masters/MASTER_CONTENT.js";
import { compareGoldenDeck, compareSlidePng, readPng } from "../compare.js";
import { runGoldenDeckRegression } from "../run_regression.js";
import { buildSummaryGoldenDeckBuffer } from "./build_deck.js";
import {
  SUMMARY_GOLDEN_CASE,
  SUMMARY_GOLDEN_FILE,
  SUMMARY_GOLDEN_HEIGHT,
  SUMMARY_GOLDEN_WIDTH,
  buildExecutiveSummary01Png,
} from "./fixtures.js";

async function main(): Promise<void> {
  const referenceDir = import.meta.dirname;
  assert.equal(SUMMARY_GOLDEN_CASE.layoutId, "EXECUTIVE_SUMMARY_01");
  assert.match(SUMMARY_GOLDEN_CASE.sourceFixture, /\.realistic\.json$/);
  const referencePath = join(referenceDir, SUMMARY_GOLDEN_FILE);
  assert.ok(readFileSync(referencePath).length > 0, "executive summary reference must exist");
  const reference = readPng(referencePath);
  assert.deepEqual(
    { width: reference.width, height: reference.height },
    { width: SUMMARY_GOLDEN_WIDTH, height: SUMMARY_GOLDEN_HEIGHT },
  );
  const generated = buildExecutiveSummary01Png();
  const generatedCopy = new PNG({ width: generated.width, height: generated.height });
  generated.data.copy(generatedCopy.data);
  assert.deepEqual(
    compareSlidePng(reference, generatedCopy, 1),
    [],
    `${SUMMARY_GOLDEN_FILE} must match the live layout fixture builder`,
  );

  const originalSpec = structuredClone(SUMMARY_GOLDEN_CASE.spec);
  const deckBuffer = await buildSummaryGoldenDeckBuffer();
  assert.deepEqual(SUMMARY_GOLDEN_CASE.spec, originalSpec, "golden rendering must not mutate SlideSpec");

  const zip = await JSZip.loadAsync(deckBuffer);
  const slideXml = await zip.file("ppt/slides/slide1.xml")?.async("string");
  assert.ok(slideXml);
  assert.match(slideXml, new RegExp(escapeRegExp(SUMMARY_GOLDEN_CASE.spec.title)));
  await assertSlideUsesMaster(zip, MASTER_CONTENT_NAME);

  const actualDir = mkdtempSync(join(tmpdir(), "jj23-actual-"));
  const missingReferenceDir = mkdtempSync(join(tmpdir(), "jj23-missing-reference-"));
  try {
    copyFileSync(referencePath, join(actualDir, SUMMARY_GOLDEN_FILE));
    const originalArgv = process.argv;
    try {
      process.argv = [
        originalArgv[0]!,
        originalArgv[1]!,
        "--actual",
        actualDir,
        "--reference",
        referenceDir,
      ];
      assert.equal(runGoldenDeckRegression(), 0, "EXECUTIVE_SUMMARY_01 must pass through the AT-55 runner");
    } finally {
      process.argv = originalArgv;
    }

    assert.throws(
      () => compareGoldenDeck(missingReferenceDir, actualDir, [SUMMARY_GOLDEN_FILE]),
      /ENOENT|no such file/i,
    );

    const changedPath = join(actualDir, SUMMARY_GOLDEN_FILE);
    const changed = readPng(changedPath);
    const offset = 0;
    changed.data[offset] = (changed.data[offset] ?? 0) > 127 ? 0 : 255;
    changed.data[offset + 1] = (changed.data[offset + 1] ?? 0) > 127 ? 0 : 255;
    changed.data[offset + 2] = (changed.data[offset + 2] ?? 0) > 127 ? 0 : 255;
    changed.data[offset + 3] = 255;
    writeFileSync(changedPath, PNG.sync.write(changed));
    const failed = compareGoldenDeck(referenceDir, actualDir, [SUMMARY_GOLDEN_FILE]);
    assert.equal(failed.status, "FAIL");
    assert.ok(failed.diffs.some(({ category }) => category === "color"));
  } finally {
    rmSync(actualDir, { recursive: true, force: true });
    rmSync(missingReferenceDir, { recursive: true, force: true });
  }

  process.stdout.write("JJ-23 EXECUTIVE_SUMMARY_01 golden-deck checks passed\n");
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});

async function assertSlideUsesMaster(zipFile: JSZip, expectedMasterName: string): Promise<void> {
  const rels = await zipFile.file("ppt/slides/_rels/slide1.xml.rels")?.async("string");
  assert.ok(rels, "slide must have relationships");
  const target = rels.match(/Type="[^"]*\/slideLayout" Target="([^"]+)"/)?.[1];
  assert.ok(target, "slide must reference a layout");
  const layoutPath = `ppt/${target.replace(/^\.\.\//, "")}`;
  const layoutXml = await zipFile.file(layoutPath)?.async("string");
  assert.ok(layoutXml, "slide layout must exist");
  assert.match(layoutXml, new RegExp(`name="${expectedMasterName}"`));
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
