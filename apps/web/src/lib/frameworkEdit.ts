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

export function formatSourceRefLabel(ref: ConversationRef): string {
  return `${ref.conversation_id} · ${ref.speaker_role} · ${ref.excerpt_pointer}`;
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
