import assert from "node:assert/strict";

import {
  ALLOWED_TRANSCRIPT_EXTENSIONS,
  getFileExtension,
  validateTranscriptFileName,
} from "./transcriptFormats.js";

assert.deepEqual(ALLOWED_TRANSCRIPT_EXTENSIONS, [".txt", ".vtt", ".srt", ".docx"]);

assert.equal(getFileExtension("notes.TXT"), ".txt");
assert.equal(getFileExtension("noextension"), "");
assert.equal(getFileExtension(".hidden"), "");

for (const ext of ALLOWED_TRANSCRIPT_EXTENSIONS) {
  const result = validateTranscriptFileName(`meeting${ext}`);
  assert.equal(result.ok, true, ext);
  assert.equal(result.extension, ext);
}

const rejected = validateTranscriptFileName("report.pdf");
assert.equal(rejected.ok, false);
assert.equal(rejected.extension, ".pdf");
assert.match(rejected.reason ?? "", /\.pdf/);

const noExt = validateTranscriptFileName("transcript");
assert.equal(noExt.ok, false);
assert.equal(noExt.extension, "");

console.log("transcriptFormats tests passed");
