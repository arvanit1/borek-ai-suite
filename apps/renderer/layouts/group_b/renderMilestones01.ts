/** JJ-17: deterministic MILESTONES_01 renderer — standalone milestone-track layout. */

import type PptxGenJS from "pptxgenjs";

import type { Milestones01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_b_milestones_01.js";
import { addConnector } from "../../design_system/components/addConnector.js";
import {
  addContentCard,
  type ContentCardRect,
} from "../../design_system/components/addContentCard.js";
import {
  addMilestone,
  milestoneBandGap,
  milestoneLabelBandHeight,
  milestoneMarkerDiameter,
  type MilestoneAnchor,
  type MilestoneContent,
} from "../../design_system/components/addMilestone.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import { MASTER_CONTENT_NAME } from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { parseTimelineWeekLabel } from "../../design_system/components/addTimeline.js";
import { addSubtitle, computeContentBand, type ContentBand } from "./contentBand.js";
import { parseTimelineDateRange } from "./timelineDates.js";

export const MILESTONES_01_TRACK_CLEARANCE =
  milestoneMarkerDiameter() / 2 + milestoneBandGap() + milestoneLabelBandHeight() * 2;

export interface Milestones01Layout {
  subtitle?: ContentBand["subtitle"];
  trackFrom: MilestoneAnchor;
  trackTo: MilestoneAnchor;
  anchors: readonly MilestoneAnchor[];
  descriptions: readonly ContentCardRect[];
}

function milestoneContent(
  item: Milestones01SlideSpec["milestones"][number],
): MilestoneContent {
  return {
    label: item.name,
    date: item.date,
  };
}

function datePositions(dates: readonly (string | undefined)[]): number[] | null {
  const parsed = dates.map((date) => {
    if (!date) {
      return null;
    }
    const range = parseTimelineDateRange(date);
    if (range) {
      return range.end;
    }
    return parseTimelineWeekLabel(date);
  });
  if (parsed.some((value) => value === null)) {
    return null;
  }
  return parsed as number[];
}

function descriptionCards(
  count: number,
  y: number,
  height: number,
  contentWidth: number,
): ContentCardRect[] {
  if (count <= 0 || height <= 0) {
    return [];
  }
  const gap = BorekGrid.columnGap;
  const cardWidth = (contentWidth - gap * (count - 1)) / count;
  return Array.from({ length: count }, (_, index) => ({
    x: BorekSpacing.marginX + index * (cardWidth + gap),
    y,
    w: cardWidth,
    h: height,
  }));
}

/** Compute a horizontal milestone track with date-based or equal-spaced markers. */
export function computeMilestones01Layout(
  hasSubtitle: boolean,
  milestoneCount: number,
  dates: readonly (string | undefined)[] = [],
): Milestones01Layout {
  const band = computeContentBand(hasSubtitle);
  const inset = milestoneMarkerDiameter();
  const trackY = band.bodyTop + milestoneMarkerDiameter();
  const trackFrom = { x: BorekSpacing.marginX + inset, y: trackY };
  const trackTo = {
    x: BorekSpacing.marginX + band.contentWidth - inset,
    y: trackY,
  };
  const trackWidth = trackTo.x - trackFrom.x;
  const positions = dates.length === milestoneCount ? datePositions(dates) : null;
  const scaleEnd = positions && positions.length > 0 ? Math.max(...positions, 1) : 1;

  const anchors = Array.from({ length: milestoneCount }, (_, index) => {
    let t: number;
    if (milestoneCount === 1) {
      t = 0.5;
    } else if (positions) {
      t = positions[index]! / scaleEnd;
    } else {
      t = index / (milestoneCount - 1);
    }
    return {
      x: trackFrom.x + t * trackWidth,
      y: trackY,
    };
  });

  const cardsTop = trackY + MILESTONES_01_TRACK_CLEARANCE + BorekGrid.rowGap;
  const descriptions = descriptionCards(
    milestoneCount,
    cardsTop,
    Math.max(band.bodyBottom - cardsTop, BorekSpacing.footerHeight),
    band.contentWidth,
  );

  return {
    subtitle: band.subtitle,
    trackFrom,
    trackTo,
    anchors,
    descriptions,
  };
}

/** Render one validated MILESTONES_01 SlideSpec as a standalone milestone track. */
export function renderMilestones01(
  pptx: PptxGenJS,
  spec: Readonly<Milestones01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const dates = spec.milestones.map((item) => item.date);
  const layout = computeMilestones01Layout(
    Boolean(spec.subtitle),
    spec.milestones.length,
    dates,
  );

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }

  addConnector(slide, layout.trackFrom, layout.trackTo);

  spec.milestones.forEach((milestone, index) => {
    const anchor = layout.anchors[index];
    if (anchor) {
      addMilestone(slide, anchor, milestoneContent(milestone));
    }
    const description = layout.descriptions[index];
    if (description) {
      addContentCard(slide, description, {
        title: milestone.name,
        description: milestone.description,
      });
    }
  });

  return slide;
}
