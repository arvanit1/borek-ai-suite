"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { JourneyStageSelector } from "@/components/JourneyStageSelector";
import { useAuth } from "@/components/AuthProvider";
import {
  getJourneyStageEligibility,
  listOpportunities,
  type JourneyStageEligibilityResponse,
  type JourneyStageName,
  type ListedOpportunityResponse,
} from "@/lib/api";
import { NEW_CLIENT_SCOPE } from "@/lib/journeyStageConfig";
import {
  NEW_CLIENT_ELIGIBILITY,
  canSubmitJourneyStage,
  defaultStartableStage,
  eligibilityForOpportunity,
} from "@/lib/journeyStageEligibility";
import { continueHref, saveSelectedJourneyStage } from "@/lib/journeyStageSelection";

interface JourneyStartPanelProps {
  heading?: string;
}

export function JourneyStartPanel({ heading = "Start a presentation" }: JourneyStartPanelProps) {
  const router = useRouter();
  const { accessToken } = useAuth();
  const [opportunities, setOpportunities] = useState<ListedOpportunityResponse[]>([]);
  const [scope, setScope] = useState<string>(NEW_CLIENT_SCOPE);
  const [eligibility, setEligibility] = useState<JourneyStageEligibilityResponse>(NEW_CLIENT_ELIGIBILITY);
  const [selected, setSelected] = useState<JourneyStageName | null>(
    defaultStartableStage(NEW_CLIENT_ELIGIBILITY),
  );
  const [loadingEligibility, setLoadingEligibility] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadOpportunities = useCallback(async () => {
    if (!accessToken) {
      setOpportunities([]);
      return;
    }
    try {
      setOpportunities(await listOpportunities(accessToken));
    } catch {
      setOpportunities([]);
    }
  }, [accessToken]);

  useEffect(() => {
    void loadOpportunities();
  }, [loadOpportunities]);

  useEffect(() => {
    let cancelled = false;

    async function loadEligibility() {
      if (scope === NEW_CLIENT_SCOPE) {
        setEligibility(NEW_CLIENT_ELIGIBILITY);
        setSelected(defaultStartableStage(NEW_CLIENT_ELIGIBILITY));
        setError(null);
        setLoadingEligibility(false);
        return;
      }
      if (!accessToken) {
        return;
      }
      setLoadingEligibility(true);
      setError(null);
      try {
        const payload = eligibilityForOpportunity(
          await getJourneyStageEligibility(accessToken, scope),
          scope,
        );
        if (!cancelled) {
          setEligibility(payload);
          setSelected(defaultStartableStage(payload));
        }
      } catch {
        if (!cancelled) {
          setError("Journey options could not be loaded for this client. Try again, or start as a new client.");
          setEligibility(NEW_CLIENT_ELIGIBILITY);
          setSelected(null);
        }
      } finally {
        if (!cancelled) {
          setLoadingEligibility(false);
        }
      }
    }

    void loadEligibility();
    return () => {
      cancelled = true;
    };
  }, [accessToken, scope]);

  const clientOptions = useMemo(
    () =>
      opportunities.map((opportunity) => ({
        id: opportunity.id,
        label: `${opportunity.client_name} — ${opportunity.opportunity_name}`,
      })),
    [opportunities],
  );

  const canContinue = canSubmitJourneyStage(eligibility, selected) && !loadingEligibility && !error;

  function handleContinue() {
    if (!selected || !canContinue) {
      return;
    }
    const opportunityId = scope === NEW_CLIENT_SCOPE ? null : scope;
    saveSelectedJourneyStage(selected, opportunityId);
    router.push(continueHref(opportunityId));
  }

  return (
    <section className="journey-start-panel" id="journey-start" data-testid="journey-start-panel">
      <div className="journey-start-copy">
        <p className="journey-start-kicker">Client journey</p>
        <h2>{heading}</h2>
        <p>
          Choose the output for this client. Later options stay locked until the previous pack
          exists. You only choose once — the same choice is used through Framework review and
          Approve.
        </p>
      </div>

      <label className="form-field journey-start-client">
        <span>Client</span>
        <select
          value={scope}
          onChange={(event) => setScope(event.target.value)}
          data-testid="journey-client-scope"
        >
          <option value={NEW_CLIENT_SCOPE}>New client</option>
          {clientOptions.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      {error ? (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      ) : null}

      {loadingEligibility ? (
        <p className="journey-start-loading">Loading available options…</p>
      ) : (
        <JourneyStageSelector
          eligibility={eligibility}
          selected={selected}
          onSelect={setSelected}
        />
      )}

      <div className="journey-start-actions">
        <button
          type="button"
          className="btn btn-primary"
          data-testid="journey-start-continue"
          disabled={!canContinue}
          onClick={handleContinue}
        >
          Continue
        </button>
      </div>
    </section>
  );
}
