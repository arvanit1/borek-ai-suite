const DEFAULT_API_URL = "http://localhost:8000";

import { getSupabaseBrowserClient } from "./supabase";
import type { FrameworkObject, FrameworkVersionResponse } from "./frameworkTypes";
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

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
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

export interface TranscriptResponse {
  id: string;
  file_name: string;
  processing_status: string;
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
): Promise<PresentationPlanGenerateResponse> {
  return apiFetch<PresentationPlanGenerateResponse>(
    `/opportunities/${opportunityId}/presentation-plan/generate`,
    accessToken,
    {
      method: "POST",
      body: JSON.stringify(
        frameworkVersionId ? { framework_version_id: frameworkVersionId } : {},
      ),
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
