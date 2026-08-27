import assert from "node:assert/strict";

import {
  countByStatus,
  createQueueItem,
  createQueueItems,
  getUploadableItems,
  hasUploadableItems,
  updateQueueItem,
} from "./uploadQueue.js";

function makeFile(name: string, type = "text/plain"): File {
  return new File(["sample"], name, { type });
}

const validTxt = makeFile("call.txt");
const validVtt = makeFile("call.vtt", "text/vtt");
const invalidPdf = makeFile("slides.pdf", "application/pdf");

const singleValid = createQueueItem(validTxt);
assert.equal(singleValid.status, "pending");
assert.equal(singleValid.validation.ok, true);

const singleInvalid = createQueueItem(invalidPdf);
assert.equal(singleInvalid.status, "rejected");
assert.equal(singleInvalid.validation.ok, false);
assert.ok(singleInvalid.errorMessage);

const mixed = createQueueItems([validTxt, invalidPdf, validVtt]);
assert.equal(mixed.length, 3);
assert.deepEqual(countByStatus(mixed), {
  rejected: 1,
  pending: 2,
  uploading: 0,
  success: 0,
  error: 0,
});

const uploadable = getUploadableItems(mixed);
assert.equal(uploadable.length, 2);
assert.ok(hasUploadableItems(mixed));
assert.ok(!hasUploadableItems([singleInvalid]));

const updated = updateQueueItem(mixed, uploadable[0].id, {
  status: "uploading",
});
assert.equal(updated.find((item) => item.id === uploadable[0].id)?.status, "uploading");
assert.equal(
  updated.filter((item) => item.status === "pending").length,
  1,
);

console.log("uploadQueue tests passed");
