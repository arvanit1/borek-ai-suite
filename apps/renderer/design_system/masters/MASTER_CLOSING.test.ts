/** AT-18 unit checks executed by pytest via `npm run test:at18 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import { BorekBranding, BorekSlide } from "../tokens/branding.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekSpacing } from "../tokens/spacing.js";
import {
  MASTER_CLOSING_CHECKLIST_PLACEHOLDER,
  MASTER_CLOSING_LABEL_PLACEHOLDER,
  MASTER_CLOSING_LAYOUT_IDS,
  MASTER_CLOSING_NAME,
  MASTER_CLOSING_STEPS_PLACEHOLDER,
  MASTER_CLOSING_TITLE_PLACEHOLDER,
  computeMasterClosingLayout,
  registerMasterClosing,
} from "./MASTER_CLOSING.js";

const EMU_PER_INCH = 914_400;

function inchesToEmu(inches: number): number {
  return Math.round(inches * EMU_PER_INCH);
}

const MASTER_TS = join(
  fileURLToPath(new URL(".", import.meta.url)),
  "MASTER_CLOSING.ts",
);

const REPO_ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..", "..");
const LAYOUT_REGISTRY_PATH = join(REPO_ROOT, "packages", "contracts", "layout_registry.json");

const layout = computeMasterClosingLayout();
const { marginX, marginTop, footerHeight } = BorekSpacing;
const { columnGap, rowGap } = BorekGrid;
const contentWidth = BorekSlide.widthInches - marginX * 2;

const sectionLabelY = marginTop + BorekBranding.logo.height + rowGap;
const sectionLabelH = footerHeight;
const slideTitleY = sectionLabelY + sectionLabelH + rowGap;
const slideTitleH = marginTop * 2;
const contentTopY = slideTitleY + slideTitleH + rowGap;
const contentBottom = BorekSlide.heightInches - footerHeight - rowGap;
const contentAreaH = contentBottom - contentTopY;
const columnW = (contentWidth - columnGap) / 2;

assert.ok(existsSync(MASTER_TS), "MASTER_CLOSING.ts must exist");
assert.equal(MASTER_CLOSING_NAME, "MASTER_CLOSING");
assert.equal(MASTER_CLOSING_LABEL_PLACEHOLDER, "sectionLabel");
assert.equal(MASTER_CLOSING_TITLE_PLACEHOLDER, "slideTitle");
assert.equal(MASTER_CLOSING_CHECKLIST_PLACEHOLDER, "closingChecklist");
assert.equal(MASTER_CLOSING_STEPS_PLACEHOLDER, "closingSteps");

assert.equal(layout.sectionLabel.x, marginX);
assert.equal(layout.sectionLabel.y, sectionLabelY);
assert.equal(layout.sectionLabel.h, sectionLabelH);
assert.equal(layout.sectionLabel.w, contentWidth);

assert.equal(layout.slideTitle.y, slideTitleY);
assert.equal(layout.slideTitle.h, slideTitleH);
assert.equal(layout.contentTopY, contentTopY);

assert.equal(layout.checklist.x, marginX);
assert.equal(layout.checklist.y, contentTopY);
assert.equal(layout.checklist.w, columnW);
assert.equal(layout.checklist.h, contentAreaH);

assert.equal(layout.steps.x, marginX + columnW + columnGap);
assert.equal(layout.steps.y, contentTopY);
assert.equal(layout.steps.w, columnW);
assert.equal(layout.steps.h, contentAreaH);

const registry = JSON.parse(readFileSync(LAYOUT_REGISTRY_PATH, "utf8")) as {
  layouts: Record<string, { category: string }>;
};
const closingLayoutIds = Object.entries(registry.layouts)
  .filter(([, meta]) => meta.category === "closing")
  .map(([layoutId]) => layoutId)
  .sort();

assert.deepEqual(
  [...MASTER_CLOSING_LAYOUT_IDS].sort(),
  closingLayoutIds,
  "MASTER_CLOSING must cover every closing-category layout in layout_registry.json",
);
assert.deepEqual(MASTER_CLOSING_LAYOUT_IDS, ["NEXT_STEPS_01"]);

const pptx = new PptxGenJS();
registerMasterClosing(pptx);
pptx.addSlide({ masterName: MASTER_CLOSING_NAME });

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));
assert.ok(buffer.byteLength > 1_000, "MASTER_CLOSING deck must produce a non-trivial pptx buffer");

const zip = await JSZip.loadAsync(buffer);
const layoutXmlPaths = Object.keys(zip.files).filter((path) => /ppt\/slideLayouts\/slideLayout\d+\.xml$/.test(path));
assert.ok(layoutXmlPaths.length >= 1, "pptx must contain slide layouts");

let closingLayoutXml: string | undefined;
for (const path of layoutXmlPaths) {
  const xml = await zip.file(path)?.async("string");
  if (xml?.includes(`name="${MASTER_CLOSING_NAME}"`)) {
    closingLayoutXml = xml;
    break;
  }
}

assert.ok(closingLayoutXml, "pptx must contain a slide layout named MASTER_CLOSING");
assert.match(
  closingLayoutXml,
  new RegExp(`<a:srgbClr val="${BorekColors.coverBackground}"/>|<a:srgbClr val="${BorekColors.coverBackground}"`),
  "closing master background must use BorekColors.coverBackground (dark variant)",
);

assert.match(closingLayoutXml, /type="body"/, "closing body placeholders must be present");
assert.match(closingLayoutXml, /type="sldNum"/i, "page-number placeholder must be present on closing master");
assert.match(closingLayoutXml, /idx="100"/, "logo placeholder region must be registered on the closing master");

const titleCount = (closingLayoutXml.match(/type="title"/g) ?? []).length;
assert.equal(titleCount, 0, "closing master must not use title-type placeholders");

const bodyCount = (closingLayoutXml.match(/type="body"/g) ?? []).length;
assert.equal(
  bodyCount,
  5,
  "closing master must define section label, slide title, checklist, steps, and footer body placeholders",
);

assert.match(
  closingLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.branding.footer.x)}" y="${inchesToEmu(layout.branding.footer.y)}"`),
  "footer placeholder x/y must follow BorekBranding tokens",
);
assert.match(
  closingLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.checklist.x)}" y="${inchesToEmu(layout.checklist.y)}"`),
  "checklist placeholder x/y must follow closing layout tokens",
);
assert.match(
  closingLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.steps.x)}" y="${inchesToEmu(layout.steps.y)}"`),
  "steps placeholder x/y must follow closing layout tokens",
);

assert.ok(
  !/subtitle|statBadge|coverTitle/i.test(closingLayoutXml),
  "closing master must not define cover/subtitle/stat regions",
);

process.stdout.write("AT-18 renderer unit checks passed\n");
