/**
 * AT-16: Section-divider slide master — eyebrow label + section title (technical plan v2 §16.1).
 *
 * Light background, minimal section-break placeholders, plus shared footer/logo/slide-number
 * from branding tokens. No body content, subtitle, or stat badges.
 */

import PptxGenJS from "pptxgenjs";

import { BorekBranding, BorekSlide, computeBrandingLayout } from "../tokens/branding.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekSpacing } from "../tokens/spacing.js";
import { BorekTypography } from "../tokens/typography.js";

/** Registered section-divider master name — reused by section-break layouts (AT-33). */
export const MASTER_SECTION_NAME = "MASTER_SECTION";

export const MASTER_SECTION_LABEL_PLACEHOLDER = "sectionLabel";
export const MASTER_SECTION_TITLE_PLACEHOLDER = "sectionTitle";

export interface MasterSectionRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface MasterSectionLayout {
  sectionLabel: MasterSectionRect;
  sectionTitle: MasterSectionRect;
  branding: ReturnType<typeof computeBrandingLayout>;
}

/** Section placeholder geometry derived from spacing, grid, slide, and branding tokens. */
export function computeMasterSectionLayout(): MasterSectionLayout {
  const branding = computeBrandingLayout();
  const { marginX, marginTop, footerHeight } = BorekSpacing;
  const { rowGap } = BorekGrid;
  const { widthInches, heightInches } = BorekSlide;
  const contentWidth = widthInches - marginX * 2;

  const contentTop = marginTop + BorekBranding.logo.height + rowGap;
  const contentBottom = heightInches - footerHeight - rowGap;

  const sectionLabelH = footerHeight;
  const labelTitleGap = marginTop;
  const sectionTitleH = marginTop * 3;
  const blockH = sectionLabelH + labelTitleGap + sectionTitleH;
  const blockY = contentTop + (contentBottom - contentTop - blockH) / 2;

  const sectionLabelY = blockY;
  const sectionTitleY = sectionLabelY + sectionLabelH + labelTitleGap;

  return {
    sectionLabel: {
      x: marginX,
      y: sectionLabelY,
      w: contentWidth,
      h: sectionLabelH,
    },
    sectionTitle: {
      x: marginX,
      y: sectionTitleY,
      w: contentWidth,
      h: sectionTitleH,
    },
    branding,
  };
}

/** Register MASTER_SECTION on a PptxGenJS instance (LAYOUT_WIDE = §16 slide size). */
export function registerMasterSection(pptx: PptxGenJS): void {
  pptx.layout = "LAYOUT_WIDE";
  const layout = computeMasterSectionLayout();
  const { footer } = BorekBranding;
  const { branding } = layout;

  pptx.defineSlideMaster({
    title: MASTER_SECTION_NAME,
    background: { color: BorekColors.background },
    slideNumber: {
      x: branding.slideNumber.x,
      y: branding.slideNumber.y,
      w: branding.slideNumber.w,
      h: branding.slideNumber.h,
      color: branding.slideNumber.color,
      fontFace: branding.slideNumber.fontFace,
      fontSize: branding.slideNumber.fontSize,
      align: branding.slideNumber.align,
    },
    objects: [
      {
        placeholder: {
          options: {
            name: BorekBranding.logo.placeholderName,
            type: "pic",
            x: branding.logo.x,
            y: branding.logo.y,
            w: branding.logo.w,
            h: branding.logo.h,
          },
        },
      },
      {
        placeholder: {
          options: {
            name: MASTER_SECTION_LABEL_PLACEHOLDER,
            type: "body",
            x: layout.sectionLabel.x,
            y: layout.sectionLabel.y,
            w: layout.sectionLabel.w,
            h: layout.sectionLabel.h,
            color: BorekColors.primary,
            fontFace: BorekTypography.fonts.body,
            fontSize: BorekTypography.defaultSizes.body,
            align: "left",
            valign: "top",
          },
        },
      },
      {
        placeholder: {
          options: {
            name: MASTER_SECTION_TITLE_PLACEHOLDER,
            type: "body",
            x: layout.sectionTitle.x,
            y: layout.sectionTitle.y,
            w: layout.sectionTitle.w,
            h: layout.sectionTitle.h,
            color: BorekColors.text,
            fontFace: BorekTypography.fonts.heading,
            fontSize: BorekTypography.defaultSizes.heading,
            align: "left",
            valign: "top",
          },
        },
      },
      {
        placeholder: {
          options: {
            name: BorekBranding.footer.placeholderName,
            type: "body",
            x: branding.footer.x,
            y: branding.footer.y,
            w: branding.footer.w,
            h: branding.footer.h,
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
