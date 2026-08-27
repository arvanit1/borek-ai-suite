/** JJ-15: deterministic PROCESS_FLOW_01 renderer — numbered phase-card layout. */

import type PptxGenJS from "pptxgenjs";

import type { ProcessFlow01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_b_process_flow_01.js";
import { addConnector } from "../../design_system/components/addConnector.js";
import {
  addProcessStep,
  type ProcessStepRect,
} from "../../design_system/components/addProcessStep.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import { MASTER_CONTENT_NAME } from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { addSubtitle, computeContentBand, type ContentBand } from "./contentBand.js";

export interface ProcessFlow01Layout {
  subtitle?: ContentBand["subtitle"];
  rows: readonly (readonly ProcessStepRect[])[];
  cards: readonly ProcessStepRect[];
}

/** Split 1–8 phases into one row (≤4) or two balanced rows (5–8). */
export function processFlowRowSizes(count: number): readonly number[] {
  if (count <= 0) {
    return [];
  }
  if (count <= 4) {
    return [count];
  }
  const first = Math.ceil(count / 2);
  return [first, count - first];
}

function cardsInRow(
  count: number,
  y: number,
  height: number,
  contentWidth: number,
): ProcessStepRect[] {
  const gap = BorekGrid.columnGap;
  const cardWidth = (contentWidth - gap * (count - 1)) / count;
  return Array.from({ length: count }, (_, index) => ({
    x: BorekSpacing.marginX + index * (cardWidth + gap),
    y,
    w: cardWidth,
    h: height,
  }));
}

/** Compute numbered phase-card rectangles from shared master/grid tokens. */
export function computeProcessFlow01Layout(
  hasSubtitle: boolean,
  phaseCount: number,
): ProcessFlow01Layout {
  const band = computeContentBand(hasSubtitle);
  const rowSizes = processFlowRowSizes(phaseCount);
  const rowGap = BorekGrid.rowGap;
  const rowCount = Math.max(rowSizes.length, 1);
  const availableHeight = band.bodyBottom - band.bodyTop;
  const cardHeight = (availableHeight - rowGap * (rowCount - 1)) / rowCount;

  const rows = rowSizes.map((size, rowIndex) =>
    cardsInRow(
      size,
      band.bodyTop + rowIndex * (cardHeight + rowGap),
      cardHeight,
      band.contentWidth,
    ),
  );

  return {
    subtitle: band.subtitle,
    rows,
    cards: rows.flat(),
  };
}

/** Render one validated PROCESS_FLOW_01 SlideSpec using numbered process-step primitives. */
export function renderProcessFlow01(
  pptx: PptxGenJS,
  spec: Readonly<ProcessFlow01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const phases = [...spec.phases].sort((left, right) => left.number - right.number);
  const layout = computeProcessFlow01Layout(Boolean(spec.subtitle), phases.length);

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }

  layout.rows.forEach((row) => {
    for (let index = 0; index < row.length - 1; index += 1) {
      const from = row[index]!;
      const to = row[index + 1]!;
      addConnector(
        slide,
        { x: from.x + from.w, y: from.y + from.h / 2 },
        { x: to.x, y: to.y + to.h / 2 },
      );
    }
  });

  phases.forEach((phase, index) => {
    const card = layout.cards[index];
    if (!card) {
      return;
    }
    addProcessStep(slide, card, {
      number: phase.number,
      title: phase.name,
      description: phase.description,
    });
  });

  return slide;
}
