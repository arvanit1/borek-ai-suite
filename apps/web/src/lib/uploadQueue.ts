import { validateTranscriptFile, type TranscriptValidationResult } from "./transcriptFormats";

export type FileUploadStatus = "rejected" | "pending" | "uploading" | "success" | "error";

export interface TranscriptQueueItem {
  id: string;
  file: File;
  fileName: string;
  status: FileUploadStatus;
  validation: TranscriptValidationResult;
  errorMessage?: string;
  transcriptId?: string;
}

let queueCounter = 0;

export function createQueueItemId(): string {
  queueCounter += 1;
  return `queue-${queueCounter}`;
}

export function createQueueItem(file: File, id = createQueueItemId()): TranscriptQueueItem {
  const validation = validateTranscriptFile(file);
  return {
    id,
    file,
    fileName: file.name,
    validation,
    status: validation.ok ? "pending" : "rejected",
    errorMessage: validation.ok ? undefined : validation.reason,
  };
}

export function createQueueItems(files: Iterable<File>): TranscriptQueueItem[] {
  return Array.from(files, (file) => createQueueItem(file));
}

export function countByStatus(items: TranscriptQueueItem[]): Record<FileUploadStatus, number> {
  const counts: Record<FileUploadStatus, number> = {
    rejected: 0,
    pending: 0,
    uploading: 0,
    success: 0,
    error: 0,
  };
  for (const item of items) {
    counts[item.status] += 1;
  }
  return counts;
}

export function getUploadableItems(items: TranscriptQueueItem[]): TranscriptQueueItem[] {
  return items.filter((item) => item.status === "pending");
}

export function hasUploadableItems(items: TranscriptQueueItem[]): boolean {
  return getUploadableItems(items).length > 0;
}

export function updateQueueItem(
  items: TranscriptQueueItem[],
  id: string,
  patch: Partial<Pick<TranscriptQueueItem, "status" | "errorMessage" | "transcriptId">>,
): TranscriptQueueItem[] {
  return items.map((item) => (item.id === id ? { ...item, ...patch } : item));
}

export function removeQueueItem(items: TranscriptQueueItem[], id: string): TranscriptQueueItem[] {
  return items.filter((item) => item.id !== id);
}

export function statusLabel(status: FileUploadStatus): string {
  switch (status) {
    case "rejected":
      return "Rejected";
    case "pending":
      return "Ready";
    case "uploading":
      return "Uploading";
    case "success":
      return "Uploaded";
    case "error":
      return "Failed";
    default:
      return status;
  }
}
