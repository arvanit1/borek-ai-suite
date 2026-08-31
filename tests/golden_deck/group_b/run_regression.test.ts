/** JJ-22: Group B golden-deck discovery, rendering, and AT-55 regression checks. */

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
import {
  compareGoldenDeck,
  compareSlidePng,
  listGoldenDeckFiles,
  readPng,
} from "../compare.js";
import { runGoldenDeckRegression } from "../run_regression.js";
import { buildGroupBGoldenDeckBuffer } from "./build_deck.js";
import {
  GROUP_B_GOLDEN_CASES,
  GROUP_B_GOLDEN_FILES,
  GROUP_B_GOLDEN_HEIGHT,
  GROUP_B_GOLDEN_WIDTH,
  buildGroupBGoldenPng,
} from "./fixtures.js";

async function main(): Promise<void> {
  const referenceDir = import.meta.dirname;
  const expectedMappings = [
    ["PROCESS_FLOW_01", "process_flow_01.png"],
    ["TIMELINE_01", "timeline_01.png"],
    ["MILESTONES_01", "milestones_01.png"],
    ["TEAM_FTE_01", "team_fte_01.png"],
  ] as const;

  assert.equal(GROUP_B_GOLDEN_CASES.length, 4);
  assert.deepEqual(
    GROUP_B_GOLDEN_CASES.map(({ layoutId, referenceFileName }) => [layoutId, referenceFileName]),
    expectedMappings,
    "all four Group B layouts must map deterministically to one golden reference",
  );
  assert.equal(new Set(GROUP_B_GOLDEN_CASES.map(({ id }) => id)).size, 4);
  assert.equal(new Set(GROUP_B_GOLDEN_CASES.map(({ layoutId }) => layoutId)).size, 4);
  assert.deepEqual(listGoldenDeckFiles(referenceDir), [...GROUP_B_GOLDEN_FILES]);

  for (const goldenCase of GROUP_B_GOLDEN_CASES) {
    assert.equal(goldenCase.spec.layoutId, goldenCase.layoutId);
    assert.match(goldenCase.sourceFixture, /\.realistic\.json$/);
    const referencePath = join(referenceDir, goldenCase.referenceFileName);
    assert.ok(readFileSync(referencePath).length > 0, `${goldenCase.id} reference must exist`);
    const reference = readPng(referencePath);
    assert.deepEqual(
      { width: reference.width, height: reference.height },
      { width: GROUP_B_GOLDEN_WIDTH, height: GROUP_B_GOLDEN_HEIGHT },
      `${goldenCase.id} must use the Group B golden canvas`,
    );
    const generated = buildGroupBGoldenPng(goldenCase.referenceFileName);
    const generatedCopy = new PNG({ width: generated.width, height: generated.height });
    generated.data.copy(generatedCopy.data);
    assert.deepEqual(
      compareSlidePng(reference, generatedCopy, 1),
      [],
      `${goldenCase.referenceFileName} must match the live layout fixture builder`,
    );
  }

  const originalSpecs = structuredClone(GROUP_B_GOLDEN_CASES.map(({ spec }) => spec));
  const deckBuffer = await buildGroupBGoldenDeckBuffer();
  assert.deepEqual(
    GROUP_B_GOLDEN_CASES.map(({ spec }) => spec),
    originalSpecs,
    "golden rendering must not mutate canonical SlideSpecs",
  );

  const zip = await JSZip.loadAsync(deckBuffer);
  const slideXmlPaths = Object.keys(zip.files)
    .filter((path) => /^ppt\/slides\/slide\d+\.xml$/.test(path))
    .sort((left, right) => slideIndex(left) - slideIndex(right));
  assert.equal(slideXmlPaths.length, 4, "production dispatcher must render four Group B slides");

  for (const [index, goldenCase] of GROUP_B_GOLDEN_CASES.entries()) {
    const slideNumber = index + 1;
    const slideXml = await zip.file(`ppt/slides/slide${slideNumber}.xml`)?.async("string");
    assert.ok(slideXml, `missing rendered slide ${slideNumber}`);
    assert.match(slideXml, new RegExp(escapeRegExp(goldenCase.spec.title)));
    await assertSlideUsesMaster(zip, slideNumber, MASTER_CONTENT_NAME);
  }

  const actualDir = mkdtempSync(join(tmpdir(), "jj22-actual-"));
  const missingReferenceDir = mkdtempSync(join(tmpdir(), "jj22-missing-reference-"));
  try {
    for (const fileName of GROUP_B_GOLDEN_FILES) {
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
      ];
      assert.equal(runGoldenDeckRegression(), 0, "Group B must pass through the AT-55 runner");
    } finally {
      process.argv = originalArgv;
    }

    assert.throws(
      () => compareGoldenDeck(missingReferenceDir, actualDir, [...GROUP_B_GOLDEN_FILES]),
      /ENOENT|no such file/i,
      "missing approved references must remain a hard failure",
    );

    const changedPath = join(actualDir, GROUP_B_GOLDEN_FILES[0]!);
    const changed = readPng(changedPath);
    recolorPixel(changed, 0, 0);
    writeFileSync(changedPath, PNG.sync.write(changed));
    const failed = compareGoldenDeck(referenceDir, actualDir, [...GROUP_B_GOLDEN_FILES]);
    assert.equal(failed.status, "FAIL", "visual regressions must surface as failures");
    assert.ok(failed.diffs.some(({ category }) => category === "color"));
  } finally {
    rmSync(actualDir, { recursive: true, force: true });
    rmSync(missingReferenceDir, { recursive: true, force: true });
  }

  process.stdout.write("JJ-22 Group B golden-deck checks passed\n");
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
