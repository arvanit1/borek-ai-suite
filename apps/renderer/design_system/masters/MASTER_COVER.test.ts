/** AT-15 unit checks executed by pytest via `npm run test:at15 --workspace borek-renderer`. */

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
  MASTER_COVER_NAME,
  MASTER_COVER_SECTION_LABEL_PLACEHOLDER,
  MASTER_COVER_STAT_BADGE_PLACEHOLDER_1,
  MASTER_COVER_STAT_BADGE_PLACEHOLDER_2,
  MASTER_COVER_STAT_BADGE_PLACEHOLDER_3,
  MASTER_COVER_SUBTITLE_PLACEHOLDER,
  MASTER_COVER_TITLE_PLACEHOLDER,
  computeMasterCoverLayout,
  registerMasterCover,
} from "./MASTER_COVER.js";

const EMU_PER_INCH = 914_400;

function inchesToEmu(inches: number): number {
  return Math.round(inches * EMU_PER_INCH);
}

const MASTER_TS = join(
  fileURLToPath(new URL(".", import.meta.url)),
  "MASTER_COVER.ts",
);

const layout = computeMasterCoverLayout();
const { marginX, marginTop, footerHeight } = BorekSpacing;
const { columnGap, rowGap } = BorekGrid;
const contentWidth = BorekSlide.widthInches - marginX * 2;
const footerY = BorekSlide.heightInches - footerHeight;

assert.ok(existsSync(MASTER_TS), "MASTER_COVER.ts must exist");
assert.equal(MASTER_COVER_NAME, "MASTER_COVER");
assert.equal(BorekColors.coverBackground, BorekColors.text);

assert.equal(layout.sectionLabel.x, marginX);
assert.equal(layout.sectionLabel.y, marginTop + BorekBranding.logo.height + rowGap);
assert.equal(layout.sectionLabel.h, footerHeight);
assert.equal(layout.sectionLabel.w, contentWidth);

assert.equal(layout.title.y, layout.sectionLabel.y + layout.sectionLabel.h + rowGap);
assert.equal(layout.title.h, marginTop * 2);
assert.equal(layout.subtitle.y, layout.title.y + layout.title.h + rowGap);
assert.equal(layout.subtitle.h, footerHeight);

const statBadgeH = footerHeight * 2;
const statBadgeW = (contentWidth - columnGap * 2) / 3;
const statBadgeY = footerY - rowGap - statBadgeH;

for (const [index, badge] of layout.statBadges.entries()) {
  assert.equal(badge.y, statBadgeY);
  assert.equal(badge.h, statBadgeH);
  assert.equal(badge.w, statBadgeW);
  assert.equal(badge.x, marginX + index * (statBadgeW + columnGap));
}

assert.equal(layout.branding.footer.y, footerY);
assert.match(layout.branding.slideNumber.format, /number/);

const pptx = new PptxGenJS();
registerMasterCover(pptx);
pptx.addSlide({ masterName: MASTER_COVER_NAME });

const buffer = await pptx.write({ outputType: "nodebuffer" });
assert.ok(Buffer.isBuffer(buffer));
assert.ok(buffer.byteLength > 1_000, "MASTER_COVER deck must produce a non-trivial pptx buffer");

const zip = await JSZip.loadAsync(buffer);
const layoutXmlPaths = Object.keys(zip.files).filter((path) => /ppt\/slideLayouts\/slideLayout\d+\.xml$/.test(path));
assert.ok(layoutXmlPaths.length >= 1, "pptx must contain slide layouts");

let coverLayoutXml: string | undefined;
for (const path of layoutXmlPaths) {
  const xml = await zip.file(path)?.async("string");
  if (xml?.includes(`name="${MASTER_COVER_NAME}"`)) {
    coverLayoutXml = xml;
    break;
  }
}

assert.ok(coverLayoutXml, "pptx must contain a slide layout named MASTER_COVER");
assert.match(
  coverLayoutXml,
  new RegExp(`<a:srgbClr val="${BorekColors.coverBackground}"/>|<a:srgbClr val="${BorekColors.coverBackground}"`),
  "cover master background must use BorekColors.coverBackground",
);

assert.match(coverLayoutXml, /type="title"/, "cover title placeholder must be present");
assert.match(coverLayoutXml, /type="body"/, "cover body placeholders must include subtitle/stat/footer regions");
assert.match(coverLayoutXml, /type="sldNum"/i, "page-number placeholder must be present on cover master");
assert.match(coverLayoutXml, /idx="100"/, "logo placeholder region must be registered on the cover master");

const titleCount = (coverLayoutXml.match(/type="title"/g) ?? []).length;
assert.ok(titleCount >= 1, "cover master must define a title placeholder region");

const bodyCount = (coverLayoutXml.match(/type="body"/g) ?? []).length;
assert.ok(bodyCount >= 5, "cover master must define subtitle, section label, stat badges, and footer body placeholders");

assert.match(
  coverLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.branding.footer.x)}" y="${inchesToEmu(layout.branding.footer.y)}"`),
  "footer placeholder x/y must follow BorekBranding tokens",
);
assert.match(
  coverLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.title.x)}" y="${inchesToEmu(layout.title.y)}"`),
  "title placeholder x/y must follow cover layout tokens",
);
assert.match(
  coverLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.subtitle.x)}" y="${inchesToEmu(layout.subtitle.y)}"`),
  "subtitle placeholder x/y must follow cover layout tokens",
);
assert.match(
  coverLayoutXml,
  new RegExp(`<a:off x="${inchesToEmu(layout.statBadges[0].x)}" y="${inchesToEmu(layout.statBadges[0].y)}"`),
  "stat badge 1 placeholder must follow cover layout tokens",
);

assert.equal(MASTER_COVER_TITLE_PLACEHOLDER, "coverTitle");
assert.equal(MASTER_COVER_SUBTITLE_PLACEHOLDER, "coverSubtitle");
assert.equal(MASTER_COVER_SECTION_LABEL_PLACEHOLDER, "coverSectionLabel");
assert.equal(MASTER_COVER_STAT_BADGE_PLACEHOLDER_1, "statBadge1");
assert.equal(MASTER_COVER_STAT_BADGE_PLACEHOLDER_2, "statBadge2");
assert.equal(MASTER_COVER_STAT_BADGE_PLACEHOLDER_3, "statBadge3");

process.stdout.write("AT-15 renderer unit checks passed\n");
