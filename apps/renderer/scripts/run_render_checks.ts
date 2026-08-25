#!/usr/bin/env node
/** CLI entry for AT-10 render checks (worker jobs and tests). */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { PresentationPlan } from "../src/contracts.js";
import type { LibreOfficePreviewResult } from "../validation/libreoffice_pipeline.js";
import { runRenderChecks } from "../validation/render_checks.js";

function main(): number {
  const planPath = process.argv[2];
  const previewJsonPath = process.argv[3];

  if (!planPath || !previewJsonPath) {
    console.error("Usage: run_render_checks.ts <presentationPlan.json> <previewResult.json>");
    return 1;
  }

  try {
    const presentationPlan = JSON.parse(readFileSync(resolve(planPath), "utf-8")) as PresentationPlan;
    const preview = JSON.parse(readFileSync(resolve(previewJsonPath), "utf-8")) as LibreOfficePreviewResult;
    const result = runRenderChecks({ presentationPlan, preview });
    process.stdout.write(`${JSON.stringify(result)}\n`);
    return result.status === "VALID" ? 0 : 1;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const result = {
      status: "VALIDATION_FAILED",
      issues: [{ code: "RENDER_EXCEPTION", message }],
      errorCode: "RENDER_VALIDATION_FAILED",
    };
    process.stdout.write(`${JSON.stringify(result)}\n`);
    console.error(message);
    return 1;
  }
}

process.exit(main());
