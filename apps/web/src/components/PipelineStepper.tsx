interface PipelineStepperProps {
  currentStep: 1 | 2 | 3 | 4;
  frameworkReady?: boolean;
  frameworkConfirmed?: boolean;
  planReady?: boolean;
}

export function PipelineStepper({
  currentStep,
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
    <ol className="upload-stepper" aria-label="Pipeline workflow">
      {steps.map((step) => (
        <li
          key={step.id}
          className={`upload-step${
            step.complete ? " upload-step-complete" : step.active ? " upload-step-active" : ""
          }`}
        >
          <span className="upload-step-marker" aria-hidden="true">
            {step.complete ? "✓" : step.id}
          </span>
          <div className="upload-step-copy">
            <strong>{step.title}</strong>
            <span>{step.detail}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}
