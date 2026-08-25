/** AT-21 unit checks executed by pytest via `npm run test:at21 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  FOOTER_LABEL_SEPARATOR,
  FOOTER_PLACEHOLDER,
  addFooter,
  footerTextOptions,
  formatFooterLabel,
} from "./addFooter.js";
import { registerMasterClosing, MASTER_CLOSING_NAME } from "../masters/MASTER_CLOSING.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
import { registerMasterCover, MASTER_COVER_NAME } from "../masters/MASTER_COVER.js";
import { registerMasterDefault, MASTER_DEFAULT_NAME } from "../masters/MASTER_DEFAULT.js";
import { registerMasterSection, MASTER_SECTION_NAME } from "../masters/MASTER_SECTION.js";
import { BorekBranding } from "../tokens/branding.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekTypography } from "../tokens/typography.js";

const HARDCODED_HEX_PATTERN = /#?[0-9A-Fa-f]{6}\b/g;
const FONT_FAMILY_PATTERNS = [/["']Aptos Display["']/g, /["']Aptos["'](?!\s*Display)/g];
const INLINE_FONT_SIZE_PATTERN = /fontSize\s*:\s*\d+(?:\.\d+)?/g;

function findHardcodedHexInContent(content: string): string[] {
  return [...content.matchAll(HARDCODED_HEX_PATTERN)].map((match) => match[0]);
}

function findHardcodedFontFamilyInContent(content: string): string[] {
  const matches: string[] = [];
  for (const pattern of FONT_FAMILY_PATTERNS) {
    for (const match of content.matchAll(pattern)) {
      matches.push(match[0]);
    }
  }
  return matches;
}

function findInlineFontSizeInContent(content: string): string[] {
  return [...content.matchAll(INLINE_FONT_SIZE_PATTERN)].map((match) => match[0]);
}

const COMPONENT_TS = join(fileURLToPath(new URL(".", import.meta.url)), "addFooter.ts");

const SAMPLE_FOOTER = formatFooterLabel({
  clientName: "Borek Solutions",
  opportunityTitle: "Invoice 3-Way Match Automation",
});

assert.ok(existsSync(COMPONENT_TS), "addFooter.ts must exist");
assert.equal(FOOTER_PLACEHOLDER, "footer");
assert.equal(FOOTER_LABEL_SEPARATOR, " · ");
assert.equal(
  formatFooterLabel({ clientName: "Borek Solutions", opportunityTitle: "Invoice 3-Way Match Automation" }),
  "Borek Solutions · Invoice 3-Way Match Automation",
);
assert.equal(formatFooterLabel({ clientName: "", opportunityTitle: "Only Title" }), "Only Title");
assert.equal(formatFooterLabel({ clientName: "Only Client", opportunityTitle: "" }), "Only Client");

const options = footerTextOptions();
assert.equal(options.placeholder, FOOTER_PLACEHOLDER);
assert.equal(options.color, BorekColors.mutedText);
assert.equal(options.fontFace, BorekTypography.fonts.body);
assert.equal(options.fontSize, BorekTypography.defaultSizes.body);
assert.equal(options.align, "left");
assert.equal(options.valign, BorekBranding.footer.valign);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

async function slideXmlFromDeck(
  register: (pptx: PptxGenJS) => void,
  masterName: string,
): Promise<string> {
  const pptx = new PptxGenJS();
  register(pptx);
  const slide = pptx.addSlide({ masterName });
  addFooter(slide, SAMPLE_FOOTER);

  const buffer = await pptx.write({ outputType: "nodebuffer" });
  assert.ok(Buffer.isBuffer(buffer));

  const zip = await JSZip.loadAsync(buffer);
  const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
  assert.ok(slidePath, "pptx must contain slide1.xml");

  const xml = await zip.file(slidePath)?.async("string");
  assert.ok(xml, "slide1.xml must be readable");
  return xml;
}

const masterCases = [
  ["MASTER_DEFAULT", registerMasterDefault, MASTER_DEFAULT_NAME],
  ["MASTER_COVER", registerMasterCover, MASTER_COVER_NAME],
  ["MASTER_SECTION", registerMasterSection, MASTER_SECTION_NAME],
  ["MASTER_CONTENT", registerMasterContent, MASTER_CONTENT_NAME],
  ["MASTER_CLOSING", registerMasterClosing, MASTER_CLOSING_NAME],
] as const;

for (const [label, register, masterName] of masterCases) {
  const slideXml = await slideXmlFromDeck(register, masterName);
  assert.match(slideXml, /Borek Solutions/, `${label} footer must contain client name`);
  assert.match(slideXml, /Invoice 3-Way Match Automation/, `${label} footer must contain opportunity title`);
  assert.match(
    slideXml,
    new RegExp(`<a:srgbClr val="${BorekColors.mutedText}"/>`),
    `${label} footer must use BorekColors.mutedText`,
  );
  assert.match(
    slideXml,
    new RegExp(BorekTypography.fonts.body.replace(/ /g, "\\s*")),
    `${label} footer must use body font from BorekTypography`,
  );
}

process.stdout.write("AT-21 renderer unit checks passed\n");
