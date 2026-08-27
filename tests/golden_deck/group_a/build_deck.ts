#!/usr/bin/env node
/** BT-24: build the five-slide Group A golden deck through the production dispatcher. */

import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import PptxGenJS from "pptxgenjs";

import { registerMasterContent } from "../../../apps/renderer/design_system/masters/MASTER_CONTENT.js";
import { registerMasterCover } from "../../../apps/renderer/design_system/masters/MASTER_COVER.js";
import { dispatchSlide } from "../../../apps/renderer/layouts/dispatcher.js";
import { GROUP_A_GOLDEN_CASES } from "./fixtures.js";

export async function buildGroupAGoldenDeckBuffer(): Promise<Buffer> {
  const pptx = new PptxGenJS();
  registerMasterCover(pptx);
  registerMasterContent(pptx);

  for (const goldenCase of GROUP_A_GOLDEN_CASES) {
    dispatchSlide(pptx, goldenCase.spec);
  }

  const output = await pptx.write({ outputType: "nodebuffer" });
  if (!Buffer.isBuffer(output)) {
    throw new Error("Group A golden deck did not produce a PPTX buffer");
  }
  return output;
}

async function main(): Promise<void> {
  const outputPath = process.argv[2];
  if (!outputPath) {
    throw new Error("Usage: build_deck.ts <output.pptx>");
  }
  writeFileSync(resolve(outputPath), await buildGroupAGoldenDeckBuffer());
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  main().catch((error: unknown) => {
    console.error(error);
    process.exitCode = 1;
  });
}
