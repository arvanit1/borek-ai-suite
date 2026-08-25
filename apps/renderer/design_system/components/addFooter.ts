/**
 * AT-21: Reusable footer component (technical plan v2 §17.1, §16.1).
 *
 * Fills the client/opportunity footer placeholder with branding typography from tokens.
 * Layout renderers must call this — never define their own footer styling.
 */

import type PptxGenJS from "pptxgenjs";

import { MASTER_DEFAULT_FOOTER_PLACEHOLDER } from "../masters/MASTER_DEFAULT.js";
import { BorekBranding } from "../tokens/branding.js";

/** Footer placeholder name — shared across all slide masters (AT-14..18). */
export const FOOTER_PLACEHOLDER = MASTER_DEFAULT_FOOTER_PLACEHOLDER;

/** Canonical separator between client name and opportunity title in the footer band. */
export const FOOTER_LABEL_SEPARATOR = " · ";

export type FooterLabelInput = {
  clientName: string;
  opportunityTitle: string;
};

/** Build consistent client/opportunity footer copy (technical plan §16.1). */
export function formatFooterLabel(input: FooterLabelInput): string {
  const clientName = input.clientName.trim();
  const opportunityTitle = input.opportunityTitle.trim();
  if (!clientName) {
    return opportunityTitle;
  }
  if (!opportunityTitle) {
    return clientName;
  }
  return `${clientName}${FOOTER_LABEL_SEPARATOR}${opportunityTitle}`;
}

/** Shared footer styling — single place for muted body typography and alignment. */
export function footerTextOptions() {
  const { footer } = BorekBranding;

  return {
    placeholder: FOOTER_PLACEHOLDER,
    color: footer.color,
    fontFace: footer.fontFace,
    fontSize: footer.fontSize,
    align: "left" as const,
    valign: footer.valign,
  };
}

/**
 * Render client/opportunity footer text into the master footer placeholder.
 *
 * @example
 * addFooter(slide, formatFooterLabel({ clientName: "Borek Solutions", opportunityTitle: spec.title }));
 * addFooter(slide, "Borek Solutions · Invoice 3-Way Match Automation");
 */
export function addFooter(slide: PptxGenJS.Slide, label: string): void {
  slide.addText(label, footerTextOptions());
}
