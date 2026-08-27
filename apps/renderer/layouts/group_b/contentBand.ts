/** Shared content-band geometry for Group B MASTER_CONTENT layouts (JJ-15..JJ-18). */

import type PptxGenJS from "pptxgenjs";

import type { ContentCardRect } from "../../design_system/components/addContentCard.js";
import { computeMasterContentLayout } from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekSlide } from "../../design_system/tokens/branding.js";
import { BorekColors } from "../../design_system/tokens/colors.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { BorekTypography } from "../../design_system/tokens/typography.js";

export interface ContentBand {
  contentWidth: number;
  contentTopY: number;
  bodyTop: number;
  bodyBottom: number;
  subtitle?: ContentCardRect;
}

/** Title-band geometry from shared master/grid tokens; subtitle consumes one band only when present. */
export function computeContentBand(hasSubtitle: boolean): ContentBand {
  const master = computeMasterContentLayout();
  const contentWidth = BorekSlide.widthInches - BorekSpacing.marginX * 2;
  const subtitlePresence = Number(hasSubtitle);
  const subtitleHeight = BorekSpacing.footerHeight * subtitlePresence;
  const subtitleGap = BorekGrid.rowGap * subtitlePresence;

  return {
    contentWidth,
    contentTopY: master.contentTopY,
    bodyTop: master.contentTopY + subtitleHeight + subtitleGap,
    bodyBottom: master.branding.footer.y - BorekGrid.rowGap,
    subtitle: hasSubtitle
      ? {
          x: BorekSpacing.marginX,
          y: master.contentTopY,
          w: contentWidth,
          h: subtitleHeight,
        }
      : undefined,
  };
}

export function addSubtitle(slide: PptxGenJS.Slide, subtitle: string, rect: ContentCardRect): void {
  slide.addText(subtitle, {
    ...rect,
    color: BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "left",
    valign: "top",
  });
}
