/** AT-10: Render validation checks after AT-9 preview (technical plan section 18.3). */

import { constants as fsConstants } from "node:fs";
import { accessSync, readFileSync } from "node:fs";
import { basename } from "node:path";
import { PNG } from "pngjs";

import type { PresentationPlan } from "../src/contracts.js";
import type { LibreOfficePreviewResult } from "./libreoffice_pipeline.js";
import { SLIDE_IMAGE_PREFIX } from "./libreoffice_pipeline.js";

export const RENDER_VALIDATION_FAILED = "RENDER_VALIDATION_FAILED";

/** Minimum share of non-near-white pixels required for a slide PNG to count as non-blank. */
export const BLANK_SLIDE_MIN_NON_WHITE_RATIO = 0.001;

export type RenderCheckIssueCode =
  | "RENDER_EXCEPTION"
  | "SLIDE_COUNT_MISMATCH"
  | "MISSING_SLIDE"
  | "BLANK_SLIDE"
  | "INVALID_PREVIEW_ARTIFACT";

export type RenderCheckIssue = {
  code: RenderCheckIssueCode;
  message: string;
  slideIndex?: number;
};

export type RenderCheckResult = {
  status: "VALID" | "VALIDATION_FAILED";
  issues: RenderCheckIssue[];
  errorCode?: string;
};

export type RenderCheckInput = {
  presentationPlan: PresentationPlan;
  preview: LibreOfficePreviewResult | null;
  renderError?: string | null;
};

export function runRenderChecks(input: RenderCheckInput): RenderCheckResult {
  const issues: RenderCheckIssue[] = [];

  if (input.renderError) {
    issues.push({
      code: "RENDER_EXCEPTION",
      message: input.renderError,
    });
    return failed(issues);
  }

  if (input.preview === null) {
    issues.push({
      code: "RENDER_EXCEPTION",
      message: "Preview pipeline did not produce output",
    });
    return failed(issues);
  }

  issues.push(...collectPreviewArtifactIssues(input.preview));
  if (issues.length > 0) {
    return failed(issues);
  }

  const expectedCount = input.presentationPlan.slides.length;
  const actualCount = input.preview.slideImagePaths.length;

  if (actualCount !== expectedCount) {
    issues.push({
      code: "SLIDE_COUNT_MISMATCH",
      message: `Expected ${expectedCount} slides from approved plan, got ${actualCount} preview images`,
    });
  }

  issues.push(...collectMissingSlideIssues(input.preview.slideImagePaths, expectedCount));
  issues.push(...collectBlankSlideIssues(input.preview.slideImagePaths));

  if (issues.length > 0) {
    return failed(issues);
  }

  return { status: "VALID", issues: [] };
}

function failed(issues: RenderCheckIssue[]): RenderCheckResult {
  return {
    status: "VALIDATION_FAILED",
    issues,
    errorCode: RENDER_VALIDATION_FAILED,
  };
}

function collectPreviewArtifactIssues(preview: LibreOfficePreviewResult): RenderCheckIssue[] {
  const issues: RenderCheckIssue[] = [];

  if (!isReadableNonEmptyFile(preview.pdfPath)) {
    issues.push({
      code: "INVALID_PREVIEW_ARTIFACT",
      message: `PDF preview artifact missing or empty: ${preview.pdfPath}`,
    });
  }

  if (preview.slideImagePaths.length === 0) {
    issues.push({
      code: "INVALID_PREVIEW_ARTIFACT",
      message: "Preview pipeline produced zero slide images",
    });
  }

  for (const [index, slidePath] of preview.slideImagePaths.entries()) {
    if (!isReadableNonEmptyFile(slidePath)) {
      issues.push({
        code: "INVALID_PREVIEW_ARTIFACT",
        message: `Slide preview image missing or empty: ${slidePath}`,
        slideIndex: index + 1,
      });
    }
  }

  return issues;
}

function collectMissingSlideIssues(slideImagePaths: string[], expectedCount: number): RenderCheckIssue[] {
  const issues: RenderCheckIssue[] = [];
  const observedNumbers: number[] = [];

  for (const slidePath of slideImagePaths) {
    try {
      observedNumbers.push(parseSlideImageNumber(slidePath));
    } catch {
      issues.push({
        code: "MISSING_SLIDE",
        message: `Preview image has unexpected filename: ${basename(slidePath)}`,
      });
    }
  }

  for (let index = 1; index <= expectedCount; index += 1) {
    if (!observedNumbers.includes(index)) {
      issues.push({
        code: "MISSING_SLIDE",
        message: `Missing preview image for slide ${index}`,
        slideIndex: index,
      });
    }
  }

  return issues;
}

function collectBlankSlideIssues(slideImagePaths: string[]): RenderCheckIssue[] {
  const issues: RenderCheckIssue[] = [];

  for (const [index, slidePath] of slideImagePaths.entries()) {
    try {
      if (isBlankSlideImage(slidePath)) {
        issues.push({
          code: "BLANK_SLIDE",
          message: `Slide ${index + 1} preview image appears blank`,
          slideIndex: index + 1,
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      issues.push({
        code: "INVALID_PREVIEW_ARTIFACT",
        message: `Could not read slide ${index + 1} preview image: ${message}`,
        slideIndex: index + 1,
      });
    }
  }

  return issues;
}

export function parseSlideImageNumber(slideImagePath: string): number {
  const filename = basename(slideImagePath);
  const match = filename.match(new RegExp(`^${SLIDE_IMAGE_PREFIX}-(\\d+)\\.png$`));
  if (!match) {
    throw new Error(`Unexpected slide preview filename: ${filename}`);
  }
  return Number.parseInt(match[1]!, 10);
}

export function isBlankSlideImage(
  slideImagePath: string,
  minNonWhiteRatio: number = BLANK_SLIDE_MIN_NON_WHITE_RATIO,
): boolean {
  const png = PNG.sync.read(readFileSync(slideImagePath));
  const pixelCount = png.width * png.height;
  if (pixelCount === 0) {
    return true;
  }

  let nonWhitePixels = 0;
  for (let offset = 0; offset < png.data.length; offset += 4) {
    const red = png.data[offset] ?? 255;
    const green = png.data[offset + 1] ?? 255;
    const blue = png.data[offset + 2] ?? 255;
    if (red < 250 || green < 250 || blue < 250) {
      nonWhitePixels += 1;
    }
  }

  return nonWhitePixels / pixelCount < minNonWhiteRatio;
}

function isReadableNonEmptyFile(path: string): boolean {
  try {
    accessSync(path, fsConstants.R_OK);
    return readFileSync(path).length > 0;
  } catch {
    return false;
  }
}
