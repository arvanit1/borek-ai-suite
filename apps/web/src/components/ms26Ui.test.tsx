import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { formatSourceRefDetail, formatSourceRefLabel } from "../lib/frameworkEdit.js";
import { SlidePreviewCard } from "./SlidePreviewCard.js";

const slideId = "59b8bf50-48a7-4c41-97c4-cd8ac1fa76de";
const slideHtml = renderToStaticMarkup(
  <SlidePreviewCard
    accessToken="token"
    slideId={slideId}
    slideIndex={0}
    layoutId="ARCHITECTURE_01"
    previewPath={null}
  />,
);

assert.doesNotMatch(slideHtml, new RegExp(slideId));
assert.doesNotMatch(slideHtml, /ARCHITECTURE_01/);
assert.match(slideHtml, /Architecture/);

const sourceRef = {
  conversation_id: "01990f5c-40a9-7000-8f2d-65f4f5f418ed",
  speaker_role: "client",
  excerpt_pointer: "6f325506-2196-4f1a-b12f-a5bce42d0904",
};
const sourceLabel = formatSourceRefLabel(sourceRef);
const sourceDetail = formatSourceRefDetail(sourceRef);
assert.equal(sourceLabel, "From Client in source conversation, source excerpt");
assert.equal(sourceDetail, "Client · source conversation · source excerpt");
assert.doesNotMatch(`${sourceLabel} ${sourceDetail}`, /[0-9a-f]{8}-[0-9a-f-]{27,}/i);

const css = readFileSync("src/app/globals.css", "utf8");
assert.match(css, /@media \(max-width: 1024px\)[\s\S]*?\.framework-chapter-nav-open\s*{\s*display: grid;/);
assert.match(css, /grid-template-columns:\s*repeat\(auto-fill, minmax\(min\(100%, 240px\), 1fr\)\)/);
assert.match(css, /\.site-user[\s\S]*?display:\s*none;/);
assert.match(css, /overflow-wrap:\s*anywhere;/);

assert.match(css, /--font-body:\s*"Segoe UI"/);
assert.match(css, /--font-heading:\s*"Segoe UI"/);
assert.match(css, /html \*,\s*html \*::before,\s*html \*::after\s*\{[\s\S]*?font-family:\s*inherit;/);
assert.match(
  css,
  /h1,\s*h2,\s*h3,\s*h4,\s*h5,\s*h6\s*\{[\s\S]*?font-family:\s*var\(--font-heading\);/,
);
assert.match(
  css,
  /\.page-header h1,\s*\.app-page-header h1,\s*\.auth-main-header h1,\s*\.pipeline-empty-page h1/,
);
assert.doesNotMatch(css, /font-weight:\s*650/);

console.log("MS-26 responsive UI tests passed");
