/**
 * Transcript upload format rules — mirrors API ALLOWED_TRANSCRIPT_EXTENSIONS (AT-40).
 */

export const ALLOWED_TRANSCRIPT_EXTENSIONS = [".txt", ".vtt", ".srt", ".docx"] as const;

export type AllowedTranscriptExtension = (typeof ALLOWED_TRANSCRIPT_EXTENSIONS)[number];

export interface TranscriptValidationResult {
  ok: boolean;
  extension: string;
  reason?: string;
}

export function getFileExtension(fileName: string): string {
  const trimmed = fileName.trim();
  const dotIndex = trimmed.lastIndexOf(".");
  if (dotIndex <= 0 || dotIndex === trimmed.length - 1) {
    return "";
  }
  return trimmed.slice(dotIndex).toLowerCase();
}

export function validateTranscriptFileName(fileName: string): TranscriptValidationResult {
  const extension = getFileExtension(fileName);
  if (!extension) {
    return {
      ok: false,
      extension,
      reason: "File must have an extension (.txt, .vtt, .srt, or .docx).",
    };
  }
  if (!ALLOWED_TRANSCRIPT_EXTENSIONS.includes(extension as AllowedTranscriptExtension)) {
    return {
      ok: false,
      extension,
      reason: `Unsupported format ${extension}. Allowed: ${ALLOWED_TRANSCRIPT_EXTENSIONS.join(", ")}.`,
    };
  }
  return { ok: true, extension };
}

export function validateTranscriptFile(file: File): TranscriptValidationResult {
  return validateTranscriptFileName(file.name);
}

export function isUploadableTranscriptFile(file: File): boolean {
  return validateTranscriptFile(file).ok;
}
