/**
 * AT-14: Base SlideMaster with logo, footer, and page-number placeholders (technical plan v2 §16).
 *
 * Placement and styling come from branding.ts — no inline layout math in this module.
 */

import PptxGenJS from "pptxgenjs";

import { BorekBranding, computeBrandingLayout } from "../tokens/branding.js";
import { BorekColors } from "../tokens/colors.js";

/** Registered master name — reused by AT-15..18 and layout renderers. */
export const MASTER_DEFAULT_NAME = "MASTER_DEFAULT";

/** Re-export branding placeholder names for master consumers (AT-21 addFooter, logo injection). */
export const MASTER_DEFAULT_LOGO_PLACEHOLDER = BorekBranding.logo.placeholderName;
export const MASTER_DEFAULT_FOOTER_PLACEHOLDER = BorekBranding.footer.placeholderName;

/** Register MASTER_DEFAULT on a PptxGenJS instance (LAYOUT_WIDE = §16 slide size). */
export function registerMasterDefault(pptx: PptxGenJS): void {
  pptx.layout = "LAYOUT_WIDE";
  const layout = computeBrandingLayout();
  const { footer } = BorekBranding;

  pptx.defineSlideMaster({
    title: MASTER_DEFAULT_NAME,
    background: { color: BorekColors.background },
    slideNumber: {
      x: layout.slideNumber.x,
      y: layout.slideNumber.y,
      w: layout.slideNumber.w,
      h: layout.slideNumber.h,
      color: layout.slideNumber.color,
      fontFace: layout.slideNumber.fontFace,
      fontSize: layout.slideNumber.fontSize,
      align: layout.slideNumber.align,
    },
    objects: [
      {
        placeholder: {
          options: {
            name: BorekBranding.logo.placeholderName,
            type: "pic",
            x: layout.logo.x,
            y: layout.logo.y,
            w: layout.logo.w,
            h: layout.logo.h,
          },
        },
      },
      {
        placeholder: {
          options: {
            name: BorekBranding.footer.placeholderName,
            type: "body",
            x: layout.footer.x,
            y: layout.footer.y,
            w: layout.footer.w,
            h: layout.footer.h,
            color: footer.color,
            fontFace: footer.fontFace,
            fontSize: footer.fontSize,
            valign: footer.valign,
          },
        },
      },
    ],
  });
}
