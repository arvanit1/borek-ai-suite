"use client";

import {
  APPROVE_BUILD_LABEL,
  HUMAN_CONFIRM_LABEL,
  attentionTone,
  blockingSignals,
  canApproveAndBuild,
  evidenceWarningText,
  isApprovalBlocked,
  openItemText,
  reviewStateLabel,
  type AttentionSignal,
  type FrameworkReviewPayload,
  type ReviewOpenItem,
} from "@/lib/frameworkReview";

interface FrameworkReviewSummaryProps {
  review: FrameworkReviewPayload;
  editable: boolean;
  confirmed: boolean;
  busy: boolean;
  dirty: boolean;
  humanConfirmed: boolean;
  onHumanConfirmedChange: (checked: boolean) => void;
  onApprove: () => void;
  onSave?: () => void;
  onJumpToChapter?: (chapterId: string) => void;
}

function ListCard({
  title,
  items,
  empty,
  prominent = false,
}: {
  title: string;
  items: string[];
  empty: string;
  prominent?: boolean;
}) {
  return (
    <section
      className={
        prominent ? "framework-summary-card framework-summary-card-prominent" : "framework-summary-card"
      }
    >
      <h3>{title}</h3>
      {items.length > 0 ? (
        <ul>
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="upload-hint">{empty}</p>
      )}
    </section>
  );
}

function openItemLines(items: ReviewOpenItem[] | undefined): string[] {
  return (items ?? []).map(openItemText).filter(Boolean);
}

function SignalList({
  signals,
  onJumpToChapter,
}: {
  signals: AttentionSignal[];
  onJumpToChapter?: (chapterId: string) => void;
}) {
  if (signals.length === 0) {
    return null;
  }
  return (
    <ul className="framework-signal-list">
      {signals.map((signal) => (
        <li key={`${signal.id}-${signal.chapter_id ?? "none"}-${signal.message}`}>
          <p>{signal.message}</p>
          {signal.action ? <p className="framework-signal-action">{signal.action}</p> : null}
          {signal.chapter_id && onJumpToChapter ? (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => onJumpToChapter(signal.chapter_id as string)}
            >
              Review chapter {signal.chapter_id}
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function FrameworkReviewSummary({
  review,
  editable,
  confirmed,
  busy,
  dirty,
  humanConfirmed,
  onHumanConfirmedChange,
  onApprove,
  onSave,
  onJumpToChapter,
}: FrameworkReviewSummaryProps) {
  const summary = review.review_summary;
  const signals = review.attention_signals ?? [];
  const blocked = isApprovalBlocked(review);
  const blockers = blockingSignals(signals);
  const tone = attentionTone(review.review_state, signals);
  const canApprove = canApproveAndBuild({
    editable,
    confirmed,
    humanConfirmed,
    blocked,
  });
  const warningSignals = signals.filter((signal) => !isApprovalBlocked({ attention_signals: [signal], review_summary: {} }) && signal.severity !== "info");
  const headline = summary.headline?.trim();
  const executiveSummary = summary.executive_summary?.trim() ?? "";
  const assumptions = openItemLines(summary.assumptions);
  const openQuestions = openItemLines(summary.open_questions);
  const evidenceWarnings = (summary.evidence_warnings ?? []).map(evidenceWarningText);
  const blockingMessages = [
    ...(summary.blocking_items ?? []).map((item) => item.message),
    summary.confirm_block_reason,
  ].filter((message, index, all): message is string => Boolean(message) && all.indexOf(message) === index);

  return (
    <section className="framework-review-summary" data-testid="framework-review-summary">
      {blocked ? (
        <div
          className="framework-blocking-banner"
          role="alert"
          data-testid="framework-blocking-banner"
        >
          <div>
            <strong>Cannot approve yet</strong>
            <p>
              Resolve the issues below before building the presentation. Approval stays locked
              until they are cleared.
            </p>
          </div>
          {blockingMessages.length > 0 ? (
            <ul>
              {blockingMessages.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          ) : null}
          <SignalList signals={blockers} onJumpToChapter={onJumpToChapter} />
        </div>
      ) : (
        <div
          className={`framework-attention-banner framework-attention-${tone}`}
          data-testid="framework-attention-banner"
        >
          <strong>{reviewStateLabel(review.review_state)}</strong>
          <p>
            {tone === "ready"
              ? "The summary looks complete. Please confirm below — approval is never automatic."
              : tone === "warning"
                ? "Please review the highlighted items before you approve."
                : "Review the customer story, then approve when you are satisfied."}
          </p>
          {warningSignals.length > 0 ? (
            <SignalList signals={warningSignals} onJumpToChapter={onJumpToChapter} />
          ) : null}
        </div>
      )}

      {headline ? <p className="framework-summary-headline">{headline}</p> : null}

      <section className="framework-summary-card framework-summary-card-lead" data-testid="framework-executive-summary">
        <h3>Executive summary</h3>
        {executiveSummary ? <p>{executiveSummary}</p> : <p className="upload-hint">No executive summary is available yet.</p>}
      </section>

      <div className="framework-summary-grid">
        <ListCard
          title="Key pain points"
          items={summary.key_pain_points ?? []}
          empty="No key pain points were captured."
        />
        <ListCard
          title="Key requirements"
          items={summary.key_requirements ?? []}
          empty="No key requirements were captured."
        />
        <ListCard
          title="Target outcomes"
          items={summary.target_outcomes ?? []}
          empty="No target outcomes were captured."
        />
      </div>

      <div className="framework-summary-grid framework-summary-grid-alerts">
        <ListCard
          title="Assumptions"
          items={assumptions}
          empty="No assumptions are recorded."
          prominent
        />
        <ListCard
          title="Open questions"
          items={openQuestions}
          empty="No open questions are recorded."
          prominent
        />
        <ListCard
          title="Evidence warnings"
          items={evidenceWarnings}
          empty="Cited sources are present for the reviewed sections."
          prominent
        />
      </div>

      {!confirmed ? (
        <div className="framework-approve-panel" data-testid="framework-approve-panel">
          <label className="framework-human-confirm">
            <input
              type="checkbox"
              data-testid="framework-human-confirm"
              checked={humanConfirmed}
              disabled={!editable || busy}
              onChange={(event) => onHumanConfirmedChange(event.target.checked)}
            />
            <span>{HUMAN_CONFIRM_LABEL}</span>
          </label>
          {blocked ? (
            <p className="framework-approve-hint" data-testid="framework-approve-blocked-hint">
              Approval is locked until the blocking issues above are resolved
              {dirty ? " and your edits are saved." : "."}
            </p>
          ) : !humanConfirmed ? (
            <p className="framework-approve-hint">Tick the confirmation above to enable approval.</p>
          ) : null}
          <div className="framework-toolbar-actions">
            {editable && onSave ? (
              <button
                type="button"
                className="btn btn-secondary"
                disabled={busy || !dirty}
                onClick={onSave}
              >
                Save changes
              </button>
            ) : null}
            <button
              type="button"
              className="btn btn-primary"
              data-testid="framework-approve-button"
              disabled={busy || !canApprove}
              onClick={onApprove}
            >
              {APPROVE_BUILD_LABEL}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
