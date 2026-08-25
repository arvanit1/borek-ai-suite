/**
 * AT-18: Closing slide master — dark-background variant (technical plan v2 §16.1).
 *
 * Dark closing field, section label + slide title header, checklist and numbered-steps
 * content regions (MS-20 / NEXT_STEPS_01), plus shared footer/logo/slide-number from
 * branding tokens.
 */

import PptxGenJS from "pptxgenjs";

import { BorekBranding, BorekSlide, computeBrandingLayout } from "../tokens/branding.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekSpacing } from "../tokens/spacing.js";
import { BorekTypography } from "../tokens/typography.js";

/** Registered closing master name — reused by renderNextSteps01 (MS-20). */
export const MASTER_CLOSING_NAME = "MASTER_CLOSING";

export const MASTER_CLOSING_LABEL_PLACEHOLDER = "sectionLabel";
export const MASTER_CLOSING_TITLE_PLACEHOLDER = "slideTitle";
export const MASTER_CLOSING_CHECKLIST_PLACEHOLDER = "closingChecklist";
export const MASTER_CLOSING_STEPS_PLACEHOLDER = "closingSteps";

/** MVP closing layout(s) from layout_registry.json (category: closing). */
export const MASTER_CLOSING_LAYOUT_IDS = ["NEXT_STEPS_01"] as const;

export type MasterClosingLayoutId = (typeof MASTER_CLOSING_LAYOUT_IDS)[number];

export interface MasterClosingRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface MasterClosingLayout {
  sectionLabel: MasterClosingRect;
  slideTitle: MasterClosingRect;
  checklist: MasterClosingRect;
  steps: MasterClosingRect;
  /** Y coordinate (inches) where layout renderers begin drawing slide-specific content. */
  contentTopY: number;
  branding: ReturnType<typeof computeBrandingLayout>;
}

/** Closing placeholder geometry derived from spacing, grid, slide, and branding tokens. */
export function computeMasterClosingLayout(): MasterClosingLayout {
  const branding = computeBrandingLayout();
  const { marginX, marginTop, footerHeight } = BorekSpacing;
  const { columnGap, rowGap } = BorekGrid;
  const { widthInches, heightInches } = BorekSlide;
  const contentWidth = widthInches - marginX * 2;

  const sectionLabelY = marginTop + BorekBranding.logo.height + rowGap;
  const sectionLabelH = footerHeight;
  const slideTitleY = sectionLabelY + sectionLabelH + rowGap;
  const slideTitleH = marginTop * 2;
  const contentTopY = slideTitleY + slideTitleH + rowGap;
  const contentBottom = heightInches - footerHeight - rowGap;
  const contentAreaH = contentBottom - contentTopY;
  const columnW = (contentWidth - columnGap) / 2;

  return {
    sectionLabel: {
      x: marginX,
      y: sectionLabelY,
      w: contentWidth,
      h: sectionLabelH,
    },
    slideTitle: {
      x: marginX,
      y: slideTitleY,
      w: contentWidth,
      h: slideTitleH,
    },
    checklist: {
      x: marginX,
      y: contentTopY,
      w: columnW,
      h: contentAreaH,
    },
    steps: {
      x: marginX + columnW + columnGap,
      y: contentTopY,
      w: columnW,
      h: contentAreaH,
    },
    contentTopY,
    branding,
  };
}

const closingTextStyle = {
  color: BorekColors.background,
} as const;

/** Register MASTER_CLOSING on a PptxGenJS instance (LAYOUT_WIDE = §16 slide size). */
export function registerMasterClosing(pptx: PptxGenJS): void {
  pptx.layout = "LAYOUT_WIDE";
  const layout = computeMasterClosingLayout();
  const { footer } = BorekBranding;
  const { branding } = layout;

  pptx.defineSlideMaster({
    title: MASTER_CLOSING_NAME,
    background: { color: BorekColors.coverBackground },
    slideNumber: {
      x: branding.slideNumber.x,
      y: branding.slideNumber.y,
      w: branding.slideNumber.w,
      h: branding.slideNumber.h,
      color: closingTextStyle.color,
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
            name: MASTER_CLOSING_LABEL_PLACEHOLDER,
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
            name: MASTER_CLOSING_TITLE_PLACEHOLDER,
            type: "body",
            x: layout.slideTitle.x,
            y: layout.slideTitle.y,
            w: layout.slideTitle.w,
            h: layout.slideTitle.h,
            ...closingTextStyle,
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
            name: MASTER_CLOSING_CHECKLIST_PLACEHOLDER,
            type: "body",
            x: layout.checklist.x,
            y: layout.checklist.y,
            w: layout.checklist.w,
            h: layout.checklist.h,
            ...closingTextStyle,
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
            name: MASTER_CLOSING_STEPS_PLACEHOLDER,
            type: "body",
            x: layout.steps.x,
            y: layout.steps.y,
            w: layout.steps.w,
            h: layout.steps.h,
            ...closingTextStyle,
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
