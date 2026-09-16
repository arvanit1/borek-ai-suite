"use client";

import { FrameworkNestedValue } from "@/components/FrameworkNestedValue";
import { isEditableContentKey } from "@/lib/frameworkEvidence";
import { customerFieldLabel } from "@/lib/frameworkLabels";
import {
  replaceNonConflictOpenItems,
  resolveOpenItemConflict,
  updateFrameworkArrayField,
  updateQualityRationale,
  updateQualityScore,
  updateRecordField,
} from "@/lib/frameworkFieldEdit";
import type { FrameworkObject } from "@/lib/frameworkTypes";

interface FrameworkRootFieldsPanelProps {
  framework: FrameworkObject;
  editable: boolean;
  onChange: (framework: FrameworkObject) => void;
}

interface RecordSectionProps {
  title: string;
  records: Record<string, unknown>[];
  editable: boolean;
  onChange: (records: Record<string, unknown>[]) => void;
}

function RecordSection({ title, records, editable, onChange }: RecordSectionProps) {
  if (records.length === 0) {
    return (
      <section className="framework-record-section">
        <h3>{title}</h3>
        <p className="upload-hint">No records in this section.</p>
      </section>
    );
  }

  return (
    <section className="framework-record-section">
      <h3>{title}</h3>
      {records.map((record, recordIndex) => (
        <article key={`${title}-${recordIndex}`} className="framework-fact-block">
          <div className="framework-fact-fields">
            {Object.entries(record)
              .filter(([fieldKey]) => isEditableContentKey(fieldKey))
              .map(([fieldKey, fieldValue]) => (
                <FrameworkNestedValue
                  key={fieldKey}
                  id={`${title}-${recordIndex}-${fieldKey}`}
                  label={customerFieldLabel(fieldKey)}
                  value={fieldValue}
                  editable={editable}
                  onChange={(next) =>
                    onChange(updateRecordField(records, recordIndex, fieldKey, next))
                  }
                />
              ))}
          </div>
        </article>
      ))}
    </section>
  );
}

export function FrameworkRootFieldsPanel({
  framework,
  editable,
  onChange,
}: FrameworkRootFieldsPanelProps) {
  return (
    <div className="framework-root-fields">
      <section className="framework-record-section">
        <h3>Quality scores</h3>
        <div className="framework-meta-grid">
          {(
            [
              "opportunity_rating",
              "conversation_quality",
              "build_readiness",
            ] as const
          ).map((field) => (
            <div key={field} className="form-field">
              <label htmlFor={`quality-${field}`}>{customerFieldLabel(field)}</label>
              <input
                id={`quality-${field}`}
                type="number"
                min={0}
                max={100}
                value={framework.quality_scores[field]}
                disabled={!editable}
                onChange={(event) =>
                  onChange(updateQualityScore(framework, field, Number(event.target.value)))
                }
              />
            </div>
          ))}
        </div>
        <div className="framework-fact-fields">
          {Object.entries(framework.quality_scores.rationale).map(([fieldKey, fieldValue]) => (
            <div key={fieldKey} className="form-field">
              <label htmlFor={`rationale-${fieldKey}`}>{customerFieldLabel(fieldKey)}</label>
              <input
                id={`rationale-${fieldKey}`}
                value={fieldValue}
                disabled={!editable}
                onChange={(event) =>
                  onChange(
                    updateQualityRationale(
                      framework,
                      fieldKey as keyof FrameworkObject["quality_scores"]["rationale"],
                      event.target.value,
                    ),
                  )
                }
              />
            </div>
          ))}
        </div>
      </section>

      <RecordSection
        title="Success measures"
        records={framework.kpis}
        editable={editable}
        onChange={(records) => onChange(updateFrameworkArrayField(framework, "kpis", records))}
      />
      <RecordSection
        title="Systems"
        records={framework.systems}
        editable={editable}
        onChange={(records) => onChange(updateFrameworkArrayField(framework, "systems", records))}
      />
      <RecordSection
        title="Rules"
        records={framework.rules}
        editable={editable}
        onChange={(records) => onChange(updateFrameworkArrayField(framework, "rules", records))}
      />
      <RecordSection
        title="Exceptions"
        records={framework.exceptions}
        editable={editable}
        onChange={(records) =>
          onChange(updateFrameworkArrayField(framework, "exceptions", records))
        }
      />
      <RecordSection
        title="Access needs"
        records={framework.access_needs}
        editable={editable}
        onChange={(records) =>
          onChange(updateFrameworkArrayField(framework, "access_needs", records))
        }
      />
      <RecordSection
        title="Evolution stages"
        records={framework.evolution_stages}
        editable={editable}
        onChange={(records) =>
          onChange(updateFrameworkArrayField(framework, "evolution_stages", records))
        }
      />
      <ConflictResolutionSection
        records={framework.open_items}
        editable={editable}
        onChange={(records) =>
          onChange(updateFrameworkArrayField(framework, "open_items", records))
        }
      />
      <RecordSection
        title="Assumptions and open items"
        records={framework.open_items.filter((item) => item.item_type !== "conflict")}
        editable={editable}
        onChange={(records) =>
          onChange(
            updateFrameworkArrayField(
              framework,
              "open_items",
              replaceNonConflictOpenItems(framework.open_items, records),
            ),
          )
        }
      />
    </div>
  );
}

interface ConflictAlternative {
  value?: unknown;
  source_refs?: unknown;
}

interface ConflictDetail {
  topic?: unknown;
  alternatives?: unknown;
  resolution?: unknown;
}

function conflictDetail(record: Record<string, unknown>): ConflictDetail | null {
  if (record.item_type !== "conflict" || typeof record.conflict !== "object" || record.conflict === null) {
    return null;
  }
  return record.conflict as ConflictDetail;
}

interface RecordListProps {
  records: Record<string, unknown>[];
  editable: boolean;
  onChange: (records: Record<string, unknown>[]) => void;
}

function ConflictResolutionSection({
  records,
  editable,
  onChange,
}: RecordListProps) {
  const conflicts = records
    .map((record, index) => ({ record, index, detail: conflictDetail(record) }))
    .filter((item): item is { record: Record<string, unknown>; index: number; detail: ConflictDetail } => {
      return item.detail !== null;
    });
  if (conflicts.length === 0) {
    return null;
  }

  return (
    <section className="framework-record-section" data-testid="framework-conflict-resolution">
      <h3>Source conflicts</h3>
      <p className="upload-hint">
        Choose the statement that should stand. Confirmation stays blocked until every conflict has a selected value.
      </p>
      {conflicts.map(({ record, index, detail }) => {
        const alternatives = Array.isArray(detail.alternatives)
          ? (detail.alternatives as ConflictAlternative[])
          : [];
        const resolution =
          typeof detail.resolution === "object" && detail.resolution !== null
            ? (detail.resolution as { selected_value?: unknown })
            : {};
        const selected = String(resolution.selected_value ?? "");
        const topic = String(detail.topic || record.description || "source conflict");
        return (
          <article key={`conflict-${index}`} className="framework-conflict-card">
            <h4>{topic}</h4>
            <p>{String(record.description || "")}</p>
            <fieldset disabled={!editable} className="framework-conflict-choices">
              <legend>Selected value</legend>
              {alternatives.map((alternative, alternativeIndex) => {
                const value = String(alternative.value ?? "");
                const choiceId = `conflict-${index}-option-${alternativeIndex}`;
                return (
                  <label key={choiceId} htmlFor={choiceId} className="framework-conflict-choice">
                    <input
                      id={choiceId}
                      type="radio"
                      name={`conflict-${index}`}
                      value={value}
                      checked={selected === value}
                      onChange={() => onChange(resolveOpenItemConflict(records, index, value))}
                    />
                    <span>{value}</span>
                  </label>
                );
              })}
            </fieldset>
          </article>
        );
      })}
    </section>
  );
}
