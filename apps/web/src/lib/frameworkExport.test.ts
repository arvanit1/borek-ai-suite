import assert from "node:assert/strict";
import test from "node:test";

import {
  buildFrameworkDownloadFilename,
  buildFrameworkRenderPath,
} from "./frameworkExport.js";

test("buildFrameworkRenderPath defaults to pdf in English", () => {
  assert.equal(
    buildFrameworkRenderPath("fw-123", "pdf"),
    "/frameworks/fw-123/render?format=pdf",
  );
});

test("buildFrameworkRenderPath includes docx format", () => {
  assert.equal(
    buildFrameworkRenderPath("fw-123", "docx"),
    "/frameworks/fw-123/render?format=docx",
  );
});

test("buildFrameworkRenderPath adds lang for non-English", () => {
  assert.equal(
    buildFrameworkRenderPath("fw-123", "docx", "de"),
    "/frameworks/fw-123/render?format=docx&lang=de",
  );
});

test("buildFrameworkDownloadFilename sanitizes title", () => {
  assert.equal(
    buildFrameworkDownloadFilename("Invoice 3-Way Match!", "docx"),
    "Invoice-3-Way-Match.docx",
  );
  assert.equal(buildFrameworkDownloadFilename("", "pdf"), "framework.pdf");
  assert.equal(
    buildFrameworkDownloadFilename("Invoice Automation", "docx", "de"),
    "Invoice-Automation-DE.docx",
  );
});
