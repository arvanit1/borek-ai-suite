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
assert.match(formHtml, /Personalise this presentation/);
assert.match(formHtml, /Optional/);
assert.match(formHtml, /leave this section empty and continue directly to transcripts/i);
assert.doesNotMatch(formHtml, /client_information_files/);
assert.match(formHtml, /Location requirements/);
assert.match(formHtml, /Add contact/);
assert.doesNotMatch(formHtml, /Client contacts/);
assert.match(formHtml, /Create opportunity/);

const existingHtml = renderToStaticMarkup(
  <OpportunityForm
    disabled={false}
    existing={{
      client_name: "Acme",
      opportunity_name: "Rollout",
      department: "Sales",
      language: "en",
      pii_redaction_enabled: true,
      additional_client_information: null,
    }}
    onSubmit={async () => undefined}
    onUpdateClientInformation={async () => undefined}
  />,
);
assert.match(existingHtml, /Save personalisation/);
assert.doesNotMatch(existingHtml, /id="client_name"/);
assert.doesNotMatch(existingHtml, /id="location_requirements"[^>]*disabled/);
assert.doesNotMatch(existingHtml, /id="client_notes"[^>]*disabled/);
assert.match(existingHtml, /Add contact/);
assert.doesNotMatch(existingHtml, /Client contacts/);

const createdWithoutContacts = renderToStaticMarkup(
  <OpportunityForm
    existing={{
      client_name: "Acme Corporation",
      opportunity_name: "Automation rollout",
      department: "Sales",
      language: "en",
      pii_redaction_enabled: true,
      additional_client_information: null,
    }}
    onSubmit={async () => undefined}
  />,
);
assert.doesNotMatch(createdWithoutContacts, /Client contacts/);
assert.doesNotMatch(createdWithoutContacts, /Add contact/);

const createdWithContacts = renderToStaticMarkup(
  <OpportunityForm
    existing={{
      client_name: "Acme Corporation",
      opportunity_name: "Automation rollout",
      department: "Sales",
      language: "en",
      pii_redaction_enabled: true,
      additional_client_information: {
        location_requirements: [],
        constraints: [],
        contacts: [{ name: "Ada Lovelace", role: "Sponsor", email: null, phone: null }],
        priorities: [],
        notes: null,
      },
    }}
    onSubmit={async () => undefined}
  />,
);
assert.match(createdWithContacts, /Client contacts/);
assert.match(createdWithContacts, /Ada Lovelace/);

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

const uploadPanelSource = readFileSync(
  fileURLToPath(new URL("./TranscriptUploadPanel.tsx", import.meta.url)),
  "utf8",
);
assert.doesNotMatch(uploadPanelSource, /PipelineStepper|UploadStepper/);
assert.match(uploadPanelSource, /Selected for this presentation/);
assert.match(uploadPanelSource, /Change output/);
assert.match(uploadPanelSource, /Continue to customer story/);
assert.match(uploadPanelSource, /journeyStage !== "first_contact"/);

const cssPath = fileURLToPath(new URL("../app/globals.css", import.meta.url));
const css = readFileSync(cssPath, "utf8");
assert.match(css, /\.client-logo-upload\s*\{[\s\S]*grid-template-columns:/);
assert.match(css, /\.client-logo-card-footer\s*\{[\s\S]*justify-content:\s*space-between/);
assert.match(css, /\.client-information-grid,[\s\S]*\.client-logo-upload\s*\{[\s\S]*grid-template-columns:\s*1fr/);

console.log("MS-27 intake UI tests passed");
