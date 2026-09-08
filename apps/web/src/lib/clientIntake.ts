import type { AdditionalClientInformation, ClientContact } from "./api";

export const CLIENT_LOGO_MAX_BYTES = 5 * 1024 * 1024;
export const CLIENT_LOGO_ACCEPT = ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp";

const LOGO_EXTENSIONS: Record<string, readonly string[]> = {
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/webp": [".webp"],
};

export interface ClientLogoValidation {
  ok: boolean;
  reason?: string;
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
