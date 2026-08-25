/** AT-16 unit checks executed by pytest via `npm run test:at16 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import { BorekBranding, BorekSlide } from "../tokens/branding.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekSpacing } from "../tokens/spacing.js";
import {
  MASTER_SECTION_LABEL_PLACEHOLDER,
  MASTER_SECTION_NAME,
  MASTER_SECTION_TITLE_PLACEHOLDER,
  computeMasterSectionLayout,
  registerMasterSection,
} from "./MASTER_SECTION.js";

const EMU_PER_INCH = 914_400;

function inchesToEmu(inches: number): number {
  return Math.round(inches * EMU_PER_INCH);
}

const MASTER_TS = join(
  fileURLToPath(new URL(".", import.meta.url)),
  "MASTER_SECTION.ts",
);

const layout = computeMasterSectionLayout();
const { marginX, marginTop, footerHeight } = BorekSpacing;
const { rowGap } = BorekGrid;
const contentWidth = BorekSlide.widthInches - marginX * 2;

const contentTop = marginTop + BorekBranding.logo.height + rowGap;
const contentBottom = BorekSlide.heightInches - footerHeight - rowGap;
const sectionLabelH = footerHeight;
const labelTitleGap = marginTop;
const sectionTitleH = marginTop * 3;
const blockH = sectionLabelH + labelTitleGap + sectionTitleH;
const blockY = contentTop + (contentBottom - contentTop - blockH) / 2;

assert.ok(existsSync(MASTER_TS), "MASTER_SECTION.ts must exist");
assert.equal(MASTER_SECTION_NAME, "MASTER_SECTION");

assert.equal(layout.sectionLabel.x, marginX);
assert.equal(layout.sectionLabel.y, blockY);
assert.equal(layout.sectionLabel.h, sectionLabelH);
assert.equal(layout.sectionLabel.w, contentWidth);

assert.equal(layout.sectionTitle.y, blockY + sectionLabelH + labelTitleGap);
assert.equal(layout.sectionTitle.h, sectionTitleH);
assert.equal(layout.sectionTitle.w, contentWidth);

assert.equal(layout.branding.footer.y, BorekSlide.heightInches - footerHeight);
assert.match(layout.branding.slideNumber.format, /number/);

const pptx = new PptxGenJS();
registerMasterSection(pptx);
pptx.addSlide({ masterName: MASTER_SECTION_NAME });

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));
assert.ok(buffer.byteLength > 1_000, "MASTER_SECTION deck must produce a non-trivial pptx buffer");

const zip = await JSZip.loadAsync(buffer);
const layoutXmlPaths = Object.keys(zip.files).filter((path) => /ppt\/slideLayouts\/slideLayout\d+\.xml$/.test(path));
assert.ok(layoutXmlPaths.length >= 1, "pptx must contain slide layouts");

let sectionLayoutXml: string | undefined;
for (const path of layoutXmlPaths) {
  const xml = await zip.file(path)?.async("string");
  if (xml?.includes(`name="${MASTER_SECTION_NAME}"`)) {
    sectionLayoutXml = xml;
    break;
  }
}

assert.ok(sectionLayoutXml, "pptx must contain a slide layout named MASTER_SECTION");
assert.match(
  sectionLayoutXml,
  new RegExp(`<a:srgbClr val="${BorekColors.background}"/>|<a:srgbClr val="${BorekColors.background}"`),
  "section master background must use BorekColors.background",
);

assert.match(sectionLayoutXml, /type="body"/, "section label, title, and footer body placeholders must be present");
assert.match(sectionLayoutXml, /type="sldNum"/i, "page-number placeholder must be present on section master");
assert.match(sectionLayoutXml, /idx="100"/, "logo placeholder region must be registered on the section master");

const titleCount = (sectionLayoutXml.match(/type="title"/g) ?? []).length;
assert.equal(titleCount, 0, "section master must not use a title-type placeholder (body regions preserve left-aligned layout)");

const bodyCount = (sectionLayoutXml.match(/type="body"/g) ?? []).length;
assert.equal(bodyCount, 3, "section master must define section label, section title, and footer body placeholders");

assert.match(
  sectionLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.branding.footer.x)}" y="${inchesToEmu(layout.branding.footer.y)}"`),
  "footer placeholder x/y must follow BorekBranding tokens",
);
assert.match(
  sectionLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.sectionLabel.x)}" y="${inchesToEmu(layout.sectionLabel.y)}"`),
  "section label placeholder x/y must follow section layout tokens",
);
assert.match(
  sectionLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.sectionTitle.x)}" y="${inchesToEmu(layout.sectionTitle.y)}"`),
  "section title placeholder x/y must follow section layout tokens",
);

assert.equal(MASTER_SECTION_LABEL_PLACEHOLDER, "sectionLabel");
assert.equal(MASTER_SECTION_TITLE_PLACEHOLDER, "sectionTitle");

process.stdout.write("AT-16 renderer unit checks passed\n");
