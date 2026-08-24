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
