/**
 * Borek web brand tokens — mirrors apps/renderer/design_system/tokens (technical plan §16).
 * CSS variables in globals.css are the runtime source; keep values aligned with this file.
 */

export const BorekBrandColors = {
  background: "#FFFFFF",
  text: "#182230",
  mutedText: "#667085",
  border: "#E4E7EC",
  primary: "#0057B8",
  primaryHover: "#004A9E",
  primarySoft: "#E8F1FB",
  coverBackground: "#182230",
} as const;

export const BorekBrandFonts = {
  heading: '"Aptos Display", "Aptos", "Segoe UI", system-ui, sans-serif',
  body: '"Aptos", "Segoe UI", system-ui, -apple-system, sans-serif',
} as const;
