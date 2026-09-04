"use client";

import { useEffect, useState } from "react";

import type { OpportunityCreatePayload } from "@/lib/api";
import { opportunityErrorMessage } from "@/lib/apiErrors";
import {
  clearOpportunityDraft,
  loadOpportunityDraft,
  saveOpportunityDraft,
} from "@/lib/pipelineContext";

export interface OpportunityFormValues {
  client_name: string;
  opportunity_name: string;
  department: string;
  language: string;
  pii_redaction_enabled: boolean;
}

const DEFAULT_VALUES: OpportunityFormValues = {
  client_name: "",
  opportunity_name: "",
  department: "",
  language: "en",
  pii_redaction_enabled: true,
};

interface OpportunityFormProps {
  disabled?: boolean;
  existing?: OpportunityFormValues | null;
  onSubmit: (values: OpportunityCreatePayload) => Promise<void>;
}

export function OpportunityForm({
  disabled = false,
  existing = null,
  onSubmit,
}: OpportunityFormProps) {
  const [values, setValues] = useState<OpportunityFormValues>(existing ?? DEFAULT_VALUES);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdLabel, setCreatedLabel] = useState<string | null>(
    existing ? `${existing.client_name} — ${existing.opportunity_name}` : null,
  );
  const locked = Boolean(existing) || Boolean(createdLabel);

  useEffect(() => {
    if (existing) {
      setValues({
        ...DEFAULT_VALUES,
        ...existing,
        pii_redaction_enabled: existing.pii_redaction_enabled !== false,
      });
      setCreatedLabel(`${existing.client_name} — ${existing.opportunity_name}`);
      return;
    }
    const draft = loadOpportunityDraft();
    if (draft) {
      setValues({
        ...DEFAULT_VALUES,
        ...draft,
        pii_redaction_enabled: draft.pii_redaction_enabled !== false,
      });
    }
  }, [existing]);

  function updateField<K extends keyof OpportunityFormValues>(
    key: K,
    value: OpportunityFormValues[K],
  ) {
    setValues((current) => {
      const next = { ...current, [key]: value };
      saveOpportunityDraft(next);
      return next;
    });
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(values);
      setCreatedLabel(`${values.client_name} — ${values.opportunity_name}`);
      clearOpportunityDraft();
    } catch (submitError) {
      setError(opportunityErrorMessage(submitError));
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
            disabled={disabled || busy || locked}
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
            disabled={disabled || busy || locked}
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
            disabled={disabled || busy || locked}
            onChange={(event) => updateField("department", event.target.value)}
            required
          />
        </div>
        <div className="form-field">
          <label htmlFor="language">Language</label>
          <select
            id="language"
            value={values.language}
            disabled={disabled || busy || locked}
            onChange={(event) => updateField("language", event.target.value)}
          >
            <option value="en">English</option>
            <option value="de">German</option>
            <option value="fr">French</option>
          </select>
        </div>
        <div className="form-field opportunity-form-pii">
          <label htmlFor="pii_redaction_enabled">
            <input
              id="pii_redaction_enabled"
              type="checkbox"
              checked={values.pii_redaction_enabled}
              disabled={disabled || busy || locked}
              onChange={(event) => updateField("pii_redaction_enabled", event.target.checked)}
            />
            Redact personal data before AI processing
          </label>
          <p>
            Names, emails, and phone numbers are removed from transcripts before they are sent to the
            model. Leave this on unless a case explicitly needs the original identifiers.
          </p>
        </div>
      </div>

      <div className="opportunity-form-actions">
        {locked ? (
          <p className="opportunity-created-status" role="status">Opportunity created</p>
        ) : (
          <button type="submit" className="btn btn-primary" disabled={disabled || busy}>
            {busy ? "Creating…" : "Create opportunity"}
          </button>
        )}
      </div>
    </form>
  );
}
