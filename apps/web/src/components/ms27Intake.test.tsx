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
assert.match(logoHtml, /continue directly to transcripts/);
assert.match(logoHtml, /No logo added/);

const cssPath = fileURLToPath(new URL("../app/globals.css", import.meta.url));
const css = readFileSync(cssPath, "utf8");
assert.match(css, /\.client-logo-upload\s*\{[\s\S]*grid-template-columns:/);
assert.match(css, /\.client-information-grid,[\s\S]*\.client-logo-upload\s*\{[\s\S]*grid-template-columns:\s*1fr/);

console.log("MS-27 intake UI tests passed");
