import PptxGenJS from "pptxgenjs";

import { registerMasterClosing } from "./design_system/masters/MASTER_CLOSING.js";
import { registerMasterContent } from "./design_system/masters/MASTER_CONTENT.js";
import { registerMasterCover } from "./design_system/masters/MASTER_COVER.js";
import { dispatchSlide } from "./layouts/dispatcher.js";
import type { SlideSpecBase } from "./src/contracts.js";

export const UNIMPLEMENTED_LAYOUT_IDS = new Set(["EXECUTIVE_SUMMARY_01"]);

export async function buildDeckBuffer(slideSpecs: readonly SlideSpecBase[]): Promise<Buffer> {
  if (slideSpecs.length === 0) {
    throw new Error("At least one SlideSpec is required");
  }

  const pptx = new PptxGenJS();
  registerMasterCover(pptx);
  registerMasterContent(pptx);
  registerMasterClosing(pptx);

  for (const spec of slideSpecs) {
    if (UNIMPLEMENTED_LAYOUT_IDS.has(spec.layoutId)) {
      throw new Error(`Layout ${spec.layoutId} has no implemented renderer`);
    }
    dispatchSlide(pptx, spec);
  }

  const output = await pptx.write({ outputType: "nodebuffer" });
  if (!Buffer.isBuffer(output)) {
    throw new Error("PptxGenJS did not produce a PPTX buffer");
  }
  return output;
}
