/**
 * AT-15: Cover slide master — title/subtitle/stat-badge regions (technical plan v2 §16.1).
 *
 * Dark cover field, cover content placeholders, plus shared footer/logo/slide-number
 * from branding tokens. No generic body content region.
 */

import PptxGenJS from "pptxgenjs";

import { BorekBranding, BorekSlide, computeBrandingLayout } from "../tokens/branding.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekSpacing } from "../tokens/spacing.js";
import { BorekTypography } from "../tokens/typography.js";

/** Registered cover master name — reused by renderCover01 (BT-17). */
export const MASTER_COVER_NAME = "MASTER_COVER";

export const MASTER_COVER_TITLE_PLACEHOLDER = "coverTitle";
export const MASTER_COVER_SUBTITLE_PLACEHOLDER = "coverSubtitle";
export const MASTER_COVER_SECTION_LABEL_PLACEHOLDER = "coverSectionLabel";
export const MASTER_COVER_STAT_BADGE_PLACEHOLDER_1 = "statBadge1";
export const MASTER_COVER_STAT_BADGE_PLACEHOLDER_2 = "statBadge2";
export const MASTER_COVER_STAT_BADGE_PLACEHOLDER_3 = "statBadge3";

export interface MasterCoverRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface MasterCoverLayout {
  sectionLabel: MasterCoverRect;
  title: MasterCoverRect;
  subtitle: MasterCoverRect;
  statBadges: [MasterCoverRect, MasterCoverRect, MasterCoverRect];
  branding: ReturnType<typeof computeBrandingLayout>;
}

/** Cover placeholder geometry derived from spacing, grid, slide, and branding tokens. */
export function computeMasterCoverLayout(): MasterCoverLayout {
  const branding = computeBrandingLayout();
  const { marginX, marginTop, footerHeight } = BorekSpacing;
  const { columnGap, rowGap } = BorekGrid;
  const { widthInches, heightInches } = BorekSlide;
  const contentWidth = widthInches - marginX * 2;
  const footerY = heightInches - footerHeight;

  const sectionLabelY = marginTop + BorekBranding.logo.height + rowGap;
  const sectionLabelH = footerHeight;
  const titleY = sectionLabelY + sectionLabelH + rowGap;
  const titleH = marginTop * 2;
  const subtitleY = titleY + titleH + rowGap;
  const subtitleH = footerHeight;

  const statBadgeH = footerHeight * 2;
  const statBadgeY = footerY - rowGap - statBadgeH;
  const statBadgeW = (contentWidth - columnGap * 2) / 3;

  const statBadge1X = marginX;
  const statBadge2X = marginX + statBadgeW + columnGap;
  const statBadge3X = marginX + (statBadgeW + columnGap) * 2;

  return {
    sectionLabel: {
      x: marginX,
      y: sectionLabelY,
      w: contentWidth,
      h: sectionLabelH,
    },
    title: {
      x: marginX,
      y: titleY,
      w: contentWidth,
      h: titleH,
    },
    subtitle: {
      x: marginX,
      y: subtitleY,
      w: contentWidth,
      h: subtitleH,
    },
    statBadges: [
      { x: statBadge1X, y: statBadgeY, w: statBadgeW, h: statBadgeH },
      { x: statBadge2X, y: statBadgeY, w: statBadgeW, h: statBadgeH },
      { x: statBadge3X, y: statBadgeY, w: statBadgeW, h: statBadgeH },
    ],
    branding,
  };
}

const coverTextStyle = {
  color: BorekColors.background,
} as const;

/** Register MASTER_COVER on a PptxGenJS instance (LAYOUT_WIDE = §16 slide size). */
export function registerMasterCover(pptx: PptxGenJS): void {
  pptx.layout = "LAYOUT_WIDE";
  const layout = computeMasterCoverLayout();
  const { footer } = BorekBranding;
  const { branding } = layout;

  pptx.defineSlideMaster({
    title: MASTER_COVER_NAME,
    background: { color: BorekColors.coverBackground },
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
            name: MASTER_COVER_SECTION_LABEL_PLACEHOLDER,
            type: "body",
            x: layout.sectionLabel.x,
            y: layout.sectionLabel.y,
            w: layout.sectionLabel.w,
            h: layout.sectionLabel.h,
            ...coverTextStyle,
            fontFace: BorekTypography.fonts.body,
            fontSize: BorekTypography.defaultSizes.body,
          },
        },
      },
      {
        placeholder: {
          options: {
            name: MASTER_COVER_TITLE_PLACEHOLDER,
            type: "title",
            x: layout.title.x,
            y: layout.title.y,
            w: layout.title.w,
            h: layout.title.h,
            ...coverTextStyle,
            fontFace: BorekTypography.fonts.heading,
            fontSize: BorekTypography.defaultSizes.heading,
          },
        },
      },
      {
        placeholder: {
          options: {
            name: MASTER_COVER_SUBTITLE_PLACEHOLDER,
            type: "body",
            x: layout.subtitle.x,
            y: layout.subtitle.y,
            w: layout.subtitle.w,
            h: layout.subtitle.h,
            ...coverTextStyle,
            fontFace: BorekTypography.fonts.body,
            fontSize: BorekTypography.defaultSizes.body,
          },
        },
      },
      {
        placeholder: {
          options: {
            name: MASTER_COVER_STAT_BADGE_PLACEHOLDER_1,
            type: "body",
            x: layout.statBadges[0].x,
            y: layout.statBadges[0].y,
            w: layout.statBadges[0].w,
            h: layout.statBadges[0].h,
            ...coverTextStyle,
            fontFace: BorekTypography.fonts.body,
            fontSize: BorekTypography.defaultSizes.body,
          },
        },
      },
      {
        placeholder: {
          options: {
            name: MASTER_COVER_STAT_BADGE_PLACEHOLDER_2,
            type: "body",
            x: layout.statBadges[1].x,
            y: layout.statBadges[1].y,
            w: layout.statBadges[1].w,
            h: layout.statBadges[1].h,
            ...coverTextStyle,
            fontFace: BorekTypography.fonts.body,
            fontSize: BorekTypography.defaultSizes.body,
          },
        },
      },
      {
        placeholder: {
          options: {
            name: MASTER_COVER_STAT_BADGE_PLACEHOLDER_3,
            type: "body",
            x: layout.statBadges[2].x,
            y: layout.statBadges[2].y,
            w: layout.statBadges[2].w,
            h: layout.statBadges[2].h,
            ...coverTextStyle,
            fontFace: BorekTypography.fonts.body,
            fontSize: BorekTypography.defaultSizes.body,
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
