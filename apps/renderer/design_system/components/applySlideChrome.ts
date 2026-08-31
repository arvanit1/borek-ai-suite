/**
 * Shared slide chrome: logo, client/opportunity footer, and leftover master prompts.
 *
 * PptxGenJS leaves unfilled body placeholders as PowerPoint "Click to add text".
 * Layouts draw cards/steps as shapes, so unused master slots stay empty unless
 * we consume them here. Closing leftovers apply to any dark MASTER_CLOSING slide,
 * not only NEXT_STEPS_01.
 */

import type PptxGenJS from "pptxgenjs";

import {
  MASTER_CLOSING_CHECKLIST_PLACEHOLDER,
  MASTER_CLOSING_STEPS_PLACEHOLDER,
} from "../masters/MASTER_CLOSING.js";
import {
  MASTER_CONTENT_LABEL_PLACEHOLDER,
} from "../masters/MASTER_CONTENT.js";
import {
  MASTER_COVER_STAT_BADGE_PLACEHOLDER_1,
  MASTER_COVER_STAT_BADGE_PLACEHOLDER_2,
  MASTER_COVER_STAT_BADGE_PLACEHOLDER_3,
} from "../masters/MASTER_COVER.js";
import { addFooter, formatFooterLabel } from "./addFooter.js";
import { addLogo, type LogoVariant } from "./addLogo.js";

/** Default left-hand footer client label (AT-21 examples / Borek Solutions). */
export const DEFAULT_CLIENT_NAME = "Borek Solutions";

const CLOSING_MASTER_LAYOUTS = new Set(["COMPLIANCE_01", "NEXT_STEPS_01"]);

export type SlideChromeOptions = {
  opportunityTitle: string;
  clientName?: string;
  layoutId?: string;
  sectionLabel?: string;
  darkBackground?: boolean;
};

export function usesClosingMaster(options: SlideChromeOptions): boolean {
  return Boolean(options.darkBackground) && CLOSING_MASTER_LAYOUTS.has(options.layoutId ?? "");
}

export function logoVariantForSlide(options: SlideChromeOptions): LogoVariant {
  if (options.layoutId === "COVER_01" || usesClosingMaster(options)) {
    return "dark";
  }
  return "light";
}

export function leftoverPlaceholdersForSlide(options: SlideChromeOptions): readonly string[] {
  if (options.layoutId === "COVER_01") {
    return [
      MASTER_COVER_STAT_BADGE_PLACEHOLDER_1,
      MASTER_COVER_STAT_BADGE_PLACEHOLDER_2,
      MASTER_COVER_STAT_BADGE_PLACEHOLDER_3,
    ];
  }

  const leftovers: string[] = [];
  if (!options.sectionLabel) {
    leftovers.push(MASTER_CONTENT_LABEL_PLACEHOLDER);
  }
  if (usesClosingMaster(options)) {
    leftovers.push(MASTER_CLOSING_CHECKLIST_PLACEHOLDER, MASTER_CLOSING_STEPS_PLACEHOLDER);
  }
  return leftovers;
}

export function applySlideChrome(slide: PptxGenJS.Slide, options: SlideChromeOptions): void {
  addLogo(slide, logoVariantForSlide(options));
  addFooter(
    slide,
    formatFooterLabel({
      clientName: options.clientName ?? DEFAULT_CLIENT_NAME,
      opportunityTitle: options.opportunityTitle,
    }),
  );
  for (const placeholder of leftoverPlaceholdersForSlide(options)) {
    slide.addText("\u00A0", { placeholder });
  }
}
