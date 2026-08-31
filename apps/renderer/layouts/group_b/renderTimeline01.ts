/** JJ-16: deterministic TIMELINE_01 renderer — two-band timeline + milestone layout. */

import type PptxGenJS from "pptxgenjs";

import type { Timeline01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_b_timeline_01.js";
import {
  addMilestone,
  milestoneLabelBandHeight,
  milestoneLabelWidth,
  milestoneMarkerDiameter,
  type MilestoneAnchor,
  type MilestoneContent,
} from "../../design_system/components/addMilestone.js";
import {
  addTimeline,
  buildTimelinePhasesFromSlideSpec,
  computeTimelineLayout,
  timelineBandGap,
  timelineDateBandHeight,
  timelineDescriptionBandHeight,
  timelineTrackHeight,
  type TimelinePhaseItem,
  type TimelineRect,
} from "../../design_system/components/addTimeline.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import { MASTER_CONTENT_NAME } from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { addSubtitle, computeContentBand, type ContentBand } from "./contentBand.js";
import { parseTimelineDateRange } from "./timelineDates.js";

export { parseTimelineDateRange } from "./timelineDates.js";

export interface Timeline01Layout {
  subtitle?: ContentBand["subtitle"];
  timeline: TimelineRect;
  milestoneTrackY: number;
  milestoneAnchors: readonly MilestoneAnchor[];
}

function milestoneForPhase(
  phaseId: string,
  milestones: Timeline01SlideSpec["milestones"],
): Timeline01SlideSpec["milestones"][number] | undefined {
  return milestones.find((milestone) => milestone.phaseId === phaseId);
}

/**
 * Map TIMELINE_01 phases onto a shared scale.
 * Independent start/end ranges (including overlaps) win; otherwise week-end ticks or equal spans.
 */
export function buildTimeline01PhaseItems(
  phases: Timeline01SlideSpec["phases"],
  milestones: Timeline01SlideSpec["milestones"],
): TimelinePhaseItem[] {
  if (phases.length === 0) {
    return [];
  }

  const dated = phases.map((phase) => {
    const milestone = milestoneForPhase(phase.id, milestones);
    const dateLabel = milestone?.date;
    return {
      phase,
      dateLabel,
      span: dateLabel ? parseTimelineDateRange(dateLabel) : null,
    };
  });

  const independentRanges = dated.every(
    (entry) => entry.span !== null && entry.span.end > entry.span.start,
  );
  if (independentRanges) {
    return dated.map((entry) => ({
      name: entry.phase.name,
      description: entry.phase.description,
      dateLabel: entry.dateLabel,
      positionStart: entry.span!.start,
      positionEnd: entry.span!.end,
    }));
  }

  return buildTimelinePhasesFromSlideSpec(phases, milestones);
}

function timelineBandHeight(): number {
  return (
    timelineDateBandHeight() +
    timelineBandGap() +
    timelineTrackHeight() +
    timelineBandGap() +
    timelineDescriptionBandHeight()
  );
}

function milestoneBandHeight(): number {
  return milestoneMarkerDiameter() / 2 + timelineBandGap() + milestoneLabelBandHeight() * 2;
}

/** Compute upper timeline band and lower milestone anchors from date/week positioning. */
export function computeTimeline01Layout(
  hasSubtitle: boolean,
  phaseItems: readonly TimelinePhaseItem[],
  milestoneCount: number,
): Timeline01Layout {
  const band = computeContentBand(hasSubtitle);
  const upperHeight = timelineBandHeight();
  const lowerHeight = milestoneBandHeight();
  const timeline: TimelineRect = {
    x: BorekSpacing.marginX,
    y: band.bodyTop,
    w: band.contentWidth,
    h: upperHeight,
  };
  const timelineLayout = computeTimelineLayout(timeline, phaseItems);
  const milestoneTrackY = Math.min(
    timeline.y + upperHeight + timelineBandGap() + milestoneMarkerDiameter() / 2,
    band.bodyBottom - lowerHeight,
  );

  const milestoneAnchors = phaseItems.slice(0, milestoneCount).map((_, index) => {
    const phaseLayout = timelineLayout.phases[index];
    const x = phaseLayout
      ? phaseLayout.segment.x + phaseLayout.segment.w / 2
      : timeline.x + ((index + 0.5) / Math.max(phaseItems.length, 1)) * timeline.w;
    return { x, y: milestoneTrackY };
  });

  return {
    subtitle: band.subtitle,
    timeline,
    milestoneTrackY,
    milestoneAnchors,
  };
}

function milestoneContent(
  specMilestone: Timeline01SlideSpec["milestones"][number],
): MilestoneContent {
  return {
    label: specMilestone.name,
    date: specMilestone.date,
  };
}

/** Render one validated TIMELINE_01 SlideSpec as a two-band roadmap. */
export function renderTimeline01(
  pptx: PptxGenJS,
  spec: Readonly<Timeline01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const phaseItems = buildTimeline01PhaseItems(spec.phases, spec.milestones);
  const layout = computeTimeline01Layout(
    Boolean(spec.subtitle),
    phaseItems,
    spec.milestones.length,
  );

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }

  addTimeline(slide, layout.timeline, { phases: phaseItems });

  const timelineLayout = computeTimelineLayout(layout.timeline, phaseItems);
  const milestonesByPhase = new Map<string, Timeline01SlideSpec["milestones"]>();
  for (const milestone of spec.milestones) {
    const group = milestonesByPhase.get(milestone.phaseId) ?? [];
    group.push(milestone);
    milestonesByPhase.set(milestone.phaseId, group);
  }

  spec.milestones.forEach((milestone) => {
    const phaseIndex = spec.phases.findIndex((phase) => phase.id === milestone.phaseId);
    const siblings = milestonesByPhase.get(milestone.phaseId) ?? [milestone];
    const siblingIndex = siblings.indexOf(milestone);
    const segment = phaseIndex >= 0 ? timelineLayout.phases[phaseIndex]?.segment : undefined;
    const fallback =
      (phaseIndex >= 0 ? layout.milestoneAnchors[phaseIndex] : undefined) ??
      layout.milestoneAnchors[0];
    if (!fallback) {
      return;
    }
    const slotCount = Math.max(siblings.length, 1);
    const x = segment
      ? segment.x + ((siblingIndex + 0.5) / slotCount) * segment.w
      : fallback.x + (siblingIndex - (slotCount - 1) / 2) * (milestoneLabelWidth() / 2);
    addMilestone(slide, { x, y: layout.milestoneTrackY }, milestoneContent(milestone));
  });

  return slide;
}
