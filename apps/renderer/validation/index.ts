/** AT-9/AT-10 renderer validation exports. */

export {
  DEFAULT_RENDER_DPI,
  LibreOfficePipelineError,
  SLIDE_IMAGE_PREFIX,
  expectedPdfPath,
  formatSlideImageFilename,
  normalizeSlideImagePaths,
  resolvePdftoppmCommand,
  resolveSofficeCommand,
  runLibreOfficePreviewPipeline,
} from "./libreoffice_pipeline.js";
export type { LibreOfficePreviewOptions, LibreOfficePreviewResult } from "./libreoffice_pipeline.js";
export {
  BLANK_SLIDE_MIN_NON_WHITE_RATIO,
  RENDER_VALIDATION_FAILED,
  isBlankSlideImage,
  parseSlideImageNumber,
  runRenderChecks,
} from "./render_checks.js";
export type {
  RenderCheckInput,
  RenderCheckIssue,
  RenderCheckIssueCode,
  RenderCheckResult,
} from "./render_checks.js";
