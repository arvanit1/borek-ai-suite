import type { ConversationRef, FrameworkChapter, FrameworkObject } from "./frameworkTypes";

export const EXPECTED_CHAPTER_COUNT = 14;

export function isFrameworkEditable(status: string): boolean {
  return status === "draft" || status === "in_review";
}

export function isFrameworkConfirmed(status: string): boolean {
  return status === "confirmed";
}

export function canEditFramework(rowStatus: string, jsonStatus?: string): boolean {
  if (isFrameworkConfirmed(rowStatus) || (jsonStatus != null && isFrameworkConfirmed(jsonStatus))) {
    return false;
  }
  return isFrameworkEditable(rowStatus) || (jsonStatus != null && isFrameworkEditable(jsonStatus));
}

const SPEAKER_ROLE_LABELS: Record<string, string> = {
  it: "IT",
  hr: "HR",
  qa: "QA",
  erp: "ERP",
  client: "Client",
  dept_head: "Department head",
  department_head: "Department head",
};

const CONVERSATION_ID_RE = /^C(\d+)$/i;
const TURN_POINTER_RE = /^turn[:\-\s]?(\d+)$/i;

function titleCaseWords(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

function formatSpeakerRoleLabel(role: string): string {
  const normalized = role.trim().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
  if (!normalized) {
    return "";
  }
  const mapped = SPEAKER_ROLE_LABELS[normalized.toLowerCase().replace(/\s+/g, "_")];
  if (mapped) {
    return mapped;
  }
  if (/^[A-Z][a-z]+$/.test(role.trim()) || /^[A-Z]{2,}$/.test(role.trim())) {
    return role.trim();
  }
  return titleCaseWords(normalized);
}

function formatConversationLabel(conversationId: string): string {
  const match = CONVERSATION_ID_RE.exec(conversationId.trim());
  if (match) {
    return `conversation ${match[1]}`;
  }
  return conversationId.trim();
}

function formatTurnLabel(excerptPointer: string): string {
  const match = TURN_POINTER_RE.exec(excerptPointer.trim());
  if (match) {
    return `turn ${match[1]}`;
  }
  return excerptPointer.trim();
}

export function formatSourceRefDetail(ref: ConversationRef): string {
  const speaker = formatSpeakerRoleLabel(ref.speaker_role);
  const conversation = formatConversationLabel(ref.conversation_id);
  const turn = formatTurnLabel(ref.excerpt_pointer);
  return [speaker, conversation, turn].filter(Boolean).join(" · ");
}

export function formatSourceRefLabel(ref: ConversationRef): string {
  const speaker = formatSpeakerRoleLabel(ref.speaker_role);
  const conversation = formatConversationLabel(ref.conversation_id);
  const turn = formatTurnLabel(ref.excerpt_pointer);

  if (speaker && conversation && turn) {
    return `From ${speaker} in ${conversation}, ${turn}`;
  }
  if (speaker && conversation) {
    return `From ${speaker} in ${conversation}`;
  }
  if (speaker && turn) {
    return `From ${speaker}, ${turn}`;
  }
  if (conversation && turn) {
    return `From ${conversation}, ${turn}`;
  }
  return speaker || conversation || turn;
}

export function updateChapter(
  framework: FrameworkObject,
  chapterIndex: number,
  chapter: FrameworkChapter,
): FrameworkObject {
  const chapters = framework.chapters.map((current, index) =>
    index === chapterIndex ? chapter : current,
  );
  return { ...framework, chapters };
}

export function updateFrameworkRootField<K extends keyof FrameworkObject>(
  framework: FrameworkObject,
  key: K,
  value: FrameworkObject[K],
): FrameworkObject {
  return { ...framework, [key]: value };
}

export function updateChapterBodyField(
  chapter: FrameworkChapter,
  blockIndex: number,
  fieldKey: string,
  value: string,
): FrameworkChapter {
  if (!Array.isArray(chapter.body)) {
    return chapter;
  }
  const body = chapter.body.map((block, index) =>
    index === blockIndex ? { ...block, [fieldKey]: value } : block,
  );
  return { ...chapter, body };
}

export function updateChapterStringBody(chapter: FrameworkChapter, value: string): FrameworkChapter {
  return { ...chapter, body: value };
}

export function countChaptersWithSourceRefs(framework: FrameworkObject): number {
  return framework.chapters.filter((chapter) => chapter.source_refs.length > 0).length;
}

export function hasExpectedChapterCount(framework: FrameworkObject): boolean {
  return framework.chapters.length === EXPECTED_CHAPTER_COUNT;
}
