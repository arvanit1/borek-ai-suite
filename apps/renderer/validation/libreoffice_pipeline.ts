/** AT-9: LibreOffice headless preview pipeline — pptx → pdf + per-slide png (technical plan §18.3, §19). */

import { spawnSync } from "node:child_process";
import { constants as fsConstants } from "node:fs";
import { accessSync, mkdirSync, readdirSync, renameSync } from "node:fs";
import { basename, extname, join, resolve } from "node:path";

export const SLIDE_IMAGE_PREFIX = "slide";
export const DEFAULT_RENDER_DPI = 150;

export type LibreOfficePreviewResult = {
  pdfPath: string;
  slideImagePaths: string[];
};

export type LibreOfficePreviewOptions = {
  outputDir?: string;
  sofficePath?: string;
  pdftoppmPath?: string;
  renderDpi?: number;
};

export class LibreOfficePipelineError extends Error {
  override name = "LibreOfficePipelineError";

  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
  }
}

export function resolveSofficeCommand(explicitPath?: string): string {
  const candidates = [
    explicitPath,
    process.env.SOFFICE_PATH,
    process.env.LIBREOFFICE_PATH,
    "soffice",
    "libreoffice",
  ].filter((value): value is string => Boolean(value));

  for (const candidate of candidates) {
    if (commandExists(candidate)) {
      return candidate;
    }
  }

  throw new LibreOfficePipelineError(
    "LibreOffice (soffice) not found. Install LibreOffice or set SOFFICE_PATH.",
  );
}

export function resolvePdftoppmCommand(explicitPath?: string): string {
  const candidates = [explicitPath, process.env.PDFTOPPM_PATH, "pdftoppm"].filter(
    (value): value is string => Boolean(value),
  );

  for (const candidate of candidates) {
    if (commandExists(candidate)) {
      return candidate;
    }
  }

  throw new LibreOfficePipelineError(
    "pdftoppm not found. Install poppler-utils or set PDFTOPPM_PATH.",
  );
}

export function expectedPdfPath(pptxPath: string, outputDir: string): string {
  const stem = basename(pptxPath, extname(pptxPath));
  return join(outputDir, `${stem}.pdf`);
}

export function formatSlideImageFilename(index: number, totalSlides: number): string {
  const width = Math.max(2, String(totalSlides).length);
  return `${SLIDE_IMAGE_PREFIX}-${String(index).padStart(width, "0")}.png`;
}

export function normalizeSlideImagePaths(outputDir: string, generatedPaths: string[]): string[] {
  const sorted = sortPopplerPngPaths(generatedPaths);
  const totalSlides = sorted.length;
  const normalized: string[] = [];

  sorted.forEach((sourcePath, index) => {
    const targetName = formatSlideImageFilename(index + 1, totalSlides);
    const targetPath = join(outputDir, targetName);
    if (resolve(sourcePath) !== resolve(targetPath)) {
      renameSync(sourcePath, targetPath);
    }
    normalized.push(targetPath);
  });

  return normalized;
}

export function runLibreOfficePreviewPipeline(
  pptxPath: string,
  options: LibreOfficePreviewOptions = {},
): LibreOfficePreviewResult {
  const absolutePptxPath = resolve(pptxPath);
  assertReadableFile(absolutePptxPath, "PPTX input");

  const outputDir = resolve(options.outputDir ?? join(absolutePptxPath, "..", "preview"));
  mkdirSync(outputDir, { recursive: true });

  const sofficePath = resolveSofficeCommand(options.sofficePath);
  const pdftoppmPath = resolvePdftoppmCommand(options.pdftoppmPath);
  const renderDpi = options.renderDpi ?? DEFAULT_RENDER_DPI;

  convertPptxToPdf(sofficePath, absolutePptxPath, outputDir);

  const pdfPath = expectedPdfPath(absolutePptxPath, outputDir);
  assertReadableFile(pdfPath, "PDF output from LibreOffice");

  const rawSlidePaths = convertPdfToPngs(pdftoppmPath, pdfPath, outputDir, renderDpi);
  const slideImagePaths = normalizeSlideImagePaths(outputDir, rawSlidePaths);

  if (slideImagePaths.length === 0) {
    throw new LibreOfficePipelineError("Preview pipeline produced zero slide images.");
  }

  return { pdfPath, slideImagePaths };
}

function convertPptxToPdf(sofficePath: string, pptxPath: string, outputDir: string): void {
  const result = spawnSync(
    sofficePath,
    ["--headless", "--norestore", "--convert-to", "pdf", "--outdir", outputDir, pptxPath],
    { encoding: "utf-8" },
  );

  if (result.error) {
    throw new LibreOfficePipelineError(
      `LibreOffice failed to convert PPTX to PDF: ${result.error.message}`,
      { cause: result.error },
    );
  }

  if (result.status !== 0) {
    throw new LibreOfficePipelineError(
      formatCommandFailure("LibreOffice PPTX→PDF conversion failed", result.stdout, result.stderr),
    );
  }
}

function convertPdfToPngs(
  pdftoppmPath: string,
  pdfPath: string,
  outputDir: string,
  renderDpi: number,
): string[] {
  const prefix = join(outputDir, SLIDE_IMAGE_PREFIX);
  const result = spawnSync(
    pdftoppmPath,
    ["-png", "-r", String(renderDpi), pdfPath, prefix],
    { encoding: "utf-8" },
  );

  if (result.error) {
    throw new LibreOfficePipelineError(
      `pdftoppm failed to render slide PNGs: ${result.error.message}`,
      { cause: result.error },
    );
  }

  if (result.status !== 0) {
    throw new LibreOfficePipelineError(
      formatCommandFailure("PDF→PNG conversion failed", result.stdout, result.stderr),
    );
  }

  const pngPaths = readdirSync(outputDir)
    .filter((name) => name.startsWith(`${SLIDE_IMAGE_PREFIX}-`) && name.endsWith(".png"))
    .map((name) => join(outputDir, name));

  return sortPopplerPngPaths(pngPaths);
}

function sortPopplerPngPaths(paths: string[]): string[] {
  return [...paths].sort((left, right) => {
    const leftIndex = parsePopplerPageIndex(basename(left));
    const rightIndex = parsePopplerPageIndex(basename(right));
    return leftIndex - rightIndex;
  });
}

function parsePopplerPageIndex(filename: string): number {
  const match = filename.match(new RegExp(`^${SLIDE_IMAGE_PREFIX}-(\\d+)\\.png$`));
  if (!match) {
    throw new LibreOfficePipelineError(`Unexpected slide image filename: ${filename}`);
  }
  return Number.parseInt(match[1]!, 10);
}

function commandExists(command: string): boolean {
  if (command.includes("/") || command.includes("\\")) {
    try {
      accessSync(command, fsConstants.F_OK);
      return true;
    } catch {
      return false;
    }
  }

  const lookup = process.platform === "win32" ? "where" : "which";
  const result = spawnSync(lookup, [command], { encoding: "utf-8" });
  return result.status === 0;
}

function assertReadableFile(path: string, label: string): void {
  try {
    accessSync(path, fsConstants.R_OK);
  } catch {
    throw new LibreOfficePipelineError(`${label} file not found or not readable: ${path}`);
  }
}

function formatCommandFailure(title: string, stdout: string, stderr: string): string {
  const details = [stderr.trim(), stdout.trim()].filter(Boolean).join("\n");
  return details ? `${title}: ${details}` : title;
}
