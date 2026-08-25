/** AT-20 unit checks executed by pytest via `npm run test:at20 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  CLOSING_SECTION_LABEL_PLACEHOLDER,
  COVER_SECTION_LABEL_PLACEHOLDER,
  SECTION_DIVIDER_LABEL_PLACEHOLDER,
  SECTION_LABEL_PLACEHOLDER,
  addSectionLabel,
  resolveSectionLabelColor,
  sectionLabelTextOptions,
} from "./addSectionLabel.js";
import { registerMasterClosing, MASTER_CLOSING_NAME } from "../masters/MASTER_CLOSING.js";
import { registerMasterContent, MASTER_CONTENT_NAME } from "../masters/MASTER_CONTENT.js";
import { registerMasterCover, MASTER_COVER_NAME } from "../masters/MASTER_COVER.js";
import { registerMasterSection, MASTER_SECTION_NAME } from "../masters/MASTER_SECTION.js";
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

const COMPONENT_TS = join(
  fileURLToPath(new URL(".", import.meta.url)),
  "addSectionLabel.ts",
);

const SAMPLE_LABEL = "ARCHITECTURE";
const SAMPLE_COVER_LABEL = "AUTOMATION PROPOSAL";
const SAMPLE_SECTION_LABEL = "TECHNICAL DESIGN";
const SAMPLE_CLOSING_LABEL = "NEXT STEPS";

assert.ok(existsSync(COMPONENT_TS), "addSectionLabel.ts must exist");
assert.equal(SECTION_LABEL_PLACEHOLDER, "sectionLabel");
assert.equal(COVER_SECTION_LABEL_PLACEHOLDER, "coverSectionLabel");
assert.equal(SECTION_DIVIDER_LABEL_PLACEHOLDER, "sectionLabel");
assert.equal(CLOSING_SECTION_LABEL_PLACEHOLDER, "sectionLabel");

assert.equal(resolveSectionLabelColor("accent"), BorekColors.primary);
assert.equal(resolveSectionLabelColor("inverse"), BorekColors.background);

const defaultOptions = sectionLabelTextOptions();
assert.equal(defaultOptions.placeholder, SECTION_LABEL_PLACEHOLDER);
assert.equal(defaultOptions.color, BorekColors.primary);
assert.equal(defaultOptions.fontFace, BorekTypography.fonts.body);
assert.equal(defaultOptions.fontSize, BorekTypography.defaultSizes.body);
assert.equal(defaultOptions.align, "left");
assert.equal(defaultOptions.valign, "top");

const inverseCoverOptions = sectionLabelTextOptions({
  placeholder: COVER_SECTION_LABEL_PLACEHOLDER,
  variant: "inverse",
});
assert.equal(inverseCoverOptions.placeholder, COVER_SECTION_LABEL_PLACEHOLDER);
assert.equal(inverseCoverOptions.color, BorekColors.background);

const componentSource = readFileSync(COMPONENT_TS, "utf8");
assert.deepEqual(findHardcodedFontFamilyInContent(componentSource), []);
assert.deepEqual(findInlineFontSizeInContent(componentSource), []);
assert.deepEqual(findHardcodedHexInContent(componentSource), []);

async function slideXmlFromDeck(
  register: (pptx: PptxGenJS) => void,
  masterName: string,
  render: (slide: PptxGenJS.Slide) => void,
): Promise<string> {
  const pptx = new PptxGenJS();
  register(pptx);
  const slide = pptx.addSlide({ masterName });
  render(slide);

  const buffer = await pptx.write({ outputType: "nodebuffer" });
  assert.ok(Buffer.isBuffer(buffer));

  const zip = await JSZip.loadAsync(buffer);
  const slidePath = Object.keys(zip.files).find((path) => /ppt\/slides\/slide1\.xml$/.test(path));
  assert.ok(slidePath, "pptx must contain slide1.xml");

  const xml = await zip.file(slidePath)?.async("string");
  assert.ok(xml, "slide1.xml must be readable");
  return xml;
}

const contentSlideXml = await slideXmlFromDeck(
  registerMasterContent,
  MASTER_CONTENT_NAME,
  (slide) => addSectionLabel(slide, SAMPLE_LABEL),
);

assert.match(contentSlideXml, new RegExp(SAMPLE_LABEL), "content slide must contain the section label text");
assert.match(
  contentSlideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.primary}"/>`),
  "accent-variant section label must use BorekColors.primary",
);
assert.match(
  contentSlideXml,
  new RegExp(BorekTypography.fonts.body.replace(/ /g, "\\s*")),
  "section label must use body font family from BorekTypography",
);

const coverSlideXml = await slideXmlFromDeck(
  registerMasterCover,
  MASTER_COVER_NAME,
  (slide) =>
    addSectionLabel(slide, SAMPLE_COVER_LABEL, {
      placeholder: COVER_SECTION_LABEL_PLACEHOLDER,
      variant: "inverse",
    }),
);

assert.match(coverSlideXml, new RegExp(SAMPLE_COVER_LABEL), "cover slide must contain the section label text");
assert.match(
  coverSlideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.background}"/>`),
  "inverse-variant cover section label must use BorekColors.background",
);

const sectionSlideXml = await slideXmlFromDeck(
  registerMasterSection,
  MASTER_SECTION_NAME,
  (slide) =>
    addSectionLabel(slide, SAMPLE_SECTION_LABEL, {
      placeholder: SECTION_DIVIDER_LABEL_PLACEHOLDER,
      variant: "accent",
    }),
);

assert.match(sectionSlideXml, new RegExp(SAMPLE_SECTION_LABEL), "section-divider slide must contain the label text");

const closingSlideXml = await slideXmlFromDeck(
  registerMasterClosing,
  MASTER_CLOSING_NAME,
  (slide) =>
    addSectionLabel(slide, SAMPLE_CLOSING_LABEL, {
      placeholder: CLOSING_SECTION_LABEL_PLACEHOLDER,
      variant: "accent",
    }),
);

assert.match(closingSlideXml, new RegExp(SAMPLE_CLOSING_LABEL), "closing slide must contain the section label text");
assert.match(
  closingSlideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.primary}"/>`),
  "accent-variant closing section label must use BorekColors.primary on dark background",
);

process.stdout.write("AT-20 renderer unit checks passed\n");
