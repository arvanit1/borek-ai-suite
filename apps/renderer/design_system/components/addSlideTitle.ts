/**
 * AT-19: Reusable slide title component (technical plan v2 §17.1).
 *
 * Fills master title placeholders with heading typography from tokens.
 * Layout renderers must call this — never define their own title styling.
 */

import type PptxGenJS from "pptxgenjs";

import { MASTER_CLOSING_TITLE_PLACEHOLDER } from "../masters/MASTER_CLOSING.js";
import { MASTER_CONTENT_TITLE_PLACEHOLDER } from "../masters/MASTER_CONTENT.js";
import { MASTER_COVER_TITLE_PLACEHOLDER } from "../masters/MASTER_COVER.js";
import { MASTER_SECTION_TITLE_PLACEHOLDER } from "../masters/MASTER_SECTION.js";
import { BorekColors, type BorekColorHex } from "../tokens/colors.js";
import { BorekTypography } from "../tokens/typography.js";

/** Default content/closing master title placeholder (MASTER_CONTENT, MASTER_CLOSING). */
export const SLIDE_TITLE_PLACEHOLDER = MASTER_CONTENT_TITLE_PLACEHOLDER;

/** Cover master title placeholder (MASTER_COVER — BT-17). */
export const COVER_TITLE_PLACEHOLDER = MASTER_COVER_TITLE_PLACEHOLDER;

/** Section-divider master title placeholder (MASTER_SECTION). */
export const SECTION_TITLE_PLACEHOLDER = MASTER_SECTION_TITLE_PLACEHOLDER;

/** Alias kept for closing layouts — same placeholder name as content slides. */
export const CLOSING_TITLE_PLACEHOLDER = MASTER_CLOSING_TITLE_PLACEHOLDER;

export type SlideTitleVariant = "light" | "dark";

export type AddSlideTitleOptions = {
  /** Master placeholder name — defaults to slideTitle. */
  placeholder?: string;
  /** light = dark text on light slides; dark = light text on dark slides. */
  variant?: SlideTitleVariant;
};

/** Map title variant to a BorekColors token (no inline hex). */
export function resolveSlideTitleColor(variant: SlideTitleVariant): BorekColorHex {
  return variant === "dark" ? BorekColors.background : BorekColors.text;
}

/** Shared title styling — single place for heading font, size, and alignment. */
export function slideTitleTextOptions(options: AddSlideTitleOptions = {}) {
  const variant = options.variant ?? "light";

  return {
    placeholder: options.placeholder ?? SLIDE_TITLE_PLACEHOLDER,
    color: resolveSlideTitleColor(variant),
    fontFace: BorekTypography.fonts.heading,
    fontSize: BorekTypography.defaultSizes.heading,
    align: "left" as const,
    valign: "top" as const,
  };
}

/**
 * Render primary slide heading into a master title placeholder.
 *
 * @example
 * addSlideTitle(slide, spec.title);
 * addSlideTitle(slide, spec.title, { placeholder: COVER_TITLE_PLACEHOLDER, variant: "dark" });
 */
export function addSlideTitle(
  slide: PptxGenJS.Slide,
  title: string,
  options: AddSlideTitleOptions = {},
): void {
  slide.addText(title, slideTitleTextOptions(options));
}
