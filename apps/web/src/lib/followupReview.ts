export type FollowupSalutationStyle = "informal" | "formal";

export interface FollowupRecipient {
  email: string;
  first_name: string | null;
  last_name: string | null;
  salutation: string | null;
  kind: "to" | "cc";
  primary: boolean;
}

export interface FollowupSenderProfile {
  name: string;
  role: string;
  email: string;
}

export interface FollowupProjectStatics {
  project_name: string;
  client_short: string;
  salutation_style: FollowupSalutationStyle;
  standard_recipients: FollowupRecipient[];
  sender_profile: FollowupSenderProfile;
}

export interface FollowupExtraction {
  schema_version: "1.0";
  prompt_version: string;
  meeting_topic: string;
  meeting_date: string;
  project_name: string | null;
  participants: Array<{ name: string; organisation: string | null }>;
  key_points: string[];
  decisions: string[];
  action_items: Array<{ action: string; owner: string; due: string }>;
  open_questions: string[];
  next_meeting: { date: string; time: string } | null;
  confidence: { key_points: "high" | "low"; action_items: "high" | "low" };
  review_flags: string[];
}

export interface FollowupDraft {
  subject: string;
  body: string;
  review_flags: string[];
  attachment_name: string | null;
  status: "draft" | "reviewed" | "sent";
}

export const FOLLOWUP_CHECKLIST = [
  { id: "names_dates", label: "Every name and date is correct" },
  { id: "owners", label: "Every action has a real owner" },
  { id: "meeting_only", label: "Nothing was added that was not said in the meeting" },
  { id: "tone", label: "Tone matches this client's Du/Sie style" },
  { id: "attachment", label: "No attachment is referenced, or every referenced attachment is attached" },
] as const;

export type FollowupChecklistId = (typeof FOLLOWUP_CHECKLIST)[number]["id"];
export type FollowupChecklistState = Record<FollowupChecklistId, boolean>;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function emptyFollowupProjectStatics(): FollowupProjectStatics {
  return {
    project_name: "",
    client_short: "",
    salutation_style: "informal",
    standard_recipients: [
      {
        email: "",
        first_name: null,
        last_name: null,
        salutation: null,
        kind: "to",
        primary: true,
      },
    ],
    sender_profile: { name: "", role: "", email: "" },
  };
}

export function primaryFollowupRecipient(statics: FollowupProjectStatics): FollowupRecipient {
  return (
    statics.standard_recipients.find((recipient) => recipient.kind === "to" && recipient.primary) ??
    statics.standard_recipients[0] ??
    emptyFollowupProjectStatics().standard_recipients[0]
  );
}

export function validateFollowupProjectStatics(statics: FollowupProjectStatics): string[] {
  const errors: string[] = [];
  if (!statics.project_name.trim()) errors.push("Enter the exact project name.");
  if (!statics.client_short.trim()) errors.push("Enter the client short name.");
  const primary = statics.standard_recipients.filter(
    (recipient) => recipient.kind === "to" && recipient.primary,
  );
  if (primary.length !== 1) {
    errors.push("Choose exactly one primary intended recipient.");
  } else {
    if (!EMAIL_PATTERN.test(primary[0].email.trim())) errors.push("Enter the primary recipient email.");
    if (statics.salutation_style === "informal" && !primary[0].first_name?.trim()) {
      errors.push("Du/informal tone needs the recipient's first name.");
    }
    if (
      statics.salutation_style === "formal" &&
      (!primary[0].salutation?.trim() || !primary[0].last_name?.trim())
    ) {
      errors.push("Sie/formal tone needs a salutation and last name.");
    }
  }
  if (
    statics.standard_recipients.some(
      (recipient) => !EMAIL_PATTERN.test(recipient.email.trim()),
    )
  ) {
    errors.push("Every intended recipient needs a valid email.");
  }
  if (!statics.sender_profile.name.trim()) errors.push("Enter the sender name.");
  if (!statics.sender_profile.role.trim()) errors.push("Enter the sender role.");
  if (!EMAIL_PATTERN.test(statics.sender_profile.email.trim())) errors.push("Enter the sender email.");
  return errors;
}

function greeting(statics: FollowupProjectStatics): string {
  const recipient = primaryFollowupRecipient(statics);
  return statics.salutation_style === "formal"
    ? `Dear ${recipient.salutation} ${recipient.last_name},`
    : `Hi ${recipient.first_name},`;
}

function actionDue(due: string): string {
  return due === "TBD" ? "date to be confirmed" : due;
}

export function renderFollowupDraft(
  extraction: FollowupExtraction,
  statics: FollowupProjectStatics,
  attachmentName: string | null = null,
): FollowupDraft {
  const lines = [
    greeting(statics),
    "",
    `thank you for your time on ${extraction.meeting_date}. Below is a short summary of what we agreed, so we all work from the same picture.`,
  ];

  if (extraction.key_points.length > 0) {
    lines.push("", "Key points", ...extraction.key_points.slice(0, 3).map((item) => `- ${item}`));
  }
  if (extraction.decisions.length > 0) {
    lines.push(
      "",
      "Decisions",
      ...extraction.decisions.map((item) => `- ${item} (agreed ${extraction.meeting_date})`),
    );
  }
  if (extraction.action_items.length > 0) {
    lines.push(
      "",
      "Next steps",
      ...extraction.action_items.slice(0, 5).map(
        (item) => `- ${item.action} - ${item.owner}, by ${actionDue(item.due)}`,
      ),
    );
  } else {
    lines.push("", "No action items were agreed for now.");
  }
  if (extraction.open_questions.length > 0) {
    lines.push("", "Open from our side", ...extraction.open_questions.map((item) => `- ${item}`));
  }
  if (extraction.next_meeting) {
    lines.push(
      "",
      `Next session: ${extraction.next_meeting.date}, ${extraction.next_meeting.time}.`,
    );
  }
  if (attachmentName) {
    lines.push("", `Attached you will find ${attachmentName} with the full detail.`);
  }
  lines.push(
    "",
    "If anything here does not match your understanding, just let me know and I will correct it.",
    "",
    "Best regards",
    statics.sender_profile.name,
    `${statics.sender_profile.role} - BOREK`,
  );

  return {
    subject: `${statics.project_name} \u2014 Follow-up ${extraction.meeting_topic} (${extraction.meeting_date})`,
    body: lines.join("\n"),
    review_flags: [...extraction.review_flags],
    attachment_name: attachmentName,
    status: "draft",
  };
}

export function followupContentWordCount(body: string): number {
  const withoutGreeting = body.replace(/^\s*[^\n]+,\s*\n/, "");
  const content = withoutGreeting.split(/\n\s*Best regards\s*\n/i)[0];
  return content.trim() ? content.trim().split(/\s+/).length : 0;
}

export function followupDraftErrors(draft: FollowupDraft): string[] {
  const errors: string[] = [];
  if (!draft.subject.trim()) errors.push("Subject cannot be empty.");
  if (!draft.body.trim()) errors.push("Email body cannot be empty.");
  if (/\{\{[^}]+\}\}/.test(`${draft.subject}\n${draft.body}`)) {
    errors.push("Remove every unresolved template placeholder.");
  }
  if (followupContentWordCount(draft.body) > 150) {
    errors.push("Keep the email body to 150 words or fewer.");
  }
  return errors;
}

export function emptyFollowupChecklist(): FollowupChecklistState {
  return {
    names_dates: false,
    owners: false,
    meeting_only: false,
    tone: false,
    attachment: false,
  };
}

export function canConfirmFollowupReview(
  draft: FollowupDraft | null,
  statics: FollowupProjectStatics,
  checklist: FollowupChecklistState,
  acknowledgedFlags: ReadonlySet<string>,
  staticsSaved: boolean,
): boolean {
  if (!draft || draft.status !== "draft" || !staticsSaved) return false;
  if (validateFollowupProjectStatics(statics).length || followupDraftErrors(draft).length) return false;
  if (FOLLOWUP_CHECKLIST.some((item) => !checklist[item.id])) return false;
  return draft.review_flags.every((flag) => acknowledgedFlags.has(flag));
}
