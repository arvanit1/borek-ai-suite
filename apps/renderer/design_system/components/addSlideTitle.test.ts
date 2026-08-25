/** AT-19 unit checks executed by pytest via `npm run test:at19 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import {
  CLOSING_TITLE_PLACEHOLDER,
  COVER_TITLE_PLACEHOLDER,
  SECTION_TITLE_PLACEHOLDER,
  SLIDE_TITLE_PLACEHOLDER,
  addSlideTitle,
  resolveSlideTitleColor,
  slideTitleTextOptions,
} from "./addSlideTitle.js";
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
  "addSlideTitle.ts",
);

const SAMPLE_TITLE = "System Overview";
const SAMPLE_COVER_TITLE = "Invoice 3-Way Match Automation";
const SAMPLE_SECTION_TITLE = "Architecture";
const SAMPLE_CLOSING_TITLE = "Next Steps";

assert.ok(existsSync(COMPONENT_TS), "addSlideTitle.ts must exist");
assert.equal(SLIDE_TITLE_PLACEHOLDER, "slideTitle");
assert.equal(COVER_TITLE_PLACEHOLDER, "coverTitle");
assert.equal(SECTION_TITLE_PLACEHOLDER, "sectionTitle");
assert.equal(CLOSING_TITLE_PLACEHOLDER, "slideTitle");

assert.equal(resolveSlideTitleColor("light"), BorekColors.text);
assert.equal(resolveSlideTitleColor("dark"), BorekColors.background);

const defaultOptions = slideTitleTextOptions();
assert.equal(defaultOptions.placeholder, SLIDE_TITLE_PLACEHOLDER);
assert.equal(defaultOptions.color, BorekColors.text);
assert.equal(defaultOptions.fontFace, BorekTypography.fonts.heading);
assert.equal(defaultOptions.fontSize, BorekTypography.defaultSizes.heading);
assert.equal(defaultOptions.align, "left");
assert.equal(defaultOptions.valign, "top");

const darkCoverOptions = slideTitleTextOptions({
  placeholder: COVER_TITLE_PLACEHOLDER,
  variant: "dark",
});
assert.equal(darkCoverOptions.placeholder, COVER_TITLE_PLACEHOLDER);
assert.equal(darkCoverOptions.color, BorekColors.background);

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
  (slide) => addSlideTitle(slide, SAMPLE_TITLE),
);

assert.match(contentSlideXml, new RegExp(SAMPLE_TITLE), "content slide must contain the title text");
assert.match(
  contentSlideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.text}"/>`),
  "light-variant title must use BorekColors.text",
);
assert.match(
  contentSlideXml,
  new RegExp(BorekTypography.fonts.heading.replace(/ /g, "\\s*")),
  "title must use heading font family from BorekTypography",
);

const coverSlideXml = await slideXmlFromDeck(
  registerMasterCover,
  MASTER_COVER_NAME,
  (slide) =>
    addSlideTitle(slide, SAMPLE_COVER_TITLE, {
      placeholder: COVER_TITLE_PLACEHOLDER,
      variant: "dark",
    }),
);

assert.match(coverSlideXml, new RegExp(SAMPLE_COVER_TITLE), "cover slide must contain the title text");
assert.match(
  coverSlideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.background}"/>`),
  "dark-variant cover title must use BorekColors.background",
);

const sectionSlideXml = await slideXmlFromDeck(
  registerMasterSection,
  MASTER_SECTION_NAME,
  (slide) =>
    addSlideTitle(slide, SAMPLE_SECTION_TITLE, {
      placeholder: SECTION_TITLE_PLACEHOLDER,
      variant: "light",
    }),
);

assert.match(sectionSlideXml, new RegExp(SAMPLE_SECTION_TITLE), "section slide must contain the title text");

const closingSlideXml = await slideXmlFromDeck(
  registerMasterClosing,
  MASTER_CLOSING_NAME,
  (slide) =>
    addSlideTitle(slide, SAMPLE_CLOSING_TITLE, {
      placeholder: CLOSING_TITLE_PLACEHOLDER,
      variant: "dark",
    }),
);

assert.match(closingSlideXml, new RegExp(SAMPLE_CLOSING_TITLE), "closing slide must contain the title text");
assert.match(
  closingSlideXml,
  new RegExp(`<a:srgbClr val="${BorekColors.background}"/>`),
  "dark-variant closing title must use BorekColors.background",
);

process.stdout.write("AT-19 renderer unit checks passed\n");
