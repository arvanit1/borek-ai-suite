"use client";

import React, { useEffect, useState } from "react";

import type { AdditionalClientInformation, ClientContact, OpportunityCreatePayload } from "@/lib/api";
import { opportunityErrorMessage } from "@/lib/apiErrors";
import { compactAdditionalClientInformation } from "@/lib/clientIntake";
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
  additional_client_information: AdditionalClientInformation | null;
}

const DEFAULT_VALUES: OpportunityFormValues = {
  client_name: "",
  opportunity_name: "",
  department: "",
  language: "en",
  pii_redaction_enabled: true,
  additional_client_information: null,
};

const EMPTY_CLIENT_INFORMATION: AdditionalClientInformation = {
  location_requirements: [],
  constraints: [],
  contacts: [],
  priorities: [],
  notes: null,
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

  function updateClientInformation(
    update: (current: AdditionalClientInformation) => AdditionalClientInformation,
  ) {
    setValues((current) => {
      const next = {
        ...current,
        additional_client_information: update(
          current.additional_client_information ?? EMPTY_CLIENT_INFORMATION,
        ),
      };
      saveOpportunityDraft(next);
      return next;
    });
  }

  function updateListField(
    key: "location_requirements" | "constraints" | "priorities",
    raw: string,
  ) {
    updateClientInformation((current) => ({ ...current, [key]: raw.split("\n") }));
  }

  function updateContact(index: number, key: keyof ClientContact, value: string) {
    updateClientInformation((current) => ({
      ...current,
      contacts: current.contacts.map((contact, contactIndex) =>
        contactIndex === index ? { ...contact, [key]: value } : contact,
      ),
    }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const additionalClientInformation = compactAdditionalClientInformation(
        values.additional_client_information,
      );
      await onSubmit({
        client_name: values.client_name,
        opportunity_name: values.opportunity_name,
        department: values.department,
        language: values.language,
        pii_redaction_enabled: values.pii_redaction_enabled,
        ...(additionalClientInformation
          ? { additional_client_information: additionalClientInformation }
          : {}),
      });
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

      <details
        className="client-information"
        open={Boolean(compactAdditionalClientInformation(values.additional_client_information))}
      >
        <summary>
          <span>Additional client information</span>
          <span className="optional-label">Optional</span>
        </summary>
        <p className="client-information-intro">
          Add known context to personalize the Framework. Leave this section empty to keep the fast path.
        </p>
        <div className="client-information-grid">
          <div className="form-field">
            <label htmlFor="location_requirements">Location requirements</label>
            <textarea
              id="location_requirements"
              rows={3}
              placeholder={"One requirement per line\ne.g. Data must stay in the EU"}
              value={(values.additional_client_information?.location_requirements ?? []).join("\n")}
              disabled={disabled || busy || locked}
              onChange={(event) => updateListField("location_requirements", event.target.value)}
            />
          </div>
          <div className="form-field">
            <label htmlFor="client_constraints">Constraints</label>
            <textarea
              id="client_constraints"
              rows={3}
              placeholder={"One constraint per line\ne.g. Go-live before Q4"}
              value={(values.additional_client_information?.constraints ?? []).join("\n")}
              disabled={disabled || busy || locked}
              onChange={(event) => updateListField("constraints", event.target.value)}
            />
          </div>
          <div className="form-field">
            <label htmlFor="client_priorities">Stated priorities</label>
            <textarea
              id="client_priorities"
              rows={3}
              placeholder={"One priority per line\ne.g. Reduce manual review"}
              value={(values.additional_client_information?.priorities ?? []).join("\n")}
              disabled={disabled || busy || locked}
              onChange={(event) => updateListField("priorities", event.target.value)}
            />
          </div>
          <div className="form-field">
            <label htmlFor="client_notes">Notes</label>
            <textarea
              id="client_notes"
              rows={3}
              maxLength={20_000}
              placeholder="Other confirmed client context"
              value={values.additional_client_information?.notes ?? ""}
              disabled={disabled || busy || locked}
              onChange={(event) =>
                updateClientInformation((current) => ({ ...current, notes: event.target.value }))
              }
            />
          </div>
        </div>

        <div className="client-contacts">
          <div className="client-contacts-header">
            <div>
              <strong>Client contacts</strong>
              <p>Add only contacts relevant to this opportunity.</p>
            </div>
            {!locked ? (
              <button
                type="button"
                className="btn btn-secondary"
                disabled={disabled || busy}
                onClick={() =>
                  updateClientInformation((current) => ({
                    ...current,
                    contacts: [...current.contacts, { name: "", role: null, email: null, phone: null }],
                  }))
                }
              >
                Add contact
              </button>
            ) : null}
          </div>
          {(values.additional_client_information?.contacts ?? []).map((contact, index) => (
            <div className="client-contact-row" key={index}>
              <div className="form-field">
                <label htmlFor={`contact_name_${index}`}>Name</label>
                <input
                  id={`contact_name_${index}`}
                  value={contact.name}
                  maxLength={200}
                  required
                  disabled={disabled || busy || locked}
                  onChange={(event) => updateContact(index, "name", event.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor={`contact_role_${index}`}>Role</label>
                <input
                  id={`contact_role_${index}`}
                  value={contact.role ?? ""}
                  maxLength={200}
                  disabled={disabled || busy || locked}
                  onChange={(event) => updateContact(index, "role", event.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor={`contact_email_${index}`}>Email</label>
                <input
                  id={`contact_email_${index}`}
                  type="email"
                  value={contact.email ?? ""}
                  maxLength={320}
                  disabled={disabled || busy || locked}
                  onChange={(event) => updateContact(index, "email", event.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor={`contact_phone_${index}`}>Phone</label>
                <input
                  id={`contact_phone_${index}`}
                  type="tel"
                  value={contact.phone ?? ""}
                  maxLength={100}
                  disabled={disabled || busy || locked}
                  onChange={(event) => updateContact(index, "phone", event.target.value)}
                />
              </div>
              {!locked ? (
                <button
                  type="button"
                  className="btn btn-quiet client-contact-remove"
                  disabled={disabled || busy}
                  onClick={() =>
                    updateClientInformation((current) => ({
                      ...current,
                      contacts: current.contacts.filter((_, contactIndex) => contactIndex !== index),
                    }))
                  }
                >
                  Remove
                </button>
              ) : null}
            </div>
          ))}
        </div>
      </details>

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
