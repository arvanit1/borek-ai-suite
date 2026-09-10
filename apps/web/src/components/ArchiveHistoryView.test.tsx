import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ArchiveHistoryView } from "./ArchiveHistoryView.js";
import { type ArchiveCard } from "../lib/archiveHistory.js";

const filed: ArchiveCard = {
  key: "44444444-4444-4444-8444-444444444444",
  opportunityId: "22222222-2222-4222-8222-222222222222",
  presentationId: "33333333-3333-4333-8333-333333333333",
  presentationVersionId: "44444444-4444-4444-8444-444444444444",
  clientName: "Northstar Logistics",
  opportunityName: "Service desk triage",
  filedAt: "2026-09-01T10:05:00Z",
  lifecycle: "filed",
  statusLabel: "Filed",
  journeyLabel: "First contact",
  openHref:
    "/deck-center?opportunityId=22222222-2222-4222-8222-222222222222&presentationId=33333333-3333-4333-8333-333333333333&presentationVersionId=44444444-4444-4444-8444-444444444444",
  pptx: {
    artifactId: "11111111-1111-4111-8111-111111111111",
    path: "/archive/artifacts/11111111-1111-4111-8111-111111111111/download",
    fileName: "northstar-first-contact.pptx",
    kind: "pptx",
  },
  pdf: {
    artifactId: "55555555-5555-4555-8555-555555555555",
    path: "/archive/artifacts/55555555-5555-4555-8555-555555555555/download",
    fileName: "northstar-first-contact.pdf",
    kind: "pdf",
  },
};

const forbidden = /SharePoint|Gamma|sha256|destination_path|repository_ref|engine/i;

function renderView(overrides: Partial<React.ComponentProps<typeof ArchiveHistoryView>> = {}) {
  return renderToStaticMarkup(
    <ArchiveHistoryView
      items={[]}
      loading={false}
      error={null}
      query={{}}
      searchDraft=""
      fromDateDraft=""
      toDateDraft=""
      hasActiveFilters={false}
      downloadingKey={null}
      onSearchChange={() => undefined}
      onFromDateChange={() => undefined}
      onToDateChange={() => undefined}
      onSubmit={(event) => event.preventDefault()}
      onClear={() => undefined}
      onRetry={() => undefined}
      onDownload={() => undefined}
      {...overrides}
    />,
  );
}

const emptyHtml = renderView();
assert.match(emptyHtml, /Archive/);
assert.match(emptyHtml, /Client or opportunity/);
assert.match(emptyHtml, /From date/);
assert.match(emptyHtml, /To date/);
assert.match(emptyHtml, /Nothing filed yet/);
assert.match(emptyHtml, /Filed presentations will appear here/);
assert.match(emptyHtml, /These files are stored in Pitch Factory/);
assert.match(emptyHtml, /Recent presentations/);
assert.doesNotMatch(emptyHtml, forbidden);
assert.doesNotMatch(emptyHtml, /opportunity UUID/i);

const noMatchHtml = renderView({ hasActiveFilters: true, query: { search: "does-not-exist" } });
assert.match(noMatchHtml, /No filed presentations match/);
assert.doesNotMatch(noMatchHtml, forbidden);

const listHtml = renderView({ items: [filed] });
assert.match(listHtml, /Northstar Logistics/);
assert.match(listHtml, /Service desk triage/);
assert.match(listHtml, /Filed 1 Sep 2026/);
assert.match(listHtml, /First contact/);
assert.match(listHtml, />Filed</);
assert.match(listHtml, /Download PowerPoint/);
assert.match(listHtml, /Download PDF/);
assert.match(listHtml, /Open/);
assert.doesNotMatch(listHtml, forbidden);
assert.doesNotMatch(listHtml, />22222222-2222-4222-8222-222222222222</);

const headerSource = readFileSync(fileURLToPath(new URL("./SiteHeader.tsx", import.meta.url)), "utf8");
assert.match(headerSource, /href="\/archive"/);
assert.match(headerSource, />Archive</);

const css = readFileSync(fileURLToPath(new URL("../app/globals.css", import.meta.url)), "utf8");
assert.match(css, /\.archive-filters\s*\{[\s\S]*grid-template-columns:/);
assert.match(css, /\.recent-status-filed\s*\{/);
assert.match(css, /@media \(max-width: 760px\)[\s\S]*\.archive-filters\s*\{[\s\S]*grid-template-columns:\s*1fr/);

console.log("MS-29 archive history UI tests passed");
