/** JJ-20 shared markers: languages, special characters, and long names. */

export const JJ20_ENGLISH = "Controlled automation";
export const JJ20_GERMAN = "Geprüfte Automatisierung";
export const JJ20_SPECIAL = "ä ö ü Ä Ö Ü ß & / % + (Pilot's)";

export function xmlForAssert(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("'", "&apos;");
}

export function padTo(value: string, length: number, fill = "X"): string {
  if (value.length >= length) {
    return value.slice(0, length);
  }
  return value.padEnd(length, fill);
}
