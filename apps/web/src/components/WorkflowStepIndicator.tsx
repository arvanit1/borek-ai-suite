import React from "react";

export const WORKFLOW_STEP_CATALOG = [
  { id: 1 as const, label: "Intake" },
  { id: 2 as const, label: "Customer story" },
  { id: 3 as const, label: "Plan" },
  { id: 4 as const, label: "Presentation" },
];

export type WorkflowStepId = (typeof WORKFLOW_STEP_CATALOG)[number]["id"];

interface WorkflowStepIndicatorProps {
  currentStep: WorkflowStepId;
}

export function WorkflowStepIndicator({ currentStep }: WorkflowStepIndicatorProps) {
  return (
    <ol className="workflow-step-indicator" aria-label="Presentation steps">
      {WORKFLOW_STEP_CATALOG.map((step, index) => {
        const state =
          step.id === currentStep ? "current" : step.id < currentStep ? "complete" : "upcoming";
        return (
          <li
            key={step.id}
            className={`workflow-step-item is-${state}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            {index > 0 ? <span className="workflow-step-rule" aria-hidden="true" /> : null}
            <span className="workflow-step-index" aria-hidden="true">
              {state === "complete" ? "✓" : step.id}
            </span>
            <span className="workflow-step-label">{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
