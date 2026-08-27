interface UploadStepperProps {
  opportunityReady: boolean;
  fileCount: number;
  uploadedCount: number;
}

export function UploadStepper({
  opportunityReady,
  fileCount,
  uploadedCount,
}: UploadStepperProps) {
  const step2Active = opportunityReady;
  const step2Complete = uploadedCount > 0;

  return (
    <ol className="upload-stepper" aria-label="Upload workflow">
      <li className={`upload-step${opportunityReady ? " upload-step-complete" : " upload-step-active"}`}>
        <span className="upload-step-marker" aria-hidden="true">
          {opportunityReady ? "✓" : "1"}
        </span>
        <div className="upload-step-copy">
          <strong>Opportunity</strong>
          <span>{opportunityReady ? "Linked to pipeline" : "Define client context"}</span>
        </div>
      </li>
      <li
        className={`upload-step${
          step2Complete ? " upload-step-complete" : step2Active ? " upload-step-active" : ""
        }`}
      >
        <span className="upload-step-marker" aria-hidden="true">
          {step2Complete ? "✓" : "2"}
        </span>
        <div className="upload-step-copy">
          <strong>Transcripts</strong>
          <span>
            {fileCount === 0
              ? "Add discovery call files"
              : `${fileCount} file${fileCount === 1 ? "" : "s"} in queue`}
          </span>
        </div>
      </li>
    </ol>
  );
}
