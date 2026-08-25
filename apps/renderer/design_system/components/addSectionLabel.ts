/**
 * AT-20: Reusable section eyebrow-label component (technical plan v2 §17.1).
 *
 * Fills master section-label placeholders with body typography from tokens.
 * Layout renderers must call this — never define their own eyebrow-label styling.
 */

import type PptxGenJS from "pptxgenjs";

import { MASTER_CLOSING_LABEL_PLACEHOLDER } from "../masters/MASTER_CLOSING.js";
import { MASTER_CONTENT_LABEL_PLACEHOLDER } from "../masters/MASTER_CONTENT.js";
import { MASTER_COVER_SECTION_LABEL_PLACEHOLDER } from "../masters/MASTER_COVER.js";
import { MASTER_SECTION_LABEL_PLACEHOLDER } from "../masters/MASTER_SECTION.js";
import { BorekColors, type BorekColorHex } from "../tokens/colors.js";
import { BorekTypography } from "../tokens/typography.js";

/** Default content/closing master section label placeholder (MASTER_CONTENT, MASTER_CLOSING). */
export const SECTION_LABEL_PLACEHOLDER = MASTER_CONTENT_LABEL_PLACEHOLDER;

/** Cover master section label placeholder (MASTER_COVER — BT-17). */
export const COVER_SECTION_LABEL_PLACEHOLDER = MASTER_COVER_SECTION_LABEL_PLACEHOLDER;

/** Section-divider master label placeholder (MASTER_SECTION — same name, shared styling). */
export const SECTION_DIVIDER_LABEL_PLACEHOLDER = MASTER_SECTION_LABEL_PLACEHOLDER;

/** Alias for closing layouts — same placeholder name as content slides. */
export const CLOSING_SECTION_LABEL_PLACEHOLDER = MASTER_CLOSING_LABEL_PLACEHOLDER;

export type SectionLabelVariant = "accent" | "inverse";

export type AddSectionLabelOptions = {
  /** Master placeholder name — defaults to sectionLabel. */
  placeholder?: string;
  /** accent = primary brand color; inverse = light text on dark slides (cover). */
  variant?: SectionLabelVariant;
};

/** Map section-label variant to a BorekColors token (no inline hex). */
export function resolveSectionLabelColor(variant: SectionLabelVariant): BorekColorHex {
  return variant === "inverse" ? BorekColors.background : BorekColors.primary;
}

/** Shared eyebrow-label styling — single place for body font, size, and alignment. */
export function sectionLabelTextOptions(options: AddSectionLabelOptions = {}) {
  const variant = options.variant ?? "accent";

  return {
    placeholder: options.placeholder ?? SECTION_LABEL_PLACEHOLDER,
    color: resolveSectionLabelColor(variant),
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "left" as const,
    valign: "top" as const,
  };
}

/**
 * Render section eyebrow label (e.g. "ARCHITECTURE") into a master placeholder.
 *
 * @example
 * addSectionLabel(slide, spec.sectionLabel);
 * addSectionLabel(slide, spec.sectionLabel, {
 *   placeholder: COVER_SECTION_LABEL_PLACEHOLDER,
 *   variant: "inverse",
 * });
 */
export function addSectionLabel(
  slide: PptxGenJS.Slide,
  label: string,
  options: AddSectionLabelOptions = {},
): void {
  slide.addText(label, sectionLabelTextOptions(options));
}
