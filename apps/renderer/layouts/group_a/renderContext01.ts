/** BT-18: deterministic CONTEXT_01 renderer. */

import type PptxGenJS from "pptxgenjs";

import type { Context01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_a_context_01.js";
import {
  addContentCard,
  type ContentCardRect,
} from "../../design_system/components/addContentCard.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import {
  computeMasterContentLayout,
  MASTER_CONTENT_NAME,
} from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekSlide } from "../../design_system/tokens/branding.js";
import { BorekColors } from "../../design_system/tokens/colors.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { BorekTypography } from "../../design_system/tokens/typography.js";

export interface Context01Layout {
  subtitle?: ContentCardRect;
  problem: ContentCardRect;
  solution: ContentCardRect;
  currentState: ContentCardRect;
  targetState: ContentCardRect;
}

/**
 * Compute the four-card composition from the shared content master and grid tokens.
 * The subtitle consumes one token-sized band only when populated.
 */
export function computeContext01Layout(hasSubtitle: boolean): Context01Layout {
  const master = computeMasterContentLayout();
  const contentWidth = BorekSlide.widthInches - BorekSpacing.marginX * 2;
  const subtitlePresence = Number(hasSubtitle);
  const subtitleHeight = BorekSpacing.footerHeight * subtitlePresence;
  const subtitleGap = BorekGrid.rowGap * subtitlePresence;
  const cardsTop = master.contentTopY + subtitleHeight + subtitleGap;
  const cardsBottom = master.branding.footer.y - BorekGrid.rowGap;
  const cardsHeight = cardsBottom - cardsTop;
  const cardWidth = (contentWidth - BorekGrid.columnGap) / 2;
  const cardHeight = (cardsHeight - BorekGrid.rowGap) / 2;
  const rightX = BorekSpacing.marginX + cardWidth + BorekGrid.columnGap;
  const bottomY = cardsTop + cardHeight + BorekGrid.rowGap;

  return {
    subtitle: hasSubtitle
      ? {
          x: BorekSpacing.marginX,
          y: master.contentTopY,
          w: contentWidth,
          h: subtitleHeight,
        }
      : undefined,
    problem: { x: BorekSpacing.marginX, y: cardsTop, w: cardWidth, h: cardHeight },
    solution: { x: rightX, y: cardsTop, w: cardWidth, h: cardHeight },
    currentState: { x: BorekSpacing.marginX, y: bottomY, w: cardWidth, h: cardHeight },
    targetState: { x: rightX, y: bottomY, w: cardWidth, h: cardHeight },
  };
}

function addSubtitle(slide: PptxGenJS.Slide, subtitle: string, rect: ContentCardRect): void {
  slide.addText(subtitle, {
    ...rect,
    color: BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "left",
    valign: "top",
  });
}

/** Render one validated CONTEXT_01 SlideSpec using only shared presentation primitives. */
export function renderContext01(
  pptx: PptxGenJS,
  spec: Readonly<Context01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const layout = computeContext01Layout(Boolean(spec.subtitle));

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }

  addContentCard(slide, layout.problem, spec.problem);
  addContentCard(slide, layout.solution, spec.solution);
  addContentCard(slide, layout.currentState, spec.currentState);
  addContentCard(slide, layout.targetState, spec.targetState);

  return slide;
}
