export type FrameworkRenderFormat = "pdf" | "docx" | "html";

export function buildFrameworkRenderPath(
  frameworkVersionId: string,
  format: FrameworkRenderFormat,
  language = "en",
): string {
  const params = new URLSearchParams({ format });
  if (language && !language.toLowerCase().startsWith("en")) {
    params.set("lang", language);
  }
  return `/frameworks/${frameworkVersionId}/render?${params.toString()}`;
}

export function buildFrameworkDownloadFilename(
  frameworkTitle: string,
  format: "pdf" | "docx",
): string {
  const safe =
    frameworkTitle.trim().replace(/[^\w\- ]+/g, "").replace(/\s+/g, "-") || "framework";
  const extension = format === "docx" ? "docx" : "pdf";
  return `${safe}.${extension}`;
}
