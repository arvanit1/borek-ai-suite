import assert from "node:assert/strict";

import {
  additionalClientInformationError,
  appendClientInformationFileNote,
  CLIENT_INFORMATION_FILE_MAX_BYTES,
  CLIENT_LOGO_MAX_BYTES,
  compactAdditionalClientInformation,
  removeClientInformationFileNote,
  validateClientInformationFile,
  validateClientLogoFile,
} from "./clientIntake.js";

assert.equal(validateClientLogoFile({ name: "brand.png", type: "image/png", size: 1 }).ok, true);
assert.equal(validateClientLogoFile({ name: "brand.JPG", type: "image/jpeg", size: 1 }).ok, true);
assert.equal(validateClientLogoFile({ name: "brand.webp", type: "image/webp", size: 1 }).ok, true);
assert.equal(
  validateClientLogoFile({ name: "brand.png", type: "image/png", size: CLIENT_LOGO_MAX_BYTES }).ok,
  true,
);
assert.equal(validateClientLogoFile({ name: "brand.svg", type: "image/svg+xml", size: 1 }).ok, false);
assert.equal(validateClientLogoFile({ name: "brand.png", type: "image/jpeg", size: 1 }).ok, false);
assert.equal(validateClientLogoFile({ name: "brand.png", type: "image/png", size: 0 }).ok, false);
assert.match(
  validateClientLogoFile({ name: "brand.png", type: "image/png", size: CLIENT_LOGO_MAX_BYTES + 1 }).reason ?? "",
  /5 MiB/,
);

assert.equal(
  compactAdditionalClientInformation({
    location_requirements: [],
    constraints: [],
    contacts: [],
    priorities: [],
    notes: "  ",
  }),
  undefined,
);

assert.deepEqual(
  compactAdditionalClientInformation({
    location_requirements: [" EU hosting ", ""],
    constraints: ["  Go-live by Q4"],
    contacts: [
      { name: " Ada ", role: " Sponsor ", email: " ", phone: null },
      { name: "", role: null, email: null, phone: null },
    ],
    priorities: [" Accuracy ", "  "],
    notes: " Procurement pending. ",
  }),
  {
    location_requirements: ["EU hosting"],
    constraints: ["Go-live by Q4"],
    contacts: [{ name: "Ada", role: "Sponsor", email: null, phone: null }],
    priorities: ["Accuracy"],
    notes: "Procurement pending.",
  },
);

assert.match(
  additionalClientInformationError({
    location_requirements: [],
    constraints: [],
    contacts: [{ name: "  ", role: "Sponsor", email: null, phone: null }],
    priorities: [],
    notes: null,
  }) ?? "",
  /name for each client contact/i,
);
assert.equal(
  additionalClientInformationError({
    location_requirements: [],
    constraints: [],
    contacts: [{ name: "  ", role: null, email: null, phone: null }],
    priorities: [],
    notes: null,
  }),
  undefined,
);

assert.equal(validateClientInformationFile({ name: "brief.txt", size: 12 }).ok, true);
assert.equal(validateClientInformationFile({ name: "brief.md", size: 12 }).ok, true);
assert.equal(validateClientInformationFile({ name: "brief.pdf", size: 12 }).ok, false);
assert.equal(validateClientInformationFile({ name: "brief.txt", size: 0 }).ok, false);
assert.equal(
  validateClientInformationFile({ name: "brief.txt", size: CLIENT_INFORMATION_FILE_MAX_BYTES + 1 }).ok,
  false,
);

const imported = appendClientInformationFileNote("Manual note.", "brief.txt", "EU hosting required.");
assert.equal(imported.error, undefined);
assert.match(imported.notes, /Manual note/);
assert.match(imported.notes, /--- brief.txt ---/);
assert.match(imported.notes, /EU hosting required/);
assert.equal(removeClientInformationFileNote(imported.notes, "brief.txt"), "Manual note.");

console.log("MS-27 client intake tests passed");
