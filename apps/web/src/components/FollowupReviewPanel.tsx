"use client";

import { useEffect, useState } from "react";

import { FollowupReviewView } from "@/components/FollowupReviewView";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/components/AuthProvider";
import { getOpportunity, updateOpportunity, type OpportunityResponse } from "@/lib/api";
import workshopClear from "../../../../packages/contracts/fixtures/followup_extraction/workshop_clear.json";
import {
  canConfirmFollowupReview,
  emptyFollowupChecklist,
  emptyFollowupProjectStatics,
  renderFollowupDraft,
  validateFollowupProjectStatics,
  type FollowupChecklistId,
  type FollowupDraft,
  type FollowupExtraction,
  type FollowupProjectStatics,
} from "@/lib/followupReview";

export function FollowupReviewPanel({ opportunityId }: { opportunityId: string }) {
  const { accessToken, session, loading: authLoading } = useAuth();
  const [opportunity, setOpportunity] = useState<OpportunityResponse | null>(null);
  const [statics, setStatics] = useState<FollowupProjectStatics>(emptyFollowupProjectStatics);
  const [staticsSaved, setStaticsSaved] = useState(false);
  const [draft, setDraft] = useState<FollowupDraft | null>(null);
  const [checklist, setChecklist] = useState(emptyFollowupChecklist);
  const [acknowledgedFlags, setAcknowledgedFlags] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!accessToken) return;
      setOpportunity(null);
      setStatics(emptyFollowupProjectStatics());
      setStaticsSaved(false);
      setDraft(null);
      setChecklist(emptyFollowupChecklist());
      setAcknowledgedFlags(new Set());
      setInfo(null);
      setBusy(true);
      setError(null);
      try {
        const loaded = await getOpportunity(accessToken, opportunityId);
        if (!active) return;
        setOpportunity(loaded);
        if (loaded.followup_statics) {
          setStatics(loaded.followup_statics);
          setStaticsSaved(true);
          setDraft(renderFollowupDraft(workshopClear as FollowupExtraction, loaded.followup_statics));
        }
      } catch {
        if (active) setError("This opportunity's follow-up review could not be loaded.");
      } finally {
        if (active) setBusy(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [accessToken, opportunityId]);

  function handleStaticsChange(value: FollowupProjectStatics) {
    setStatics(value);
    setStaticsSaved(false);
    setInfo(null);
    setDraft(null);
    setChecklist(emptyFollowupChecklist());
    setAcknowledgedFlags(new Set());
  }

  async function handleSaveStatics() {
    if (!accessToken) return;
    const validation = validateFollowupProjectStatics(statics);
    if (validation.length) {
      setError(validation[0]);
      return;
    }
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const saved = await updateOpportunity(accessToken, opportunityId, { followup_statics: statics });
      if (!saved.followup_statics) throw new Error("Missing saved project statics");
      setOpportunity(saved);
      setStatics(saved.followup_statics);
      setStaticsSaved(true);
      setDraft(renderFollowupDraft(workshopClear as FollowupExtraction, saved.followup_statics));
      setChecklist(emptyFollowupChecklist());
      setAcknowledgedFlags(new Set());
      setInfo("Project email settings saved. Review the fixture draft below.");
    } catch {
      setError("Project email settings could not be saved. Check the values and try again.");
    } finally {
      setBusy(false);
    }
  }

  function handleFlagChange(flag: string, checked: boolean) {
    setAcknowledgedFlags((current) => {
      const next = new Set(current);
      if (checked) next.add(flag);
      else next.delete(flag);
      return next;
    });
  }

  function handleDraftChange(value: FollowupDraft) {
    setDraft(value);
    setChecklist(emptyFollowupChecklist());
    setAcknowledgedFlags(new Set());
    setInfo(null);
  }

  function handleConfirm() {
    if (!canConfirmFollowupReview(draft, statics, checklist, acknowledgedFlags, staticsSaved)) {
      return;
    }
    setDraft((current) => current ? { ...current, status: "reviewed" } : current);
    setInfo("Fixture reviewed - not sent. No Outlook or send API was called.");
  }

  const canConfirm = canConfirmFollowupReview(
    draft,
    statics,
    checklist,
    acknowledgedFlags,
    staticsSaved,
  );

  return (
    <div className="app-workspace">
      <SiteHeader signedInEmail={session?.user.email} />
      <main className="app-shell app-workspace-body">
        {authLoading ? <p className="recent-state-card">Loading follow-up review...</p> : null}
        {!authLoading && !accessToken ? <p className="alert alert-info">Sign in to review this follow-up.</p> : null}
        {!authLoading && accessToken ? (
          <FollowupReviewView
            clientName={opportunity?.client_name ?? "Client"}
            opportunityName={opportunity?.opportunity_name ?? "Opportunity"}
            statics={statics}
            staticsSaved={staticsSaved}
            draft={draft}
            checklist={checklist}
            acknowledgedFlags={acknowledgedFlags}
            canConfirm={canConfirm}
            busy={busy}
            error={error}
            info={info}
            onStaticsChange={handleStaticsChange}
            onSaveStatics={() => void handleSaveStatics()}
            onDraftChange={handleDraftChange}
            onChecklistChange={(id: FollowupChecklistId, checked: boolean) => setChecklist((current) => ({ ...current, [id]: checked }))}
            onFlagChange={handleFlagChange}
            onConfirm={handleConfirm}
          />
        ) : null}
      </main>
    </div>
  );
}
