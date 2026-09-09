import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ClientLogoUpload } from "./ClientLogoUpload.js";
import { OpportunityForm } from "./OpportunityForm.js";

const formHtml = renderToStaticMarkup(
  <OpportunityForm disabled={false} onSubmit={async () => undefined} />,
);
assert.match(formHtml, /Additional client information/);
assert.match(formHtml, /Optional/);
assert.match(formHtml, /leave this section empty and continue directly to transcripts/i);
assert.match(formHtml, /Location requirements/);
assert.match(formHtml, /Client contacts/);
assert.match(formHtml, /Create opportunity/);

const logoHtml = renderToStaticMarkup(
  <ClientLogoUpload accessToken="token" opportunityId="opportunity" />,
);
assert.match(logoHtml, /Client logo/);
assert.match(logoHtml, /Optional/);
assert.match(logoHtml, /PNG, JPEG, or WebP/);
assert.match(logoHtml, /5 MiB maximum/);
assert.match(logoHtml, /cover and closing/);
assert.match(logoHtml, /bottom-right/);
assert.match(logoHtml, /Client name/);
assert.match(logoHtml, /src="\/logo.webp"/);
assert.doesNotMatch(logoHtml, /64-4096/);
assert.doesNotMatch(logoHtml, /Gamma/i);

const cssPath = fileURLToPath(new URL("../app/globals.css", import.meta.url));
const css = readFileSync(cssPath, "utf8");
assert.match(css, /\.client-logo-upload\s*\{[\s\S]*grid-template-columns:/);
assert.match(css, /\.client-logo-card-footer\s*\{[\s\S]*justify-content:\s*space-between/);
assert.match(css, /\.client-information-grid,[\s\S]*\.client-logo-upload\s*\{[\s\S]*grid-template-columns:\s*1fr/);

console.log("MS-27 intake UI tests passed");
