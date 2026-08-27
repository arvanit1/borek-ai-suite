/** BT-24: Group A golden-deck discovery, rendering, and AT-55 regression checks. */

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
import { MASTER_COVER_NAME } from "../../../apps/renderer/design_system/masters/MASTER_COVER.js";
import {
  compareGoldenDeck,
  listReferenceSlideFiles,
  readPng,
} from "../compare.js";
import { runGoldenDeckRegression } from "../run_regression.js";
import { buildGroupAGoldenDeckBuffer } from "./build_deck.js";
import { GROUP_A_GOLDEN_CASES } from "./fixtures.js";

async function main(): Promise<void> {
  const referenceDir = import.meta.dirname;
  const expectedMappings = [
    ["COVER_01", "slide-01.png"],
    ["CONTEXT_01", "slide-02.png"],
    ["PROBLEM_SOLUTION_01", "slide-03.png"],
    ["SCOPE_01", "slide-04.png"],
    ["REQUIREMENTS_MATRIX_01", "slide-05.png"],
  ] as const;
  const expectedReferenceFiles = expectedMappings.map(([, fileName]) => fileName);

  assert.equal(GROUP_A_GOLDEN_CASES.length, 5);
  assert.deepEqual(
    GROUP_A_GOLDEN_CASES.map(({ layoutId, referenceFileName }) => [layoutId, referenceFileName]),
    expectedMappings,
    "all five Group A layouts must map deterministically to one golden reference",
  );
  assert.equal(new Set(GROUP_A_GOLDEN_CASES.map(({ id }) => id)).size, 5);
  assert.equal(new Set(GROUP_A_GOLDEN_CASES.map(({ layoutId }) => layoutId)).size, 5);
  assert.deepEqual(listReferenceSlideFiles(referenceDir, 5), expectedReferenceFiles);

  for (const goldenCase of GROUP_A_GOLDEN_CASES) {
    assert.equal(goldenCase.spec.layoutId, goldenCase.layoutId);
    assert.match(goldenCase.sourceFixture, /\.realistic\.json$/);
    const referencePath = join(referenceDir, goldenCase.referenceFileName);
    assert.ok(readFileSync(referencePath).length > 0, `${goldenCase.id} reference must exist`);
    const reference = readPng(referencePath);
    assert.deepEqual(
      { width: reference.width, height: reference.height },
      { width: 2001, height: 1125 },
      `${goldenCase.id} must use the AT-9 150 DPI wide-slide canvas`,
    );
  }

  const originalSpecs = structuredClone(GROUP_A_GOLDEN_CASES.map(({ spec }) => spec));
  const deckBuffer = await buildGroupAGoldenDeckBuffer();
  assert.deepEqual(
    GROUP_A_GOLDEN_CASES.map(({ spec }) => spec),
    originalSpecs,
    "golden rendering must not mutate canonical SlideSpecs",
  );

  const zip = await JSZip.loadAsync(deckBuffer);
  const slideXmlPaths = Object.keys(zip.files)
    .filter((path) => /^ppt\/slides\/slide\d+\.xml$/.test(path))
    .sort((left, right) => slideIndex(left) - slideIndex(right));
  assert.equal(slideXmlPaths.length, 5, "production dispatcher must render five Group A slides");

  for (const [index, goldenCase] of GROUP_A_GOLDEN_CASES.entries()) {
    const slideNumber = index + 1;
    const slideXml = await zip.file(`ppt/slides/slide${slideNumber}.xml`)?.async("string");
    assert.ok(slideXml, `missing rendered slide ${slideNumber}`);
    assert.match(slideXml, new RegExp(escapeRegExp(goldenCase.spec.title)));
    await assertSlideUsesMaster(
      zip,
      slideNumber,
      goldenCase.layoutId === "COVER_01" ? MASTER_COVER_NAME : MASTER_CONTENT_NAME,
    );
  }

  const actualDir = mkdtempSync(join(tmpdir(), "bt24-actual-"));
  const missingReferenceDir = mkdtempSync(join(tmpdir(), "bt24-missing-reference-"));
  try {
    for (const fileName of expectedReferenceFiles) {
      copyFileSync(join(referenceDir, fileName), join(actualDir, fileName));
    }

    const originalArgv = process.argv;
    try {
      process.argv = [
        originalArgv[0]!,
        originalArgv[1]!,
        "--actual",
        actualDir,
        "--reference",
        referenceDir,
        "--expected-count",
        "5",
      ];
      assert.equal(runGoldenDeckRegression(), 0, "Group A must pass through the AT-55 runner");
    } finally {
      process.argv = originalArgv;
    }

    assert.throws(
      () => compareGoldenDeck(missingReferenceDir, actualDir, expectedReferenceFiles),
      /ENOENT|no such file/i,
      "missing approved references must remain a hard failure",
    );

    const changedPath = join(actualDir, expectedReferenceFiles[0]!);
    const changed = readPng(changedPath);
    recolorPixel(changed, 0, 0);
    writeFileSync(changedPath, PNG.sync.write(changed));
    const failed = compareGoldenDeck(referenceDir, actualDir, expectedReferenceFiles);
    assert.equal(failed.status, "FAIL", "visual regressions must surface as failures");
    assert.ok(failed.diffs.some(({ category }) => category === "color"));
  } finally {
    rmSync(actualDir, { recursive: true, force: true });
    rmSync(missingReferenceDir, { recursive: true, force: true });
  }

  process.stdout.write("BT-24 Group A golden-deck checks passed\n");
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});

function slideIndex(path: string): number {
  return Number.parseInt(path.match(/slide(\d+)\.xml$/)?.[1] ?? "0", 10);
}

async function assertSlideUsesMaster(
  zipFile: JSZip,
  slideNumber: number,
  expectedMasterName: string,
): Promise<void> {
  const rels = await zipFile
    .file(`ppt/slides/_rels/slide${slideNumber}.xml.rels`)
    ?.async("string");
  assert.ok(rels, `slide ${slideNumber} must have relationships`);
  const target = rels.match(/Type="[^"]*\/slideLayout" Target="([^"]+)"/)?.[1];
  assert.ok(target, `slide ${slideNumber} must reference a layout`);
  const layoutPath = `ppt/${target.replace(/^\.\.\//, "")}`;
  const layoutXml = await zipFile.file(layoutPath)?.async("string");
  assert.ok(layoutXml, `slide ${slideNumber} layout must exist`);
  assert.match(layoutXml, new RegExp(`name="${expectedMasterName}"`));
}

function recolorPixel(png: PNG, x: number, y: number): void {
  const offset = (y * png.width + x) * 4;
  png.data[offset] = (png.data[offset] ?? 0) > 127 ? 0 : 255;
  png.data[offset + 1] = (png.data[offset + 1] ?? 0) > 127 ? 0 : 255;
  png.data[offset + 2] = (png.data[offset + 2] ?? 0) > 127 ? 0 : 255;
  png.data[offset + 3] = 255;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
