import assert from "node:assert/strict";

import { buildDownloadFilename, mapDeckSlides } from "./deckCenter.js";
import type { DeckCenterResponse } from "./deckTypes.js";

const sampleDeck: DeckCenterResponse = {
  presentation_id: "00000000-0000-4000-8000-000000000010",
  presentation_name: "Invoice 3-Way Match - Automation Proposal",
  version_number: 1,
  status: "ready",
  slides: [
    {
      slide_id: "11111111-1111-4111-8111-111111111111",
      slide_index: 1,
      layout_id: "CONTEXT_01",
      preview_url: "/presentations/x/preview/slides/1.png",
    },
    {
      slide_id: "22222222-2222-4222-8222-222222222222",
      slide_index: 0,
      layout_id: "COVER_01",
      preview_url: "/presentations/x/preview/slides/0.png",
    },
  ],
  pptx_download_url: "/presentations/x/download/pptx",
  pdf_download_url: "/presentations/x/download/pdf",
};

const tiles = mapDeckSlides(sampleDeck);
assert.equal(tiles.length, 2);
assert.equal(tiles[0].slideIndex, 0);
assert.equal(tiles[1].layoutId, "CONTEXT_01");

assert.equal(
  buildDownloadFilename("Invoice 3-Way Match!", "pptx"),
  "Invoice-3-Way-Match.pptx",
);

console.log("deckCenter tests passed");
