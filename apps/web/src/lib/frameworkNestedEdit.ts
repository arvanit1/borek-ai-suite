import type { FrameworkChapter } from "./frameworkTypes";

export function replaceArrayItem<T>(items: T[], index: number, value: T): T[] {
  return items.map((item, itemIndex) => (itemIndex === index ? value : item));
}

export function replaceRecordField(
  record: Record<string, unknown>,
  fieldKey: string,
  value: unknown,
): Record<string, unknown> {
  return { ...record, [fieldKey]: value };
}

export function updateChapterBodyValue(
  chapter: FrameworkChapter,
  blockIndex: number,
  fieldKey: string,
  value: unknown,
): FrameworkChapter {
  if (!Array.isArray(chapter.body)) {
    return chapter;
  }
  const body = chapter.body.map((block, index) =>
    index === blockIndex ? replaceRecordField(block, fieldKey, value) : block,
  );
  return { ...chapter, body };
}
