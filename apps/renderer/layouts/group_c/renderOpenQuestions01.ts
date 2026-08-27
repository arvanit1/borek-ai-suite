/** MS-19: deterministic OPEN_QUESTIONS_01 renderer — two-column questions. */

import type PptxGenJS from "pptxgenjs";

import type { OpenQuestions01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_c_open_questions_01.js";
import { addBulletList, type BulletListRect } from "../../design_system/components/addBulletList.js";
import type { ContentCardRect } from "../../design_system/components/addContentCard.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import { MASTER_CONTENT_NAME } from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekColors } from "../../design_system/tokens/colors.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { BorekTypography } from "../../design_system/tokens/typography.js";
import { addSubtitle, computeContentBand } from "./contentBand.js";

export interface QuestionColumnLayout {
  heading: ContentCardRect;
  list: BulletListRect;
}

export interface OpenQuestions01Layout {
  subtitle?: ContentCardRect;
  left: QuestionColumnLayout;
  right: QuestionColumnLayout;
}

/** Compute two equal columns from the shared content body band. */
export function computeOpenQuestions01Layout(hasSubtitle: boolean): OpenQuestions01Layout {
  const band = computeContentBand(hasSubtitle);
  const columnWidth = (band.contentWidth - BorekGrid.columnGap) / 2;
  const headingHeight = BorekSpacing.footerHeight;
  const listTop = band.bodyTop + headingHeight + BorekGrid.rowGap / 2;
  const listHeight = band.bodyBottom - listTop;
  const rightX = BorekSpacing.marginX + columnWidth + BorekGrid.columnGap;

  const column = (x: number): QuestionColumnLayout => ({
    heading: { x, y: band.bodyTop, w: columnWidth, h: headingHeight },
    list: { x, y: listTop, w: columnWidth, h: listHeight },
  });

  return {
    subtitle: band.subtitle,
    left: column(BorekSpacing.marginX),
    right: column(rightX),
  };
}

function addColumnHeading(slide: PptxGenJS.Slide, rect: ContentCardRect, heading: string): void {
  slide.addText(heading, {
    ...rect,
    color: BorekColors.text,
    fontFace: BorekTypography.fonts.heading,
    fontSize: BorekTypography.defaultSizes.body,
    bold: true,
    align: "left",
    valign: "top",
  });
}

/** Render one validated OPEN_QUESTIONS_01 SlideSpec using two addBulletList columns. */
export function renderOpenQuestions01(
  pptx: PptxGenJS,
  spec: Readonly<OpenQuestions01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const layout = computeOpenQuestions01Layout(Boolean(spec.subtitle));

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }

  addColumnHeading(slide, layout.left.heading, spec.left.heading);
  addBulletList(slide, layout.left.list, spec.left.items);
  addColumnHeading(slide, layout.right.heading, spec.right.heading);
  addBulletList(slide, layout.right.list, spec.right.items);

  return slide;
}
