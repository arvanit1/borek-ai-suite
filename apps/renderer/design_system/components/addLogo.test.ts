/** AT-14 logo injection checks. */

import assert from "node:assert/strict";
import { existsSync } from "node:fs";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  addLogo,
  BOREK_LOGO_ON_DARK_PATH,
  BOREK_LOGO_ON_LIGHT_PATH,
  LOGO_PLACEHOLDER,
} from "./addLogo.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
import { BorekBranding } from "../tokens/branding.js";

assert.ok(existsSync(BOREK_LOGO_ON_LIGHT_PATH), "renderer must ship logo-on-light.png");
assert.ok(existsSync(BOREK_LOGO_ON_DARK_PATH), "renderer must ship logo.png for dark slides");
assert.equal(LOGO_PLACEHOLDER, BorekBranding.logo.placeholderName);

const pptx = new PptxGenJS();
registerMasterContent(pptx);
const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
addLogo(slide);

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));

const zip = await JSZip.loadAsync(buffer);
const media = Object.keys(zip.files).filter((path) => path.startsWith("ppt/media/"));
assert.ok(media.length >= 1, "logo injection must embed at least one media file");

process.stdout.write("AT-14 logo injection checks passed\n");
