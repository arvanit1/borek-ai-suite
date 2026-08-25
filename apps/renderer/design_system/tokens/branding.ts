/**
 * Borek branding tokens (technical plan v2 §16 — design-system/branding.ts).
 *
 * Slide dimensions, logo/footer/page-number placement, and default footer styling.
 * Masters and components import from here — never inline placement or branding literals.
 *
 * Position values are in inches (PptxGenJS positioning convention).
 */

import { BorekColors } from "./colors.js";
import { BorekSpacing } from "./spacing.js";
import { BorekTypography } from "./typography.js";

/** Technical plan v2 §16 — BorekTheme.slide dimensions (inches). */
export const BorekSlide = {
  widthInches: 13.333,
  heightInches: 7.5,
} as const;

export type BorekSlideDimension = keyof typeof BorekSlide;

export type BorekSlideInches = (typeof BorekSlide)[BorekSlideDimension];

const footerY = BorekSlide.heightInches - BorekSpacing.footerHeight;
const contentWidth = BorekSlide.widthInches - BorekSpacing.marginX * 2;

export const BorekBranding = {
  logo: {
    placeholderName: "logo",
    x: BorekSpacing.marginX,
    y: BorekSpacing.marginTop,
    width: BorekSpacing.marginX * 2,
    height: BorekSpacing.footerHeight,
  },
  footer: {
    placeholderName: "footer",
    x: BorekSpacing.marginX,
    y: footerY,
    width: contentWidth - BorekSpacing.marginX,
    height: BorekSpacing.footerHeight,
    color: BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    valign: "middle",
  },
  slideNumber: {
    x: BorekSlide.widthInches - BorekSpacing.marginX * 2,
    y: footerY,
    width: BorekSpacing.marginX,
    height: BorekSpacing.footerHeight,
    color: BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "right",
    format: "number",
  },
} as const;

export type BorekBrandingRegion = keyof typeof BorekBranding;

export interface BrandingRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface BrandingLayout {
  logo: BrandingRect;
  footer: BrandingRect;
  slideNumber: BrandingRect & {
    color: string;
    fontFace: string;
    fontSize: number;
    align: "right";
    format: "number";
  };
}

/** Map branding tokens to PptxGenJS master layout rectangles. */
export function computeBrandingLayout(): BrandingLayout {
  const { logo, footer, slideNumber } = BorekBranding;

  return {
    logo: {
      x: logo.x,
      y: logo.y,
      w: logo.width,
      h: logo.height,
    },
    footer: {
      x: footer.x,
      y: footer.y,
      w: footer.width,
      h: footer.height,
    },
    slideNumber: {
      x: slideNumber.x,
      y: slideNumber.y,
      w: slideNumber.width,
      h: slideNumber.height,
      color: slideNumber.color,
      fontFace: slideNumber.fontFace,
      fontSize: slideNumber.fontSize,
      align: slideNumber.align,
      format: slideNumber.format,
    },
  };
}

export const BorekBrandingTokens = {
  slide: BorekSlide,
  branding: BorekBranding,
} as const;

/** All branding tokens as a plain record (for tests and future theme wiring). */
export const BOREK_BRANDING_TOKENS = BorekBrandingTokens;
