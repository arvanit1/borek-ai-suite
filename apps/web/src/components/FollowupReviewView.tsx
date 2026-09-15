import React from "react";

import { AppPageHeader } from "@/components/AppPageHeader";
import {
  FOLLOWUP_CHECKLIST,
  followupContentWordCount,
  followupDraftErrors,
  primaryFollowupRecipient,
  type FollowupChecklistId,
  type FollowupChecklistState,
  type FollowupDraft,
  type FollowupProjectStatics,
  type FollowupRecipient,
} from "@/lib/followupReview";

export interface FollowupReviewViewProps {
  clientName: string;
  opportunityName: string;
  statics: FollowupProjectStatics;
  staticsSaved: boolean;
  draft: FollowupDraft | null;
  checklist: FollowupChecklistState;
  acknowledgedFlags: ReadonlySet<string>;
  canConfirm: boolean;
  busy: boolean;
  error: string | null;
  info: string | null;
  onStaticsChange: (value: FollowupProjectStatics) => void;
  onSaveStatics: () => void;
  onDraftChange: (value: FollowupDraft) => void;
  onChecklistChange: (id: FollowupChecklistId, checked: boolean) => void;
  onFlagChange: (flag: string, checked: boolean) => void;
  onConfirm: () => void;
}

export function FollowupReviewView({
  clientName,
  opportunityName,
  statics,
  staticsSaved,
  draft,
  checklist,
  acknowledgedFlags,
  canConfirm,
  busy,
  error,
  info,
  onStaticsChange,
  onSaveStatics,
  onDraftChange,
  onChecklistChange,
  onFlagChange,
  onConfirm,
}: FollowupReviewViewProps) {
  const primary = primaryFollowupRecipient(statics);
  const primaryIndex = statics.standard_recipients.findIndex(
    (recipient) => recipient.kind === "to" && recipient.primary,
  );
  const updatePrimary = (updates: Partial<FollowupRecipient>) => {
    onStaticsChange({
      ...statics,
      standard_recipients: statics.standard_recipients.map((recipient, index) =>
        index === primaryIndex
          ? { ...recipient, ...updates, kind: "to", primary: true }
          : recipient,
      ),
    });
  };
  const updateRecipient = (index: number, updates: Partial<FollowupRecipient>) => {
    onStaticsChange({
      ...statics,
      standard_recipients: statics.standard_recipients.map((recipient, recipientIndex) =>
        recipientIndex === index ? { ...recipient, ...updates, primary: false } : recipient,
      ),
    });
  };
  const removeRecipient = (index: number) => {
    onStaticsChange({
      ...statics,
      standard_recipients: statics.standard_recipients.filter((_, recipientIndex) => recipientIndex !== index),
    });
  };
  const reviewed = draft?.status === "reviewed";
  const locked = draft ? draft.status !== "draft" : false;
  const draftErrors = draft ? followupDraftErrors(draft) : [];

  return (
    <div className="followup-review-page">
      <AppPageHeader
        kicker="Meeting follow-up"
        title="Review the client email"
        lead="Check the exact subject, wording, names, dates, and intended recipient before anything reaches Outlook."
      />

      <div className="followup-context" aria-label="Opportunity">
        <span>{clientName}</span>
        <strong>{opportunityName}</strong>
        <span className="followup-fixture-badge">JJ-32 fixture review</span>
      </div>

      <div className="alert alert-info followup-unsent-note">
        This is a review fixture only. No Outlook draft or client email has been created or sent.
      </div>
      {error ? <p className="alert alert-error" role="alert">{error}</p> : null}
      {info ? <p className="alert alert-info" role="status">{info}</p> : null}

      <section className="upload-panel followup-statics-panel">
        <header className="upload-panel-header">
          <div>
            <h2>Project email settings</h2>
            <p>Stored once on this opportunity. These values are never guessed by the model.</p>
          </div>
          <span className={`recent-status ${staticsSaved ? "recent-status-filed" : "recent-status-review"}`}>
            {staticsSaved ? "Saved" : "Not saved"}
          </span>
        </header>
        <div className="followup-form-grid">
          <div className="form-field">
            <label htmlFor="followup-project-name">Project name</label>
            <input id="followup-project-name" value={statics.project_name} onChange={(event) => onStaticsChange({ ...statics, project_name: event.target.value })} disabled={busy || locked} />
          </div>
          <div className="form-field">
            <label htmlFor="followup-client-short">Client short name</label>
            <input id="followup-client-short" value={statics.client_short} onChange={(event) => onStaticsChange({ ...statics, client_short: event.target.value })} disabled={busy || locked} />
          </div>
          <div className="form-field">
            <label htmlFor="followup-tone">Client tone</label>
            <select id="followup-tone" value={statics.salutation_style} onChange={(event) => onStaticsChange({ ...statics, salutation_style: event.target.value as FollowupProjectStatics["salutation_style"] })} disabled={busy || locked}>
              <option value="informal">Du / informal</option>
              <option value="formal">Sie / formal</option>
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="followup-recipient-email">Primary intended recipient</label>
            <input id="followup-recipient-email" type="email" value={primary.email} onChange={(event) => updatePrimary({ email: event.target.value })} disabled={busy || locked} />
          </div>
          <div className="form-field">
            <label htmlFor="followup-recipient-first">Recipient first name</label>
            <input id="followup-recipient-first" value={primary.first_name ?? ""} onChange={(event) => updatePrimary({ first_name: event.target.value || null })} disabled={busy || locked} />
          </div>
          <div className="form-field">
            <label htmlFor="followup-recipient-salutation">Formal salutation</label>
            <input id="followup-recipient-salutation" value={primary.salutation ?? ""} onChange={(event) => updatePrimary({ salutation: event.target.value || null })} placeholder="Mr, Ms, Dr" disabled={busy || locked} />
          </div>
          <div className="form-field">
            <label htmlFor="followup-recipient-last">Recipient last name</label>
            <input id="followup-recipient-last" value={primary.last_name ?? ""} onChange={(event) => updatePrimary({ last_name: event.target.value || null })} disabled={busy || locked} />
          </div>
          <div className="form-field">
            <label htmlFor="followup-sender-name">Sender name</label>
            <input id="followup-sender-name" value={statics.sender_profile.name} onChange={(event) => onStaticsChange({ ...statics, sender_profile: { ...statics.sender_profile, name: event.target.value } })} disabled={busy || locked} />
          </div>
          <div className="form-field">
            <label htmlFor="followup-sender-role">Sender role</label>
            <input id="followup-sender-role" value={statics.sender_profile.role} onChange={(event) => onStaticsChange({ ...statics, sender_profile: { ...statics.sender_profile, role: event.target.value } })} disabled={busy || locked} />
          </div>
          <div className="form-field">
            <label htmlFor="followup-sender-email">Sender email</label>
            <input id="followup-sender-email" type="email" value={statics.sender_profile.email} onChange={(event) => onStaticsChange({ ...statics, sender_profile: { ...statics.sender_profile, email: event.target.value } })} disabled={busy || locked} />
          </div>
          <div className="followup-secondary-recipients">
            <h3>Additional intended recipients</h3>
            {statics.standard_recipients.map((recipient, index) =>
              index === primaryIndex ? null : (
                <div className="followup-recipient-row" key={`recipient-${index}`}>
                  <div className="form-field">
                    <label htmlFor={`followup-recipient-${index}-email`}>Recipient email</label>
                    <input id={`followup-recipient-${index}-email`} type="email" value={recipient.email} onChange={(event) => updateRecipient(index, { email: event.target.value })} disabled={busy || locked} />
                  </div>
                  <div className="form-field">
                    <label htmlFor={`followup-recipient-${index}-kind`}>Recipient type</label>
                    <select id={`followup-recipient-${index}-kind`} value={recipient.kind} onChange={(event) => updateRecipient(index, { kind: event.target.value as FollowupRecipient["kind"] })} disabled={busy || locked}>
                      <option value="to">To</option>
                      <option value="cc">CC</option>
                    </select>
                  </div>
                  <button type="button" className="btn btn-quiet" onClick={() => removeRecipient(index)} disabled={busy || locked}>Remove</button>
                </div>
              ),
            )}
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy || locked || statics.standard_recipients.length >= 20}
              onClick={() => onStaticsChange({
                ...statics,
                standard_recipients: [
                  ...statics.standard_recipients,
                  { email: "", first_name: null, last_name: null, salutation: null, kind: "cc", primary: false },
                ],
              })}
            >
              Add recipient
            </button>
          </div>
        </div>
        {!locked ? (
          <div className="followup-panel-actions">
            <button type="button" className="btn btn-secondary" onClick={onSaveStatics} disabled={busy}>
              {busy ? "Saving..." : "Save project settings"}
            </button>
          </div>
        ) : null}
      </section>

      {draft ? (
        <>
          <section className="upload-panel followup-draft-panel">
            <header className="upload-panel-header">
              <div>
                <h2>Email draft</h2>
                <p>Plain text, short, and editable before review confirmation.</p>
              </div>
              <span className={`recent-status ${reviewed ? "recent-status-filed" : "recent-status-review"}`}>
                {draft.status === "reviewed" ? "Reviewed - not sent" : draft.status === "sent" ? "Sent" : "Draft"}
              </span>
            </header>
            <div className="form-field">
              <label htmlFor="followup-subject">Subject</label>
              <input id="followup-subject" value={draft.subject} onChange={(event) => onDraftChange({ ...draft, subject: event.target.value })} disabled={busy || locked} />
            </div>
            <div className="form-field">
              <label htmlFor="followup-body">Body</label>
              <textarea id="followup-body" rows={18} value={draft.body} onChange={(event) => onDraftChange({ ...draft, body: event.target.value })} disabled={busy || locked} />
            </div>
            <div className="followup-draft-meta">
              <span>
                Intended recipients: {statics.standard_recipients.map((recipient) => `${recipient.kind.toUpperCase()} ${recipient.email}`).join(", ")}
              </span>
              <span>Sender: {statics.sender_profile.name} ({statics.sender_profile.email})</span>
              <span>{followupContentWordCount(draft.body)}/150 body words</span>
            </div>
            {draftErrors.length ? (
              <ul className="alert alert-error followup-validation" role="alert">
                {draftErrors.map((message) => <li key={message}>{message}</li>)}
              </ul>
            ) : null}
          </section>

          <section className="upload-panel followup-checklist-panel">
            <header className="upload-panel-header">
              <div>
                <h2>Required review</h2>
                <p>Confirm each statement against the meeting before marking this fixture reviewed.</p>
              </div>
            </header>
            <div className="followup-checklist">
              {FOLLOWUP_CHECKLIST.map((item) => (
                <label key={item.id}>
                  <input type="checkbox" checked={checklist[item.id]} onChange={(event) => onChecklistChange(item.id, event.target.checked)} disabled={busy || locked} />
                  <span>{item.label}</span>
                </label>
              ))}
            </div>

            <div className="followup-flags">
              <h3>Extraction flags</h3>
              {draft.review_flags.length ? draft.review_flags.map((flag) => (
                <label key={flag}>
                  <input type="checkbox" checked={acknowledgedFlags.has(flag)} onChange={(event) => onFlagChange(flag, event.target.checked)} disabled={busy || locked} />
                  <span>Checked against transcript: {flag}</span>
                </label>
              )) : <p className="upload-hint">No extraction flags require acknowledgement.</p>}
            </div>

            <div className="followup-panel-actions">
              <button type="button" className="btn btn-primary" data-testid="followup-confirm-review" onClick={onConfirm} disabled={!canConfirm || busy || locked}>
                {draft.status === "reviewed" ? "Reviewed - not sent" : draft.status === "sent" ? "Sent" : "Confirm review"}
              </button>
              <p>Confirmation never sends an email. BT-33 must persist an Outlook draft before this fixture can become a live review.</p>
            </div>
          </section>
        </>
      ) : (
        <section className="recent-state-card">
          <p>Save valid project email settings to prepare the JJ-32 fixture for review.</p>
        </section>
      )}
    </div>
  );
}
