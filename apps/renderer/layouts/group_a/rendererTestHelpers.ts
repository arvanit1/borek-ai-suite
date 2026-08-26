import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import { registerMasterContent, MASTER_CONTENT_NAME } from "../../design_system/masters/MASTER_CONTENT.js";

export interface RenderToPptxOptions {
  registerMaster?: (pptx: PptxGenJS) => void;
  expectedMasterName?: string;
}

export const HARDCODED_HEX_PATTERN = /#?[0-9A-Fa-f]{6}\b/g;
export const INLINE_FONT_SIZE_PATTERN = /fontSize\s*:\s*\d+(?:\.\d+)?/g;
export const INLINE_FONT_FAMILY_PATTERN = /fontFace\s*:\s*["'][^"']+["']/g;

export function readRendererSource(url: URL): string {
  return readFileSync(url, "utf8");
}

export async function renderToPptx(
  render: (pptx: PptxGenJS) => PptxGenJS.Slide,
  options: RenderToPptxOptions = {},
): Promise<{ buffer: Buffer; slideXml: string; zip: JSZip }> {
  const pptx = new PptxGenJS();
  const registerMaster = options.registerMaster ?? registerMasterContent;
  const expectedMasterName = options.expectedMasterName ?? MASTER_CONTENT_NAME;
  registerMaster(pptx);
  render(pptx);

  const output = await pptx.write({ outputType: "nodebuffer" });
  assert.ok(Buffer.isBuffer(output), "renderer must produce a PPTX buffer");

  const zip = await JSZip.loadAsync(output);
  const slideXml = await zip.file("ppt/slides/slide1.xml")?.async("string");
  assert.ok(slideXml, "rendered PPTX must contain slide1.xml");
  await assertUsesMaster(zip, expectedMasterName);

  return { buffer: output, slideXml, zip };
}

export async function assertUsesMaster(zip: JSZip, expectedMasterName: string): Promise<void> {
  const rels = await zip.file("ppt/slides/_rels/slide1.xml.rels")?.async("string");
  assert.ok(rels, "rendered slide must have relationships");

  const target = rels.match(/Type="[^"]*\/slideLayout" Target="([^"]+)"/)?.[1];
  assert.ok(target, "rendered slide must reference a slide layout");

  const layoutPath = `ppt/${target.replace(/^\.\.\//, "")}`;
  const layoutXml = await zip.file(layoutPath)?.async("string");
  assert.ok(layoutXml, `referenced slide layout must exist at ${layoutPath}`);
  assert.match(layoutXml, new RegExp(`name="${expectedMasterName}"`));
}

export function assertRendererUsesSharedPrimitives(
  source: string,
  expectedCardCalls: number,
): void {
  assert.match(source, /MASTER_CONTENT_NAME/);
  assert.match(source, /addSlideTitle\(/);
  assert.match(source, /addSectionLabel\(/);
  assert.equal([...source.matchAll(/addContentCard\(/g)].length, expectedCardCalls);
  assert.deepEqual([...source.matchAll(HARDCODED_HEX_PATTERN)], []);
  assert.deepEqual([...source.matchAll(INLINE_FONT_SIZE_PATTERN)], []);
  assert.deepEqual([...source.matchAll(INLINE_FONT_FAMILY_PATTERN)], []);
  assert.doesNotMatch(source, /\b(?:fetch|axios|OpenAI)\b/);
  assert.doesNotMatch(source, /\b(?:validate\w*|compress\w*|truncate\w*)\s*\(/i);
}

export function assertXmlContains(slideXml: string, values: readonly string[]): void {
  for (const value of values) {
    assert.match(slideXml, new RegExp(escapeRegExp(value)));
  }
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
