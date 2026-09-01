import type { ConversationRef, FrameworkChapter } from "./frameworkTypes";

export function isConversationRef(value: unknown): value is ConversationRef {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return (
    typeof record.conversation_id === "string" &&
    typeof record.speaker_role === "string" &&
    typeof record.excerpt_pointer === "string"
  );
}

export function sourceRefsFromValue(value: unknown): ConversationRef[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isConversationRef);
}

export function sourceRefsForBlock(block: Record<string, unknown>): ConversationRef[] {
  return sourceRefsFromValue(block.source_refs);
}

export function sourceRefsForFactDisplay(chapter: FrameworkChapter, block?: Record<string, unknown>): ConversationRef[] {
  if (block) {
    return sourceRefsForBlock(block);
  }
  return chapter.source_refs;
}

export function countFactSourceRefs(chapter: FrameworkChapter): number {
  if (Array.isArray(chapter.body)) {
    return chapter.body.reduce(
      (total, block) => total + sourceRefsForBlock(block).length,
      0,
    );
  }
  return chapter.source_refs.length;
}

export function isEditableContentKey(fieldKey: string): boolean {
  return fieldKey !== "source_refs";
}

export function isBlockTypeKey(fieldKey: string): boolean {
  return fieldKey === "block";
}
