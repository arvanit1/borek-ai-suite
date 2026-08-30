import { createWriteStream, readFileSync, writeFileSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";

import { ZipArchive } from "archiver";

import { buildDeckBuffer } from "./deck_builder.js";
import type { PresentationPlan, SlideSpecBase } from "./src/contracts.js";
import { runLibreOfficePreviewPipeline } from "./validation/libreoffice_pipeline.js";
import {
  RENDER_VALIDATION_FAILED,
  runRenderChecks,
  type RenderCheckResult,
} from "./validation/render_checks.js";

export const MAX_RENDER_SLIDES = 30;

export type RenderRequest = {
  presentationPlan: PresentationPlan;
  slideSpecs: SlideSpecBase[];
};

export type RenderManifest = {
  pptx: string;
  pdf: string;
  previews: string[];
  slideCount: number;
  validation: RenderCheckResult;
};

export class RenderServiceError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode = 422,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "RenderServiceError";
  }
}

export function validateRenderRequest(value: unknown): RenderRequest {
  if (!value || typeof value !== "object") {
    throw new RenderServiceError("INVALID_RENDER_REQUEST", "Request body must be an object", 400);
  }
  const request = value as Partial<RenderRequest>;
  if (!request.presentationPlan || !Array.isArray(request.presentationPlan.slides)) {
    throw new RenderServiceError(
      "INVALID_RENDER_REQUEST",
      "presentationPlan.slides must be an array",
      400,
    );
  }
  if (!Array.isArray(request.slideSpecs)) {
    throw new RenderServiceError("INVALID_RENDER_REQUEST", "slideSpecs must be an array", 400);
  }
  if (request.slideSpecs.length === 0 || request.slideSpecs.length > MAX_RENDER_SLIDES) {
    throw new RenderServiceError(
      "INVALID_SLIDE_COUNT",
      `slideSpecs must contain between 1 and ${MAX_RENDER_SLIDES} slides`,
      400,
    );
  }
  if (request.presentationPlan.slides.length !== request.slideSpecs.length) {
    throw new RenderServiceError(
      "SLIDE_COUNT_MISMATCH",
      "PresentationPlan and SlideSpec counts must match",
    );
  }

  request.presentationPlan.slides.forEach((planned, index) => {
    const spec = request.slideSpecs![index] as SlideSpecBase | undefined;
    if (!spec || typeof spec.layoutId !== "string") {
      throw new RenderServiceError(
        "INVALID_SLIDE_SPEC",
        `SlideSpec ${index + 1} must include layoutId`,
        400,
      );
    }
    if (planned.layoutId !== spec.layoutId) {
      throw new RenderServiceError(
        "LAYOUT_MISMATCH",
        `Slide ${index + 1} planned ${planned.layoutId} but received ${spec.layoutId}`,
      );
    }
  });

  return request as RenderRequest;
}

export async function renderArtifactBundle(requestValue: unknown): Promise<Buffer> {
  const request = validateRenderRequest(requestValue);
  const workDir = await mkdtemp(join(tmpdir(), "borek-render-"));
  try {
    const pptxPath = join(workDir, "deck.pptx");
    writeFileSync(pptxPath, await buildDeckBuffer(request.slideSpecs));

    let preview;
    try {
      preview = runLibreOfficePreviewPipeline(pptxPath, { outputDir: workDir });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new RenderServiceError(RENDER_VALIDATION_FAILED, message, 422);
    }

    const validation = runRenderChecks({
      presentationPlan: request.presentationPlan,
      preview,
    });
    if (validation.status !== "VALID") {
      throw new RenderServiceError(
        validation.errorCode ?? RENDER_VALIDATION_FAILED,
        "Rendered deck failed validation",
        422,
        validation.issues,
      );
    }

    const manifest: RenderManifest = {
      pptx: "deck.pptx",
      pdf: "deck.pdf",
      previews: preview.slideImagePaths.map((path) => basename(path)),
      slideCount: request.slideSpecs.length,
      validation,
    };
    const manifestPath = join(workDir, "manifest.json");
    writeFileSync(manifestPath, `${JSON.stringify(manifest)}\n`, "utf8");

    return await createArchiveBuffer([
      pptxPath,
      preview.pdfPath,
      ...preview.slideImagePaths,
      manifestPath,
    ]);
  } finally {
    await rm(workDir, { recursive: true, force: true });
  }
}

async function createArchiveBuffer(paths: readonly string[]): Promise<Buffer> {
  const archivePath = join(
    tmpdir(),
    `borek-artifacts-${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}.zip`,
  );
  try {
    await new Promise<void>((resolve, reject) => {
      const output = createWriteStream(archivePath);
      const archive = new ZipArchive({ zlib: { level: 9 } });
      output.on("close", resolve);
      output.on("error", reject);
      archive.on("error", reject);
      archive.pipe(output);
      for (const path of paths) {
        archive.file(path, { name: basename(path) });
      }
      void archive.finalize();
    });
    return readFileSync(archivePath);
  } finally {
    await rm(archivePath, { force: true });
  }
}
