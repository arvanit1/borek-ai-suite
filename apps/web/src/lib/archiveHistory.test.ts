import assert from "node:assert/strict";

import {
  ARCHIVE_O2_NOTE,
  archiveDateRangeError,
  archiveEmptyCopy,
  buildArchiveCards,
  buildArchiveListPath,
  formatArchiveDate,
  hasActiveArchiveFilters,
  journeyStageLabel,
  type ArchiveArtifact,
} from "./archiveHistory.js";

function artifact(overrides: Partial<ArchiveArtifact> = {}): ArchiveArtifact {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    opportunity_id: "22222222-2222-4222-8222-222222222222",
    presentation_id: "33333333-3333-4333-8333-333333333333",
    presentation_version_id: "44444444-4444-4444-8444-444444444444",
    artifact_kind: "pptx",
    content_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    file_name: "northstar-first-contact.pptx",
    size_bytes: 2048,
    sha256: "a".repeat(64),
    status: "filed",
    client_name: "Northstar Logistics",
    opportunity_name: "Service desk triage",
    approved_by: "user-a",
    approved_at: "2026-09-01T10:00:00Z",
    filed_at: "2026-09-01T10:05:00Z",
    journey_stage: "first_contact",
    download_url: "/archive/artifacts/11111111-1111-4111-8111-111111111111/download",
    ...overrides,
  };
}

const pptx = artifact();
const pdf = artifact({
  id: "55555555-5555-4555-8555-555555555555",
  artifact_kind: "pdf",
  file_name: "northstar-first-contact.pdf",
  download_url: "/archive/artifacts/55555555-5555-4555-8555-555555555555/download",
});
const later = artifact({
  id: "66666666-6666-4666-8666-666666666666",
  presentation_version_id: "77777777-7777-4777-8777-777777777777",
  opportunity_name: "Warehouse rollout",
  journey_stage: "deepening",
  filed_at: "2026-09-08T12:00:00Z",
  download_url: "/archive/artifacts/66666666-6666-4666-8666-666666666666/download",
});
const foreign = artifact({
  id: "88888888-8888-4888-8888-888888888888",
  presentation_version_id: "99999999-9999-4999-8999-999999999999",
  client_name: "Other Client",
  opportunity_name: "Hidden opportunity",
  approved_by: "user-b",
  download_url: "/archive/artifacts/88888888-8888-4888-8888-888888888888/download",
});

const cards = buildArchiveCards([pdf, later, pptx, foreign], "user-a");
assert.deepEqual(
  cards.map((card) => card.opportunityName),
  ["Warehouse rollout", "Service desk triage"],
);
assert.equal(cards[1]?.pptx?.path, pptx.download_url);
assert.equal(cards[1]?.pdf?.path, pdf.download_url);
assert.equal(cards[1]?.statusLabel, "Filed");
assert.equal(cards[1]?.journeyLabel, "First contact");
assert.equal(cards[0]?.journeyLabel, "Deepening");
assert.ok(!cards.some((card) => card.clientName === "Other Client"));

const serialized = JSON.stringify(cards);
assert.doesNotMatch(serialized, /sha256/);
assert.doesNotMatch(serialized, /approved_by/);
assert.doesNotMatch(serialized, /Gamma/i);
assert.doesNotMatch(serialized, /SharePoint/i);
assert.doesNotMatch(serialized, /destination_path/);
assert.doesNotMatch(serialized, /repository_ref/);

assert.equal(buildArchiveListPath({}), "/archive/artifacts");
assert.equal(
  buildArchiveListPath({ search: "invoice", fromDate: "2026-09-01", toDate: "2026-09-10" }),
  "/archive/artifacts?search=invoice&from_date=2026-09-01&to_date=2026-09-10",
);
assert.ok(!buildArchiveListPath({ search: "Northstar" }).includes("opportunityId"));
assert.ok(!buildArchiveListPath({ search: "Northstar" }).includes("22222222"));

assert.equal(hasActiveArchiveFilters({}), false);
assert.equal(hasActiveArchiveFilters({ search: "  " }), false);
assert.equal(hasActiveArchiveFilters({ search: "Northstar" }), true);
assert.equal(hasActiveArchiveFilters({ fromDate: "2026-09-01" }), true);
assert.equal(archiveDateRangeError("2026-09-10", "2026-09-01"), "The From date must be on or before the To date.");
assert.equal(archiveDateRangeError("2026-09-01", "2026-09-10"), null);

assert.equal(journeyStageLabel("concretisation"), "Concretisation");
assert.equal(journeyStageLabel("unknown"), undefined);
assert.equal(formatArchiveDate("2026-09-01T10:05:00Z"), "1 Sep 2026");

const empty = archiveEmptyCopy(false);
assert.match(empty.title, /appear here/i);
assert.doesNotMatch(empty.detail, /SharePoint/i);
assert.doesNotMatch(empty.detail, /UUID/i);

const noMatch = archiveEmptyCopy(true);
assert.match(noMatch.title, /No filed presentations match/);

assert.match(ARCHIVE_O2_NOTE, /Pitch Factory/);
assert.doesNotMatch(ARCHIVE_O2_NOTE, /SharePoint/i);
assert.doesNotMatch(ARCHIVE_O2_NOTE, /Gamma/i);

const unavailable = buildArchiveCards([
  artifact({
    download_url: null,
    presentation_version_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  }),
]);
assert.equal(unavailable[0]?.statusLabel, "Not available");
assert.equal(unavailable[0]?.pptx, undefined);

console.log("MS-29 archive history mapping tests passed");
