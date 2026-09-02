/** JJ-23: deterministic EXECUTIVE_SUMMARY_01 renderer — headline band plus highlight cards. */

import type PptxGenJS from "pptxgenjs";

import type { ExecutiveSummary01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_summary_executive_summary_01.js";
import {
  addContentCard,
  type ContentCardRect,
} from "../../design_system/components/addContentCard.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import { MASTER_CONTENT_NAME } from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekColors } from "../../design_system/tokens/colors.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { BorekTypography } from "../../design_system/tokens/typography.js";
import { addSubtitle, computeContentBand, type ContentBand } from "../group_b/contentBand.js";

export interface ExecutiveSummary01Layout {
  subtitle?: ContentBand["subtitle"];
  headline: ContentCardRect;
  highlights: readonly ContentCardRect[];
}

/** Compute the lead headline band and a single row of highlight cards. */
export function computeExecutiveSummary01Layout(
  hasSubtitle: boolean,
  highlightCount: number,
): ExecutiveSummary01Layout {
  const band = computeContentBand(hasSubtitle);
  const count = Math.max(highlightCount, 1);
  const headlineHeight = BorekSpacing.footerHeight * 2;
  const headline: ContentCardRect = {
    x: BorekSpacing.marginX,
    y: band.bodyTop,
    w: band.contentWidth,
    h: headlineHeight,
  };
  const cardsTop = headline.y + headline.h + BorekGrid.rowGap;
  const cardsHeight = Math.max(band.bodyBottom - cardsTop, BorekSpacing.footerHeight * 3);
  const cardWidth = (band.contentWidth - BorekGrid.columnGap * (count - 1)) / count;
  const highlights = Array.from({ length: count }, (_, index) => ({
    x: BorekSpacing.marginX + index * (cardWidth + BorekGrid.columnGap),
    y: cardsTop,
    w: cardWidth,
    h: cardsHeight,
  }));

  return {
    subtitle: band.subtitle,
    headline,
    highlights,
  };
}

function addHeadline(slide: PptxGenJS.Slide, headline: string, rect: ContentCardRect): void {
  slide.addText(headline, {
    ...rect,
    color: BorekColors.text,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    bold: true,
    align: "left",
    valign: "middle",
  });
}

/** Render one validated EXECUTIVE_SUMMARY_01 SlideSpec using shared presentation primitives. */
export function renderExecutiveSummary01(
  pptx: PptxGenJS,
  spec: Readonly<ExecutiveSummary01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const layout = computeExecutiveSummary01Layout(Boolean(spec.subtitle), spec.highlights.length);

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }
  addHeadline(slide, spec.headline, layout.headline);
  spec.highlights.forEach((highlight, index) => {
    const rect = layout.highlights[index];
    if (rect) {
      addContentCard(slide, rect, highlight);
    }
  });

  return slide;
}
