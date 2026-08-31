#!/usr/bin/env node
/** MS-23: build the five-slide Group C golden deck through the production dispatcher. */

import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import PptxGenJS from "pptxgenjs";

import { registerMasterClosing } from "../../../apps/renderer/design_system/masters/MASTER_CLOSING.js";
import { registerMasterContent } from "../../../apps/renderer/design_system/masters/MASTER_CONTENT.js";
import { dispatchSlide } from "../../../apps/renderer/layouts/dispatcher.js";
import { GROUP_C_GOLDEN_CASES } from "./fixtures.js";

export async function buildGroupCGoldenDeckBuffer(): Promise<Buffer> {
  const pptx = new PptxGenJS();
  registerMasterContent(pptx);
  registerMasterClosing(pptx);

  for (const goldenCase of GROUP_C_GOLDEN_CASES) {
    dispatchSlide(pptx, goldenCase.spec);
  }

  const output = await pptx.write({ outputType: "nodebuffer" });
  if (!Buffer.isBuffer(output)) {
    throw new Error("Group C golden deck did not produce a PPTX buffer");
  }
  return output;
}

async function main(): Promise<void> {
  const outputPath = process.argv[2];
  if (!outputPath) {
    throw new Error("Usage: build_deck.ts <output.pptx>");
  }
  writeFileSync(resolve(outputPath), await buildGroupCGoldenDeckBuffer());
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) {
  main().catch((error: unknown) => {
    console.error(error);
    process.exitCode = 1;
  });
}
