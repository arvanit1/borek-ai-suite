"use client";

interface JobFailureAlertProps {
  message: string;
  retryable?: boolean;
  retrying?: boolean;
  onRetry?: () => void;
}

export function JobFailureAlert({
  message,
  retryable = false,
  retrying = false,
  onRetry,
}: JobFailureAlertProps) {
  return (
    <div className="alert alert-error" data-testid="job-failure-alert">
      <div>
        <strong>{message}</strong>
        {retryable ? <p>This failure can be retried from the last stage.</p> : null}
      </div>
      {retryable && onRetry ? (
        <button
          type="button"
          className="btn btn-secondary"
          disabled={retrying}
          onClick={onRetry}
          data-testid="job-retry-button"
        >
          {retrying ? "Retrying…" : "Retry job"}
        </button>
      ) : null}
    </div>
  );
}
