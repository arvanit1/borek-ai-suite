/** AT-14 unit checks executed by pytest via `npm run test:at14 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  BorekBranding,
  BorekSlide,
  computeBrandingLayout,
} from "../tokens/branding.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekSpacing } from "../tokens/spacing.js";
import { BorekTypography } from "../tokens/typography.js";
import {
  MASTER_DEFAULT_FOOTER_PLACEHOLDER,
  MASTER_DEFAULT_LOGO_PLACEHOLDER,
  MASTER_DEFAULT_NAME,
  registerMasterDefault,
} from "./MASTER_DEFAULT.js";

const EMU_PER_INCH = 914_400;

function inchesToEmu(inches: number): number {
  return Math.round(inches * EMU_PER_INCH);
}

const MASTER_TS = join(
  fileURLToPath(new URL(".", import.meta.url)),
  "MASTER_DEFAULT.ts",
);

const layout = computeBrandingLayout();

assert.ok(existsSync(MASTER_TS), "MASTER_DEFAULT.ts must exist");

assert.equal(MASTER_DEFAULT_NAME, "MASTER_DEFAULT");
assert.equal(MASTER_DEFAULT_LOGO_PLACEHOLDER, BorekBranding.logo.placeholderName);
assert.equal(MASTER_DEFAULT_FOOTER_PLACEHOLDER, BorekBranding.footer.placeholderName);

assert.equal(BorekSlide.widthInches, 13.333);
assert.equal(BorekSlide.heightInches, 7.5);

assert.equal(layout.logo.x, BorekSpacing.marginX);
assert.equal(layout.logo.y, BorekSpacing.marginTop);
assert.equal(layout.logo.w, BorekSpacing.marginX * 2);
assert.equal(layout.logo.h, BorekSpacing.footerHeight);

assert.equal(layout.footer.x, BorekSpacing.marginX);
assert.equal(layout.footer.y, BorekSlide.heightInches - BorekSpacing.footerHeight);
assert.equal(layout.footer.h, BorekSpacing.footerHeight);
assert.equal(
  layout.footer.w,
  BorekSlide.widthInches - BorekSpacing.marginX * 2 - BorekSpacing.marginX,
);

assert.equal(layout.slideNumber.y, layout.footer.y);
assert.equal(layout.slideNumber.h, BorekSpacing.footerHeight);
assert.equal(layout.slideNumber.color, BorekColors.mutedText);
assert.equal(layout.slideNumber.fontFace, BorekTypography.fonts.body);
assert.equal(layout.slideNumber.fontSize, BorekTypography.defaultSizes.body);
assert.equal(layout.slideNumber.align, "right");
assert.equal(layout.slideNumber.format, "number");

const pptx = new PptxGenJS();
registerMasterDefault(pptx);
pptx.addSlide({ masterName: MASTER_DEFAULT_NAME });

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));
assert.ok(buffer.byteLength > 1_000, "MASTER_DEFAULT deck must produce a non-trivial pptx buffer");

const zip = await JSZip.loadAsync(buffer);
const layoutXmlPaths = Object.keys(zip.files).filter((path) => /ppt\/slideLayouts\/slideLayout\d+\.xml$/.test(path));
assert.ok(layoutXmlPaths.length >= 1, "pptx must contain slide layouts");

let masterLayoutXml: string | undefined;
for (const path of layoutXmlPaths) {
  const xml = await zip.file(path)?.async("string");
  if (xml?.includes(`name="${MASTER_DEFAULT_NAME}"`)) {
    masterLayoutXml = xml;
    break;
  }
}

assert.ok(masterLayoutXml, "pptx must contain a slide layout named MASTER_DEFAULT");

assert.match(masterLayoutXml, /type="body"/, "footer placeholder must be a body placeholder");
assert.match(masterLayoutXml, /type="sldNum"/i, "page-number placeholder must be present");
assert.match(masterLayoutXml, /idx="100"/, "logo placeholder region must be registered on the master layout");

assert.match(
  masterLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.logo.x)}" y="${inchesToEmu(layout.logo.y)}"`),
  "logo placeholder x/y must follow branding tokens",
);
assert.match(
  masterLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.footer.x)}" y="${inchesToEmu(layout.footer.y)}"`),
  "footer placeholder x/y must follow branding tokens",
);
assert.match(
  masterLayoutXml,
  new RegExp(`<a:ext cx="${inchesToEmu(layout.footer.w)}" cy="${inchesToEmu(layout.footer.h)}"`),
  "footer placeholder size must follow branding tokens",
);
assert.match(masterLayoutXml, new RegExp(`val="${BorekColors.mutedText}"`), "footer uses mutedText color token");
assert.match(masterLayoutXml, new RegExp(`typeface="${BorekTypography.fonts.body}"`), "footer uses body font token");

process.stdout.write("AT-14 renderer unit checks passed\n");
