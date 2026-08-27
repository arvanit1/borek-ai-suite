"use client";

import {
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
            {Object.entries(record).map(([fieldKey, fieldValue]) => (
              <div key={fieldKey} className="form-field">
                <label htmlFor={`${title}-${recordIndex}-${fieldKey}`}>{fieldKey}</label>
                <input
                  id={`${title}-${recordIndex}-${fieldKey}`}
                  value={String(fieldValue ?? "")}
                  disabled={!editable}
                  onChange={(event) =>
                    onChange(
                      updateRecordField(records, recordIndex, fieldKey, event.target.value),
                    )
                  }
                />
              </div>
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
              <label htmlFor={`quality-${field}`}>{field.replace(/_/g, " ")}</label>
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
              <label htmlFor={`rationale-${fieldKey}`}>{fieldKey.replace(/_/g, " ")}</label>
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
        title="KPIs"
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
      <RecordSection
        title="Open items"
        records={framework.open_items}
        editable={editable}
        onChange={(records) =>
          onChange(updateFrameworkArrayField(framework, "open_items", records))
        }
      />
    </div>
  );
}
