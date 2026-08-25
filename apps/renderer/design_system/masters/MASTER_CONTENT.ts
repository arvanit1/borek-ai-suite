/**
 * AT-17: Standard content slide master — section label + slide title header band (technical plan v2 §16.1).
 *
 * Light background, shared footer/logo/slide-number from branding tokens, and top header
 * regions for addSectionLabel/addSlideTitle (AT-19/AT-20). Layout-specific visuals render
 * below the title band inside layout functions (§17.2).
 */

import PptxGenJS from "pptxgenjs";

import { BorekBranding, BorekSlide, computeBrandingLayout } from "../tokens/branding.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekSpacing } from "../tokens/spacing.js";
import { BorekTypography } from "../tokens/typography.js";

/** Registered content master name — reused by the majority of layout renderers (§17.2). */
export const MASTER_CONTENT_NAME = "MASTER_CONTENT";

export const MASTER_CONTENT_LABEL_PLACEHOLDER = "sectionLabel";
export const MASTER_CONTENT_TITLE_PLACEHOLDER = "slideTitle";

/**
 * MVP layouts that use MASTER_CONTENT (layout_registry.json — all except cover and closing).
 * Keeps AT-17 "used by the majority of layouts" traceable without wiring renderers yet.
 */
export const MASTER_CONTENT_LAYOUT_IDS = [
  "EXECUTIVE_SUMMARY_01",
  "CONTEXT_01",
  "PROBLEM_SOLUTION_01",
  "SCOPE_01",
  "REQUIREMENTS_MATRIX_01",
  "PROCESS_FLOW_01",
  "TIMELINE_01",
  "MILESTONES_01",
  "TEAM_FTE_01",
  "ARCHITECTURE_01",
  "COMPLIANCE_01",
  "SUCCESS_METRICS_01",
  "OPEN_QUESTIONS_01",
] as const;

export type MasterContentLayoutId = (typeof MASTER_CONTENT_LAYOUT_IDS)[number];

export const MVP_LAYOUT_COUNT = 15;

export interface MasterContentRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface MasterContentLayout {
  sectionLabel: MasterContentRect;
  slideTitle: MasterContentRect;
  /** Y coordinate (inches) where layout renderers begin drawing slide-specific content. */
  contentTopY: number;
  branding: ReturnType<typeof computeBrandingLayout>;
}

/** Content header geometry derived from spacing, grid, slide, and branding tokens. */
export function computeMasterContentLayout(): MasterContentLayout {
  const branding = computeBrandingLayout();
  const { marginX, marginTop, footerHeight } = BorekSpacing;
  const { rowGap } = BorekGrid;
  const { widthInches } = BorekSlide;
  const contentWidth = widthInches - marginX * 2;

  const sectionLabelY = marginTop + BorekBranding.logo.height + rowGap;
  const sectionLabelH = footerHeight;
  const slideTitleY = sectionLabelY + sectionLabelH + rowGap;
  const slideTitleH = marginTop * 2;
  const contentTopY = slideTitleY + slideTitleH + rowGap;

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
    contentTopY,
    branding,
  };
}

/** Register MASTER_CONTENT on a PptxGenJS instance (LAYOUT_WIDE = §16 slide size). */
export function registerMasterContent(pptx: PptxGenJS): void {
  pptx.layout = "LAYOUT_WIDE";
  const layout = computeMasterContentLayout();
  const { footer } = BorekBranding;
  const { branding } = layout;

  pptx.defineSlideMaster({
    title: MASTER_CONTENT_NAME,
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
            name: MASTER_CONTENT_LABEL_PLACEHOLDER,
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
            name: MASTER_CONTENT_TITLE_PLACEHOLDER,
            type: "body",
            x: layout.slideTitle.x,
            y: layout.slideTitle.y,
            w: layout.slideTitle.w,
            h: layout.slideTitle.h,
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
