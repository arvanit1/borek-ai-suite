"use client";

import { customerFieldLabel } from "@/lib/frameworkLabels";
import { replaceArrayItem, replaceRecordField } from "@/lib/frameworkNestedEdit";

interface FrameworkNestedValueProps {
  id: string;
  label?: string;
  value: unknown;
  editable: boolean;
  onChange: (value: unknown) => void;
}

export function FrameworkNestedValue({
  id,
  label,
  value,
  editable,
  onChange,
}: FrameworkNestedValueProps) {
  const field = (
    <NestedControl id={id} value={value} editable={editable} onChange={onChange} />
  );
  if (!label) {
    return field;
  }
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      {field}
    </div>
  );
}

function NestedControl({
  id,
  value,
  editable,
  onChange,
}: Omit<FrameworkNestedValueProps, "label">) {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <p className="upload-hint">No items.</p>;
    }
    if (value.every((item) => Array.isArray(item))) {
      return (
        <div className="framework-nested-table-wrap">
          <table className="framework-nested-table">
            <tbody>
              {value.map((row, rowIndex) => (
                <tr key={`${id}-row-${rowIndex}`}>
                  {(row as unknown[]).map((cell, cellIndex) => (
                    <td key={`${id}-cell-${rowIndex}-${cellIndex}`}>
                      <input
                        id={`${id}-${rowIndex}-${cellIndex}`}
                        value={String(cell ?? "")}
                        disabled={!editable}
                        onChange={(event) => {
                          const nextRow = replaceArrayItem(row as unknown[], cellIndex, event.target.value);
                          onChange(replaceArrayItem(value, rowIndex, nextRow));
                        }}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    if (value.every((item) => typeof item === "object" && item !== null && !Array.isArray(item))) {
      return (
        <div className="framework-nested-list">
          {value.map((item, itemIndex) => (
            <article key={`${id}-record-${itemIndex}`} className="framework-nested-record">
              {Object.entries(item as Record<string, unknown>)
                .filter(([fieldKey]) => fieldKey !== "source_refs")
                .map(([fieldKey, fieldValue]) => (
                <FrameworkNestedValue
                  key={`${id}-${itemIndex}-${fieldKey}`}
                  id={`${id}-${itemIndex}-${fieldKey}`}
                  label={customerFieldLabel(fieldKey)}
                  value={fieldValue}
                  editable={editable}
                  onChange={(next) => {
                    const updated = replaceRecordField(
                      item as Record<string, unknown>,
                      fieldKey,
                      next,
                    );
                    onChange(replaceArrayItem(value, itemIndex, updated));
                  }}
                />
              ))}
            </article>
          ))}
        </div>
      );
    }
    return (
      <div className="framework-nested-list">
        {value.map((item, itemIndex) => (
          <input
            key={`${id}-item-${itemIndex}`}
            id={`${id}-${itemIndex}`}
            value={String(item ?? "")}
            disabled={!editable}
            onChange={(event) =>
              onChange(replaceArrayItem(value, itemIndex, event.target.value))
            }
          />
        ))}
      </div>
    );
  }

  if (typeof value === "object" && value !== null) {
    const record = value as Record<string, unknown>;
    return (
      <div className="framework-nested-list">
        {Object.entries(record)
          .filter(([fieldKey]) => fieldKey !== "source_refs")
          .map(([fieldKey, fieldValue]) => (
            <FrameworkNestedValue
              key={`${id}-${fieldKey}`}
              id={`${id}-${fieldKey}`}
              label={customerFieldLabel(fieldKey)}
              value={fieldValue}
              editable={editable}
              onChange={(next) => onChange(replaceRecordField(record, fieldKey, next))}
            />
          ))}
      </div>
    );
  }

  if (typeof value === "number") {
    return (
      <input
        id={id}
        type="number"
        value={Number.isNaN(value) ? "" : value}
        disabled={!editable}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    );
  }

  if (typeof value === "boolean") {
    return (
      <input
        id={id}
        type="checkbox"
        checked={value}
        disabled={!editable}
        onChange={(event) => onChange(event.target.checked)}
      />
    );
  }

  return (
    <input
      id={id}
      value={String(value ?? "")}
      disabled={!editable}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
