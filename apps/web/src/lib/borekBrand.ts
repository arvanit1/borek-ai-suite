/**
 * Borek web brand tokens — aligned with boreksolutions.de (Elementor kit + Binox theme).
 * CSS variables in globals.css are the runtime source; keep values aligned with this file.
 *
 * Corporate site reference (Aug 2026):
 * - Primary navy: #0D1240
 * - Accent orange: #DB3D00
 * - Interactive gold: #FFCD4C
 * - Dark hero/footer: #090C28 → #0C1036 → #020611
 */

export const BorekBrandColors = {
  navy: "#0D1240",
  navyHeader: "#0D123F",
  navyDark: "#090C28",
  navyDeep: "#020611",
  accent: "#DB3D00",
  gold: "#FFCD4C",
  cream: "#FEF2ED",
  background: "#FFFFFF",
  pageBackground: "#F9F9F9",
  text: "#0D1240",
  textOnDark: "#FFFFFF",
  mutedText: "#54595F",
  border: "#E4E7EC",
  primarySoft: "#EEF0F7",
  primaryHover: "#090C28",
  coverBackground: "#090C28",
} as const;

export const BorekBrandFonts = {
  heading: '"Segoe UI", system-ui, -apple-system, sans-serif',
  body: '"Segoe UI", system-ui, -apple-system, sans-serif',
} as const;
