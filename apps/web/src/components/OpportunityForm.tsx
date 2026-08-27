"use client";

import { useState } from "react";

import type { OpportunityCreatePayload } from "@/lib/api";

export interface OpportunityFormValues {
  client_name: string;
  opportunity_name: string;
  department: string;
  language: string;
}

const DEFAULT_VALUES: OpportunityFormValues = {
  client_name: "",
  opportunity_name: "",
  department: "",
  language: "en",
};

interface OpportunityFormProps {
  disabled?: boolean;
  onSubmit: (values: OpportunityCreatePayload) => Promise<void>;
}

export function OpportunityForm({ disabled = false, onSubmit }: OpportunityFormProps) {
  const [values, setValues] = useState<OpportunityFormValues>(DEFAULT_VALUES);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdLabel, setCreatedLabel] = useState<string | null>(null);

  function updateField<K extends keyof OpportunityFormValues>(
    key: K,
    value: OpportunityFormValues[K],
  ) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(values);
      setCreatedLabel(`${values.client_name} — ${values.opportunity_name}`);
      setValues(DEFAULT_VALUES);
    } catch (submitError) {
      const message =
        submitError instanceof Error ? submitError.message : "Could not create opportunity.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="opportunity-form" onSubmit={handleSubmit}>
      {error ? <div className="alert alert-error">{error}</div> : null}
      {createdLabel ? (
        <div className="upload-inline-success">
          <span className="upload-inline-success-icon" aria-hidden="true">
            ✓
          </span>
          <div>
            <strong>Opportunity created</strong>
            <p>{createdLabel}</p>
          </div>
        </div>
      ) : null}

      <div className="opportunity-form-grid">
        <div className="form-field">
          <label htmlFor="client_name">Client name</label>
          <input
            id="client_name"
            placeholder="e.g. Acme Corporation"
            value={values.client_name}
            disabled={disabled || busy}
            onChange={(event) => updateField("client_name", event.target.value)}
            required
          />
        </div>
        <div className="form-field">
          <label htmlFor="opportunity_name">Opportunity name</label>
          <input
            id="opportunity_name"
            placeholder="e.g. Q3 automation rollout"
            value={values.opportunity_name}
            disabled={disabled || busy}
            onChange={(event) => updateField("opportunity_name", event.target.value)}
            required
          />
        </div>
        <div className="form-field">
          <label htmlFor="department">Department</label>
          <input
            id="department"
            placeholder="e.g. Sales Engineering"
            value={values.department}
            disabled={disabled || busy}
            onChange={(event) => updateField("department", event.target.value)}
            required
          />
        </div>
        <div className="form-field">
          <label htmlFor="language">Language</label>
          <select
            id="language"
            value={values.language}
            disabled={disabled || busy}
            onChange={(event) => updateField("language", event.target.value)}
          >
            <option value="en">English</option>
            <option value="de">German</option>
            <option value="fr">French</option>
          </select>
        </div>
      </div>

      <div className="opportunity-form-actions">
        <button type="submit" className="btn btn-primary" disabled={disabled || busy}>
          {busy ? "Creating…" : "Create opportunity"}
        </button>
      </div>
    </form>
  );
}
