const DEFAULT_API_URL = "http://localhost:8000";

import { formatJobFailureMessage } from "./jobErrors";
import { getSupabaseBrowserClient } from "./supabase";
import type { FrameworkObject, FrameworkVersionResponse } from "./frameworkTypes";
import type { FrameworkReviewPayload } from "./frameworkReview";
import type {
  PresentationPlanGenerateResponse,
  PresentationPlanResponse,
} from "./planTypes";
import type {
  DeckCenterResponse,
  PresentationGenerateResponse,
  PresentationResponse,
} from "./deckTypes";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || DEFAULT_API_URL;
}

async function resolveAccessToken(fallback: string): Promise<string> {
  const client = getSupabaseBrowserClient();
  if (client) {
    const { data } = await client.auth.getSession();
    if (data.session?.access_token) {
      return data.session.access_token;
    }
  }
  return fallback;
}

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
  };
}

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly retryable?: boolean;
  readonly jobId?: string;
  readonly stage?: string;

  constructor(
    message: string,
    status: number,
    code?: string,
    extras?: { retryable?: boolean; jobId?: string; stage?: string },
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.retryable = extras?.retryable;
    this.jobId = extras?.jobId;
    this.stage = extras?.stage;
  }
}

export interface JobErrorDetail {
  code: string;
  message: string;
  stage: string;
  retryable: boolean;
}

export interface JobResponse {
  job_id: string;
  job_type: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  current_stage: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  result: Record<string, unknown>;
  error: JobErrorDetail | null;
}

export interface ActiveJobResponse {
  job_id: string;
  job_type: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  current_stage: string;
  started_at: string | null;
  error: JobErrorDetail | null;
}

async function parseError(response: Response): Promise<ApiRequestError> {
  let message = `Request failed (${response.status})`;
  let code: string | undefined;
  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body.error?.message) {
      message = body.error.message;
    }
    code = body.error?.code;
  } catch {
    // Response body is not JSON — keep default message.
  }
  return new ApiRequestError(message, response.status, code);
}

export async function apiFetch<T>(
  path: string,
  accessToken: string,
  init: RequestInit = {},
): Promise<T> {
  const token = await resolveAccessToken(accessToken);
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function getJob(
  accessToken: string,
  jobId: string,
): Promise<JobResponse> {
  return apiFetch<JobResponse>(`/jobs/${jobId}`, accessToken);
}

export async function retryJob(
  accessToken: string,
  jobId: string,
  fromStage?: string,
): Promise<JobEnqueueResponse> {
  const query = fromStage ? `?from_stage=${fromStage}` : "";
  return apiFetch<JobEnqueueResponse>(`/jobs/${jobId}/retry${query}`, accessToken, {
    method: "POST",
  });
}

export interface JobEnqueueResponse {
  job_id: string;
  status: string;
  is_existing_job?: boolean;
}

export async function getActiveJob(
  accessToken: string,
  opportunityId: string,
  stageGroup?: "framework" | "presentation",
): Promise<ActiveJobResponse | null> {
  const query = stageGroup ? `?stage_group=${stageGroup}` : "";
  try {
    return await apiFetch<ActiveJobResponse>(
      `/opportunities/${opportunityId}/jobs/active${query}`,
      accessToken,
    );
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function getLatestOpportunityJob(
  accessToken: string,
  opportunityId: string,
): Promise<JobResponse | null> {
  return apiFetch<JobResponse | null>(
    `/opportunities/${opportunityId}/jobs/latest`,
    accessToken,
  );
}

/** Maximum client-side wait for long-running generation jobs (12 minutes). */
export const FRAMEWORK_JOB_TIMEOUT_MS = 720_000;

export async function waitForJob(
  accessToken: string,
  jobId: string,
  timeoutMs = FRAMEWORK_JOB_TIMEOUT_MS,
): Promise<JobResponse> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const job = await getJob(accessToken, jobId);
    if (job.status === "COMPLETED") {
      return job;
    }
    if (job.status === "FAILED") {
      throw new ApiRequestError(
        formatJobFailureMessage(job.error),
        422,
        job.error?.code,
        {
          retryable: Boolean(job.error?.retryable),
          jobId: job.job_id,
          stage: job.error?.stage,
        },
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new ApiRequestError("Generation job timed out", 408, "JOB_TIMEOUT", { jobId });
}

export async function apiFetchBlob(
  path: string,
  accessToken: string,
  init: RequestInit = {},
): Promise<Blob> {
  const token = await resolveAccessToken(accessToken);
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  return response.blob();
}

export interface OpportunityCreatePayload {
  client_name: string;
  opportunity_name: string;
  department: string;
  language: string;
}

export interface OpportunityResponse {
  id: string;
  client_name: string;
  opportunity_name: string;
  department: string;
  language: string;
  status: string;
}

export interface ListedOpportunityResponse extends OpportunityResponse {
  pii_redaction_enabled: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface TranscriptResponse {
  id: string;
  file_name: string;
  processing_status: string;
  created_at: string;
}

export interface TranscriptUploadResponse {
  transcript: TranscriptResponse;
  processing_status: string;
}

export async function createOpportunity(
  accessToken: string,
  payload: OpportunityCreatePayload,
): Promise<OpportunityResponse> {
  return apiFetch<OpportunityResponse>("/opportunities", accessToken, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getOpportunity(
  accessToken: string,
  opportunityId: string,
): Promise<OpportunityResponse> {
  return apiFetch<OpportunityResponse>(`/opportunities/${opportunityId}`, accessToken);
}

export async function listOpportunities(
  accessToken: string,
): Promise<ListedOpportunityResponse[]> {
  return apiFetch<ListedOpportunityResponse[]>("/opportunities", accessToken);
}

export async function listTranscripts(
  accessToken: string,
  opportunityId: string,
): Promise<TranscriptResponse[]> {
  return apiFetch<TranscriptResponse[]>(
    `/opportunities/${opportunityId}/transcripts`,
    accessToken,
  );
}

export async function uploadTranscript(
  accessToken: string,
  opportunityId: string,
  file: File,
): Promise<TranscriptUploadResponse> {
  const formData = new FormData();
  formData.append("file", file, file.name);
  return apiFetch<TranscriptUploadResponse>(
    `/opportunities/${opportunityId}/transcripts`,
    accessToken,
    {
      method: "POST",
      body: formData,
    },
  );
}

export interface FrameworkGenerateResponse {
  job_id: string;
  status: string;
  framework_version_id: string | null;
  is_existing_job?: boolean;
}

export type { FrameworkVersionResponse };

export async function getLatestFramework(
  accessToken: string,
  opportunityId: string,
): Promise<FrameworkVersionResponse> {
  return apiFetch<FrameworkVersionResponse>(
    `/opportunities/${opportunityId}/framework`,
    accessToken,
  );
}

export async function getFrameworkReview(
  accessToken: string,
  opportunityId: string,
): Promise<FrameworkReviewPayload> {
  return apiFetch<FrameworkReviewPayload>(
    `/opportunities/${opportunityId}/framework/review`,
    accessToken,
  );
}

export async function generateFramework(
  accessToken: string,
  opportunityId: string,
): Promise<FrameworkGenerateResponse> {
  return apiFetch<FrameworkGenerateResponse>(
    `/opportunities/${opportunityId}/framework/generate`,
    accessToken,
    { method: "POST" },
  );
}

export interface FrameworkJobEnqueueResponse {
  job_id: string;
  status: string;
  is_existing_job?: boolean;
}

export async function regenerateFrameworkChapter(
  accessToken: string,
  opportunityId: string,
  chapterId: string,
): Promise<FrameworkJobEnqueueResponse> {
  return apiFetch<FrameworkJobEnqueueResponse>(
    `/opportunities/${opportunityId}/framework/regenerate-chapter`,
    accessToken,
    {
      method: "POST",
      body: JSON.stringify({ chapter_id: chapterId }),
    },
  );
}

export async function updateFramework(
  accessToken: string,
  opportunityId: string,
  frameworkJson: FrameworkObject,
): Promise<FrameworkVersionResponse> {
  return apiFetch<FrameworkVersionResponse>(
    `/opportunities/${opportunityId}/framework`,
    accessToken,
    {
      method: "PATCH",
      body: JSON.stringify({ framework_json: frameworkJson }),
    },
  );
}

export async function confirmFramework(
  accessToken: string,
  opportunityId: string,
  frameworkVersionId?: string,
): Promise<FrameworkVersionResponse> {
  return apiFetch<FrameworkVersionResponse>(
    `/opportunities/${opportunityId}/framework/confirm`,
    accessToken,
    {
      method: "POST",
      body: JSON.stringify(
        frameworkVersionId ? { framework_version_id: frameworkVersionId } : {},
      ),
    },
  );
}

export type { PresentationPlanResponse, PresentationPlanGenerateResponse };

export async function getLatestPresentationPlan(
  accessToken: string,
  opportunityId: string,
): Promise<PresentationPlanResponse> {
  return apiFetch<PresentationPlanResponse>(
    `/opportunities/${opportunityId}/presentation-plan`,
    accessToken,
  );
}

export async function generatePresentationPlan(
  accessToken: string,
  opportunityId: string,
  frameworkVersionId?: string,
  autoContinue = false,
): Promise<PresentationPlanGenerateResponse> {
  return apiFetch<PresentationPlanGenerateResponse>(
    `/opportunities/${opportunityId}/presentation-plan/generate`,
    accessToken,
    {
      method: "POST",
      body: JSON.stringify({
        ...(frameworkVersionId ? { framework_version_id: frameworkVersionId } : {}),
        ...(autoContinue ? { auto_continue: true } : {}),
      }),
    },
  );
}

export type {
  DeckCenterResponse,
  PresentationGenerateResponse,
  PresentationResponse,
};

export async function getLatestPresentation(
  accessToken: string,
  opportunityId: string,
): Promise<PresentationResponse> {
  return apiFetch<PresentationResponse>(
    `/opportunities/${opportunityId}/presentation`,
    accessToken,
  );
}

export async function getPresentationPlan(
  accessToken: string,
  presentationPlanId: string,
): Promise<PresentationPlanResponse> {
  return apiFetch<PresentationPlanResponse>(
    `/presentation-plans/${presentationPlanId}`,
    accessToken,
  );
}

export async function getPresentation(
  accessToken: string,
  presentationId: string,
): Promise<PresentationResponse> {
  return apiFetch<PresentationResponse>(
    `/presentations/${presentationId}`,
    accessToken,
  );
}

export async function generatePresentation(
  accessToken: string,
  opportunityId: string,
  presentationPlanId?: string,
): Promise<PresentationGenerateResponse> {
  return apiFetch<PresentationGenerateResponse>(
    `/opportunities/${opportunityId}/presentation/generate`,
    accessToken,
    {
      method: "POST",
      body: JSON.stringify(
        presentationPlanId ? { presentation_plan_id: presentationPlanId } : {},
      ),
    },
  );
}

export async function getDeckCenter(
  accessToken: string,
  presentationId: string,
): Promise<DeckCenterResponse> {
  return apiFetch<DeckCenterResponse>(`/presentations/${presentationId}/deck`, accessToken);
}

export async function fetchSlidePreviewBlob(
  accessToken: string,
  previewPath: string,
): Promise<Blob> {
  return apiFetchBlob(previewPath, accessToken);
}

export async function downloadPresentationFile(
  accessToken: string,
  downloadPath: string,
): Promise<Blob> {
  return apiFetchBlob(downloadPath, accessToken);
}

export async function downloadFrameworkRender(
  accessToken: string,
  renderPath: string,
): Promise<Blob> {
  return apiFetchBlob(renderPath, accessToken);
}

export async function regeneratePresentationSlide(
  accessToken: string,
  presentationId: string,
  slideId: string,
): Promise<JobEnqueueResponse> {
  return apiFetch<JobEnqueueResponse>(
    `/presentations/${presentationId}/slides/${slideId}/regenerate`,
    accessToken,
    { method: "POST" },
  );
}

export async function changePresentationSlideLayout(
  accessToken: string,
  presentationId: string,
  slideId: string,
  layoutId: string,
): Promise<JobEnqueueResponse> {
  return apiFetch<JobEnqueueResponse>(
    `/presentations/${presentationId}/slides/${slideId}/change-layout`,
    accessToken,
    {
      method: "POST",
      body: JSON.stringify({ layout_id: layoutId }),
    },
  );
}
