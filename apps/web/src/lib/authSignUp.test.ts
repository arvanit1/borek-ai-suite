import assert from "node:assert/strict";

import {
  DUPLICATE_EMAIL_MESSAGE,
  isDuplicateSignUpEmail,
  resolveSignUpErrorMessage,
} from "./authSignUp.js";

assert.equal(isDuplicateSignUpEmail(null), false);
assert.equal(isDuplicateSignUpEmail(undefined), false);
assert.equal(isDuplicateSignUpEmail({ identities: [{ id: "abc" }] }), false);
assert.equal(isDuplicateSignUpEmail({ identities: [] }), true);

assert.equal(
  resolveSignUpErrorMessage("User already registered"),
  DUPLICATE_EMAIL_MESSAGE,
);
assert.equal(
  resolveSignUpErrorMessage("Network error"),
  "Network error",
);

process.stdout.write("authSignUp tests passed\n");
