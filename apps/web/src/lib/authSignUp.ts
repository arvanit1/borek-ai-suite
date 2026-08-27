/** Interpret Supabase signUp responses — duplicate emails can look like success. */

export interface SignUpIdentity {
  id?: string;
}

export interface SignUpUser {
  identities?: SignUpIdentity[] | null;
}

export function isDuplicateSignUpEmail(user: SignUpUser | null | undefined): boolean {
  if (!user) {
    return false;
  }
  return Array.isArray(user.identities) && user.identities.length === 0;
}

export const DUPLICATE_EMAIL_MESSAGE =
  "An account with this email already exists. Please sign in instead.";

export function resolveSignUpErrorMessage(errorMessage: string): string {
  const normalized = errorMessage.toLowerCase();
  if (
    normalized.includes("already registered") ||
    normalized.includes("already exists") ||
    normalized.includes("user already registered")
  ) {
    return DUPLICATE_EMAIL_MESSAGE;
  }
  return errorMessage;
}
