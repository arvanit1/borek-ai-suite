import type { FrameworkObject } from "./frameworkTypes";

export function updateRecordField(
  records: Record<string, unknown>[],
  recordIndex: number,
  fieldKey: string,
  value: string,
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
