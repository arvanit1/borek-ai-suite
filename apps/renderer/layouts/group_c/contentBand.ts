/** Shared content-band geometry for Group C MASTER_CONTENT / MASTER_CLOSING layouts. */

import type PptxGenJS from "pptxgenjs";

import type { ContentCardRect } from "../../design_system/components/addContentCard.js";
import {
  computeMasterClosingLayout,
  MASTER_CLOSING_NAME,
} from "../../design_system/masters/MASTER_CLOSING.js";
import {
  computeMasterContentLayout,
  MASTER_CONTENT_NAME,
} from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekSlide } from "../../design_system/tokens/branding.js";
import { BorekColors } from "../../design_system/tokens/colors.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { BorekTypography } from "../../design_system/tokens/typography.js";

export interface ContentBand {
  masterName: typeof MASTER_CONTENT_NAME | typeof MASTER_CLOSING_NAME;
  contentWidth: number;
  contentTopY: number;
  bodyTop: number;
  bodyBottom: number;
  subtitle?: ContentCardRect;
}

export type ContentBandVariant = "light" | "dark";

/** Title-band geometry from the chosen master; subtitle consumes one band only when present. */
export function computeContentBand(hasSubtitle: boolean, dark = false): ContentBand {
  const master = dark ? computeMasterClosingLayout() : computeMasterContentLayout();
  const contentWidth = BorekSlide.widthInches - BorekSpacing.marginX * 2;
  const subtitlePresence = Number(hasSubtitle);
  const subtitleHeight = BorekSpacing.footerHeight * subtitlePresence;
  const subtitleGap = BorekGrid.rowGap * subtitlePresence;

  return {
    masterName: dark ? MASTER_CLOSING_NAME : MASTER_CONTENT_NAME,
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

export function addSubtitle(
  slide: PptxGenJS.Slide,
  subtitle: string,
  rect: ContentCardRect,
  variant: ContentBandVariant = "light",
): void {
  slide.addText(subtitle, {
    ...rect,
    color: variant === "dark" ? BorekColors.background : BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "left",
    valign: "top",
  });
}
