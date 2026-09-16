import type { FrameworkObject } from "./frameworkTypes";

export function updateRecordField(
  records: Record<string, unknown>[],
  recordIndex: number,
  fieldKey: string,
  value: unknown,
): Record<string, unknown>[] {
  return records.map((record, index) =>
    index === recordIndex ? { ...record, [fieldKey]: value } : record,
  );
}

export function updateQualityScore(
  framework: FrameworkObject,
  field: "opportunity_rating" | "conversation_quality" | "build_readiness",
  value: number,
): FrameworkObject {
  return {
    ...framework,
    quality_scores: {
      ...framework.quality_scores,
      [field]: value,
    },
  };
}

export function updateQualityRationale(
  framework: FrameworkObject,
  field: keyof FrameworkObject["quality_scores"]["rationale"],
  value: string,
): FrameworkObject {
  return {
    ...framework,
    quality_scores: {
      ...framework.quality_scores,
      rationale: {
        ...framework.quality_scores.rationale,
        [field]: value,
      },
    },
  };
}

export function updateFrameworkArrayField<K extends keyof FrameworkObject>(
  framework: FrameworkObject,
  key: K,
  value: FrameworkObject[K],
): FrameworkObject {
  return { ...framework, [key]: value };
}

export function resolveOpenItemConflict(
  items: Record<string, unknown>[],
  itemIndex: number,
  selectedValue: string,
): Record<string, unknown>[] {
  return items.map((item, index) => {
    if (index !== itemIndex) {
      return item;
    }
    const conflict = item.conflict;
    if (typeof conflict !== "object" || conflict === null || Array.isArray(conflict)) {
      return item;
    }
    return {
      ...item,
      conflict: {
        ...(conflict as Record<string, unknown>),
        resolution: { selected_value: selectedValue },
      },
    };
  });
}

export function replaceNonConflictOpenItems(
  items: Record<string, unknown>[],
  nextNonConflicts: Record<string, unknown>[],
): Record<string, unknown>[] {
  const result: Record<string, unknown>[] = [];
  let otherIndex = 0;
  for (const item of items) {
    if (item.item_type === "conflict") {
      result.push(item);
      continue;
    }
    const next = nextNonConflicts[otherIndex];
    otherIndex += 1;
    if (next !== undefined) {
      result.push(next);
    }
  }
  while (otherIndex < nextNonConflicts.length) {
    result.push(nextNonConflicts[otherIndex]);
    otherIndex += 1;
  }
  return result;
}
