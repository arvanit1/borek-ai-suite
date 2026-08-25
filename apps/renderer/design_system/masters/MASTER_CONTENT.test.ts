/** AT-17 unit checks executed by pytest via `npm run test:at17 --workspace borek-renderer`. */

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
  MASTER_CONTENT_LABEL_PLACEHOLDER,
  MASTER_CONTENT_LAYOUT_IDS,
  MASTER_CONTENT_NAME,
  MASTER_CONTENT_TITLE_PLACEHOLDER,
  MVP_LAYOUT_COUNT,
  computeMasterContentLayout,
  registerMasterContent,
} from "./MASTER_CONTENT.js";

const EMU_PER_INCH = 914_400;

function inchesToEmu(inches: number): number {
  return Math.round(inches * EMU_PER_INCH);
}

const MASTER_TS = join(
  fileURLToPath(new URL(".", import.meta.url)),
  "MASTER_CONTENT.ts",
);

const REPO_ROOT = join(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..", "..");
const LAYOUT_REGISTRY_PATH = join(REPO_ROOT, "packages", "contracts", "layout_registry.json");

const layout = computeMasterContentLayout();
const { marginX, marginTop, footerHeight } = BorekSpacing;
const { rowGap } = BorekGrid;
const contentWidth = BorekSlide.widthInches - marginX * 2;

const sectionLabelY = marginTop + BorekBranding.logo.height + rowGap;
const sectionLabelH = footerHeight;
const slideTitleY = sectionLabelY + sectionLabelH + rowGap;
const slideTitleH = marginTop * 2;
const contentTopY = slideTitleY + slideTitleH + rowGap;

assert.ok(existsSync(MASTER_TS), "MASTER_CONTENT.ts must exist");
assert.equal(MASTER_CONTENT_NAME, "MASTER_CONTENT");
assert.equal(MASTER_CONTENT_LABEL_PLACEHOLDER, "sectionLabel");
assert.equal(MASTER_CONTENT_TITLE_PLACEHOLDER, "slideTitle");

assert.equal(layout.sectionLabel.x, marginX);
assert.equal(layout.sectionLabel.y, sectionLabelY);
assert.equal(layout.sectionLabel.h, sectionLabelH);
assert.equal(layout.sectionLabel.w, contentWidth);

assert.equal(layout.slideTitle.y, slideTitleY);
assert.equal(layout.slideTitle.h, slideTitleH);
assert.equal(layout.slideTitle.w, contentWidth);
assert.equal(layout.contentTopY, contentTopY);

assert.ok(
  MASTER_CONTENT_LAYOUT_IDS.length > MVP_LAYOUT_COUNT / 2,
  "MASTER_CONTENT must be designated for a majority of MVP layouts",
);
assert.equal(MASTER_CONTENT_LAYOUT_IDS.length, 13);

const registry = JSON.parse(readFileSync(LAYOUT_REGISTRY_PATH, "utf8")) as {
  layouts: Record<string, unknown>;
};
const registryLayoutIds = Object.keys(registry.layouts).sort();
const expectedContentLayoutIds = registryLayoutIds
  .filter((layoutId) => layoutId !== "COVER_01" && layoutId !== "NEXT_STEPS_01")
  .sort();

assert.deepEqual(
  [...MASTER_CONTENT_LAYOUT_IDS].sort(),
  expectedContentLayoutIds,
  "MASTER_CONTENT must cover every MVP layout except cover and closing masters",
);

for (const layoutId of MASTER_CONTENT_LAYOUT_IDS) {
  assert.ok(registryLayoutIds.includes(layoutId), `layout registry must include ${layoutId}`);
}
assert.ok(!MASTER_CONTENT_LAYOUT_IDS.includes("COVER_01" as never));
assert.ok(!MASTER_CONTENT_LAYOUT_IDS.includes("NEXT_STEPS_01" as never));

const pptx = new PptxGenJS();
registerMasterContent(pptx);
pptx.addSlide({ masterName: MASTER_CONTENT_NAME });

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));
assert.ok(buffer.byteLength > 1_000, "MASTER_CONTENT deck must produce a non-trivial pptx buffer");

const zip = await JSZip.loadAsync(buffer);
const layoutXmlPaths = Object.keys(zip.files).filter((path) => /ppt\/slideLayouts\/slideLayout\d+\.xml$/.test(path));
assert.ok(layoutXmlPaths.length >= 1, "pptx must contain slide layouts");

let contentLayoutXml: string | undefined;
for (const path of layoutXmlPaths) {
  const xml = await zip.file(path)?.async("string");
  if (xml?.includes(`name="${MASTER_CONTENT_NAME}"`)) {
    contentLayoutXml = xml;
    break;
  }
}

assert.ok(contentLayoutXml, "pptx must contain a slide layout named MASTER_CONTENT");
assert.match(
  contentLayoutXml,
  new RegExp(`<a:srgbClr val="${BorekColors.background}"/>|<a:srgbClr val="${BorekColors.background}"`),
  "content master background must use BorekColors.background",
);

assert.match(contentLayoutXml, /type="body"/, "content label, title, and footer body placeholders must be present");
assert.match(contentLayoutXml, /type="sldNum"/i, "page-number placeholder must be present on content master");
assert.match(contentLayoutXml, /idx="100"/, "logo placeholder region must be registered on the content master");

const titleCount = (contentLayoutXml.match(/type="title"/g) ?? []).length;
assert.equal(titleCount, 0, "content master must not use title-type placeholders");

const bodyCount = (contentLayoutXml.match(/type="body"/g) ?? []).length;
assert.equal(bodyCount, 3, "content master must define section label, slide title, and footer body placeholders");

assert.match(
  contentLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.branding.footer.x)}" y="${inchesToEmu(layout.branding.footer.y)}"`),
  "footer placeholder x/y must follow BorekBranding tokens",
);
assert.match(
  contentLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.sectionLabel.x)}" y="${inchesToEmu(layout.sectionLabel.y)}"`),
  "section label placeholder x/y must follow content layout tokens",
);
assert.match(
  contentLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.slideTitle.x)}" y="${inchesToEmu(layout.slideTitle.y)}"`),
  "slide title placeholder x/y must follow content layout tokens",
);

assert.ok(
  !/subtitle|statBadge|coverTitle/i.test(contentLayoutXml),
  "content master must not define cover/subtitle/stat regions",
);

process.stdout.write("AT-17 renderer unit checks passed\n");
