import Link from "next/link";

interface PipelineStepperProps {
  currentStep: 1 | 2 | 3 | 4;
  opportunityId?: string;
  frameworkReady?: boolean;
  frameworkConfirmed?: boolean;
  planReady?: boolean;
}

function stepHref(stepId: number, opportunityId?: string): string {
  if (stepId === 1) {
    return "/upload";
  }
  const path =
    stepId === 2 ? "/framework-review" : stepId === 3 ? "/plan-preview" : "/deck-center";
  return opportunityId ? `${path}?opportunityId=${encodeURIComponent(opportunityId)}` : path;
}

export function PipelineStepper({
  currentStep,
  opportunityId,
  frameworkReady = false,
  frameworkConfirmed = false,
  planReady = false,
}: PipelineStepperProps) {
  const steps = [
    {
      id: 1,
      title: "Upload",
      detail: currentStep > 1 ? "Transcripts ingested" : "Attach discovery calls",
      complete: currentStep > 1,
      active: currentStep === 1,
    },
    {
      id: 2,
      title: "Framework",
      detail: frameworkConfirmed
        ? "Confirmed"
        : frameworkReady
          ? "Draft ready for review"
          : "Generate and review 14 chapters",
      complete: frameworkConfirmed,
      active: currentStep === 2,
    },
    {
      id: 3,
      title: "Plan",
      detail: planReady ? "Slide plan ready" : "Preview slide order and layouts",
      complete: planReady,
      active: currentStep === 3,
    },
    {
      id: 4,
      title: "Deck",
      detail: "Preview slides and download",
      complete: false,
      active: currentStep === 4,
    },
  ] as const;

  return (
    <ol className="pipeline-rail" aria-label="Pipeline workflow">
      {steps.map((step) => (
        <li
          key={step.id}
          className={`pipeline-rail-step${
            step.complete ? " pipeline-rail-complete" : step.active ? " pipeline-rail-active" : ""
          }`}
        >
          <Link href={stepHref(step.id, opportunityId)} className="pipeline-rail-link">
            <span className="pipeline-rail-index" aria-hidden="true">
              {step.complete ? "✓" : step.id}
            </span>
            <span className="pipeline-rail-copy">
              <strong>{step.title}</strong>
              <span>{step.detail}</span>
            </span>
          </Link>
        </li>
      ))}
    </ol>
  );
}
