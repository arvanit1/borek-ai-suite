import assert from "node:assert/strict";

import actionOverflow from "../../../../packages/contracts/fixtures/followup_extraction/action_overflow.json";
import noDeadline from "../../../../packages/contracts/fixtures/followup_extraction/no_deadline.json";
import unownedCommitment from "../../../../packages/contracts/fixtures/followup_extraction/unowned_commitment.json";
import workshopClear from "../../../../packages/contracts/fixtures/followup_extraction/workshop_clear.json";
import {
  canConfirmFollowupReview,
  emptyFollowupChecklist,
  followupContentWordCount,
  renderFollowupDraft,
  validateFollowupProjectStatics,
  type FollowupExtraction,
  type FollowupProjectStatics,
} from "./followupReview.js";

const informal: FollowupProjectStatics = {
  project_name: "Acme Invoice Pilot",
  client_short: "Acme",
  salutation_style: "informal",
  standard_recipients: [
    {
      email: "markus@example.com",
      first_name: "Markus",
      last_name: "Weber",
      salutation: "Mr",
      kind: "to",
      primary: true,
    },
  ],
  sender_profile: {
    name: "Lena Hoffmann",
    role: "Project Lead",
    email: "lena@borek.example",
  },
};

const clear = workshopClear as FollowupExtraction;
const draft = renderFollowupDraft(clear, informal);
assert.match(draft.subject, /Acme Invoice Pilot/);
assert.match(draft.body, /^Hi Markus,/);
for (const point of clear.key_points) assert.match(draft.body, new RegExp(point));
for (const action of clear.action_items) assert.match(draft.body, new RegExp(action.action));
assert.match(draft.body, /Decisions/);
assert.doesNotMatch(draft.body, /Open from our side/);
assert.doesNotMatch(draft.body, /Next session:/);
assert.doesNotMatch(draft.body, /\{\{/);
assert.ok(followupContentWordCount(draft.body) <= 150);

const formal = structuredClone(informal);
formal.salutation_style = "formal";
formal.standard_recipients[0].first_name = null;
const formalDraft = renderFollowupDraft(clear, formal);
assert.match(formalDraft.body, /^Dear Mr Weber,/);
assert.equal(validateFollowupProjectStatics(formal).length, 0);

const noActions = renderFollowupDraft(unownedCommitment as FollowupExtraction, informal);
assert.match(noActions.body, /No action items were agreed for now/);
assert.match(noActions.body, /Open from our side/);
assert.doesNotMatch(noActions.body, /Next steps\n/);

const tbd = renderFollowupDraft(noDeadline as FollowupExtraction, informal);
assert.match(tbd.body, /date to be confirmed/);
assert.doesNotMatch(tbd.body, /by TBD/);

const flagged = renderFollowupDraft(actionOverflow as FollowupExtraction, informal);
const checks = {
  ...emptyFollowupChecklist(),
  names_dates: true,
  owners: true,
  meeting_only: true,
  tone: true,
  attachment: true,
};
assert.equal(canConfirmFollowupReview(flagged, informal, checks, new Set(), true), false);
assert.equal(
  canConfirmFollowupReview(
    flagged,
    informal,
    checks,
    new Set(["action_overflow_see_protocol"]),
    true,
  ),
  true,
);
assert.equal(canConfirmFollowupReview(draft, informal, checks, new Set(), false), false);
assert.equal(canConfirmFollowupReview(draft, informal, checks, new Set(), true), true);

assert.equal(
  canConfirmFollowupReview(draft, informal, { ...checks, attachment: false }, new Set(), true),
  false,
);

const malformed = structuredClone(informal);
malformed.standard_recipients.push({
  email: "not@valid",
  first_name: null,
  last_name: null,
  salutation: null,
  kind: "cc",
  primary: false,
});
assert.match(validateFollowupProjectStatics(malformed).join(" "), /Every intended recipient/);

console.log("MS-32 follow-up template and review rules tests passed");
