/** MS-20: deterministic NEXT_STEPS_01 renderer — checklist + numbered steps. */

import type PptxGenJS from "pptxgenjs";

import type { NextSteps01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_c_next_steps_01.js";
import { addBulletList, type BulletListRect } from "../../design_system/components/addBulletList.js";
import type { ContentCardRect } from "../../design_system/components/addContentCard.js";
import {
  addNumberBadge,
  numberBadgeDiameter,
} from "../../design_system/components/addNumberBadge.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import { MASTER_CLOSING_NAME } from "../../design_system/masters/MASTER_CLOSING.js";
import { MASTER_CONTENT_NAME } from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekColors } from "../../design_system/tokens/colors.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { BorekTypography } from "../../design_system/tokens/typography.js";
import { addSubtitle, computeContentBand } from "./contentBand.js";

export interface NextStepRowLayout {
  badge: ContentCardRect;
  text: ContentCardRect;
}

export interface NextSteps01Layout {
  subtitle?: ContentCardRect;
  checklist: BulletListRect;
  steps: ContentCardRect;
  stepRows: readonly NextStepRowLayout[];
}

/** Two equal columns from the shared content/closing body band. */
export function computeNextSteps01Layout(
  hasSubtitle: boolean,
  dark: boolean,
  stepCount: number,
): NextSteps01Layout {
  const band = computeContentBand(hasSubtitle, dark);
  const columnWidth = (band.contentWidth - BorekGrid.columnGap) / 2;
  const bodyHeight = band.bodyBottom - band.bodyTop;
  const checklist: BulletListRect = {
    x: BorekSpacing.marginX,
    y: band.bodyTop,
    w: columnWidth,
    h: bodyHeight,
  };
  const steps: ContentCardRect = {
    x: BorekSpacing.marginX + columnWidth + BorekGrid.columnGap,
    y: band.bodyTop,
    w: columnWidth,
    h: bodyHeight,
  };

  return {
    subtitle: band.subtitle,
    checklist,
    steps,
    stepRows: computeStepRows(steps, stepCount),
  };
}

function computeStepRows(column: ContentCardRect, stepCount: number): NextStepRowLayout[] {
  if (stepCount <= 0) {
    return [];
  }
  const badge = numberBadgeDiameter();
  const rowGap = BorekGrid.rowGap;
  const rowHeight = (column.h - rowGap * (stepCount - 1)) / stepCount;
  const textGap = BorekGrid.columnGap / 2;

  return Array.from({ length: stepCount }, (_, index) => {
    const y = column.y + index * (rowHeight + rowGap);
    return {
      badge: { x: column.x, y, w: badge, h: badge },
      text: {
        x: column.x + badge + textGap,
        y,
        w: column.w - badge - textGap,
        h: rowHeight,
      },
    };
  });
}

/** Render one validated NEXT_STEPS_01 SlideSpec using closing/content primitives. */
export function renderNextSteps01(
  pptx: PptxGenJS,
  spec: Readonly<NextSteps01SlideSpec>,
): PptxGenJS.Slide {
  const dark = spec.darkBackground;
  const slide = pptx.addSlide({
    masterName: dark ? MASTER_CLOSING_NAME : MASTER_CONTENT_NAME,
  });
  const steps = [...spec.steps].sort((left, right) => left.number - right.number);
  const layout = computeNextSteps01Layout(Boolean(spec.subtitle), dark, steps.length);

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title, dark ? { variant: "dark" } : undefined);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle, dark ? "dark" : "light");
  }

  addBulletList(slide, layout.checklist, spec.checklist, dark ? { variant: "dark" } : undefined);

  steps.forEach((step, index) => {
    const row = layout.stepRows[index];
    if (!row) {
      return;
    }
    addNumberBadge(slide, row.badge, step.number);
    slide.addText(step.text, {
      ...row.text,
      color: dark ? BorekColors.background : BorekColors.text,
      fontFace: BorekTypography.fonts.body,
      fontSize: BorekTypography.defaultSizes.body,
      align: "left",
      valign: "middle",
    });
  });

  return slide;
}
