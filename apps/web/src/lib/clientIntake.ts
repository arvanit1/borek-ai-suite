import type { AdditionalClientInformation, ClientContact } from "./api";

export const CLIENT_LOGO_MAX_BYTES = 5 * 1024 * 1024;
export const CLIENT_LOGO_ACCEPT = ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp";
export const CLIENT_INFORMATION_FILE_MAX_BYTES = 5 * 1024 * 1024;
export const CLIENT_INFORMATION_NOTES_MAX = 20_000;
export const CLIENT_INFORMATION_FILE_ACCEPT =
  ".txt,.md,.csv,.json,text/plain,text/markdown,text/csv,application/json";
const CLIENT_INFORMATION_FILE_EXTENSIONS = [".txt", ".md", ".csv", ".json"] as const;

const LOGO_EXTENSIONS: Record<string, readonly string[]> = {
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/webp": [".webp"],
};

export interface ClientLogoValidation {
  ok: boolean;
  reason?: string;
}

export function additionalClientInformationError(
  value: AdditionalClientInformation | null | undefined,
): string | undefined {
  const incompleteContact = value?.contacts.some((contact) =>
    !contact.name.trim() &&
    Boolean(contact.role?.trim() || contact.email?.trim() || contact.phone?.trim()),
  );
  return incompleteContact ? "Add a name for each client contact, or remove their other details." : undefined;
}

export function validateClientLogoFile(file: Pick<File, "name" | "size" | "type">): ClientLogoValidation {
  const mime = file.type.toLowerCase();
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!LOGO_EXTENSIONS[mime]?.includes(extension)) {
    return { ok: false, reason: "Use a PNG, JPEG, or WebP image whose extension matches its format." };
  }
  if (file.size === 0) {
    return { ok: false, reason: "This image is empty. Choose another logo." };
  }
  if (file.size > CLIENT_LOGO_MAX_BYTES) {
    return { ok: false, reason: "The client logo must be 5 MiB or smaller." };
  }
  return { ok: true };
}

export function validateClientInformationFile(
  file: Pick<File, "name" | "size">,
): ClientLogoValidation {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!(CLIENT_INFORMATION_FILE_EXTENSIONS as readonly string[]).includes(extension)) {
    return { ok: false, reason: "Use a TXT, Markdown, CSV, or JSON file." };
  }
  if (file.size === 0) {
    return { ok: false, reason: "This file is empty. Choose another file." };
  }
  if (file.size > CLIENT_INFORMATION_FILE_MAX_BYTES) {
    return { ok: false, reason: "Each file must be 5 MiB or smaller." };
  }
  return { ok: true };
}

function fileNoteHeader(fileName: string): string {
  return `--- ${fileName} ---`;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function removeClientInformationFileNote(
  notes: string | null | undefined,
  fileName: string,
): string | null {
  if (!notes) {
    return null;
  }
  const header = escapeRegExp(fileNoteHeader(fileName));
  const next = notes
    .replace(new RegExp(`(?:^|\\n\\n)${header}\\n[\\s\\S]*?(?=\\n--- |$)`), "")
    .trim();
  return next || null;
}

export function appendClientInformationFileNote(
  notes: string | null | undefined,
  fileName: string,
  content: string,
): { notes: string; error?: string } {
  const body = content.replace(/\s+$/u, "");
  const block = `${fileNoteHeader(fileName)}\n${body}\n`;
  const remainder = removeClientInformationFileNote(notes, fileName);
  const next = remainder ? `${remainder}\n\n${block}` : block;
  if (next.length > CLIENT_INFORMATION_NOTES_MAX) {
    return {
      notes: notes?.trim() || "",
      error: "Notes cannot exceed 20,000 characters. Choose a shorter file or trim the notes field.",
    };
  }
  return { notes: next };
}

function cleanList(values: readonly string[] | undefined): string[] {
  return (values ?? []).map((value) => value.trim()).filter(Boolean);
}

function cleanContact(contact: ClientContact): ClientContact | null {
  const name = contact.name.trim();
  const role = contact.role?.trim() || null;
  const email = contact.email?.trim() || null;
  const phone = contact.phone?.trim() || null;
  if (!name && !role && !email && !phone) {
    return null;
  }
  return { name, role, email, phone };
}

export function compactAdditionalClientInformation(
  value: AdditionalClientInformation | null | undefined,
): AdditionalClientInformation | undefined {
  if (!value) {
    return undefined;
  }
  const compacted: AdditionalClientInformation = {
    location_requirements: cleanList(value.location_requirements),
    constraints: cleanList(value.constraints),
    contacts: value.contacts.map(cleanContact).filter((contact): contact is ClientContact => Boolean(contact)),
    priorities: cleanList(value.priorities),
    notes: value.notes?.trim() || null,
  };
  return compacted.location_requirements.length ||
    compacted.constraints.length ||
    compacted.contacts.length ||
    compacted.priorities.length ||
    compacted.notes
    ? compacted
    : undefined;
}
