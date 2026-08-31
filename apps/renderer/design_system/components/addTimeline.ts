/**
 * AT-28: Timeline bar component (technical plan v2 §17.1).
 *
 * Horizontal phase bar with configurable segment count and date/week-based positioning.
 * Segment widths are proportional to positionStart/positionEnd on a shared timeline scale.
 * Milestone markers are rendered separately by addMilestone (AT-32).
 */

import type PptxGenJS from "pptxgenjs";

import { BorekBorders } from "../tokens/borders.js";
import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekSpacing } from "../tokens/spacing.js";
import { BorekTypography } from "../tokens/typography.js";

export const TIMELINE_PHASE_SHAPE = "roundRect" as const;
export const TIMELINE_TRACK_SHAPE = "line" as const;

export interface TimelineRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Resolved start/end on a shared timeline scale (e.g. weeks). */
export interface TimelinePhasePosition {
  start: number;
  end: number;
}

/** Single upper-band phase segment — aligns with TIMELINE_01 phases + milestone dates. */
export interface TimelinePhaseItem {
  name: string;
  description?: string;
  /** Display label at the phase end tick, e.g. "Week 2". */
  dateLabel?: string;
  /** Inclusive start on the shared timeline scale. */
  positionStart?: number;
  /** Inclusive end on the shared timeline scale (typically the milestone week). */
  positionEnd?: number;
}

export interface TimelineContent {
  phases: readonly TimelinePhaseItem[];
}

/** Minimal TIMELINE_01 phase shape for buildTimelinePhasesFromSlideSpec(). */
export interface SlideSpecTimelinePhase {
  id: string;
  name: string;
  description: string;
}

/** Minimal TIMELINE_01 milestone shape for buildTimelinePhasesFromSlideSpec(). */
export interface SlideSpecTimelineMilestone {
  phaseId: string;
  date?: string;
}

export interface TimelineTextRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface TimelinePhaseLayout {
  segment: TimelineTextRect;
  dateLabel: TimelineTextRect;
  name: TimelineTextRect;
  description: TimelineTextRect;
}

export interface TimelineLayout {
  trackY: number;
  track: TimelineTextRect;
  scaleEnd: number;
  phases: TimelinePhaseLayout[];
}

/** Gap between adjacent phase segments — from grid token (AT-13). */
export function timelinePhaseGap(): number {
  return BorekGrid.columnGap;
}

/** Height of the primary phase bar track. */
export function timelineTrackHeight(): number {
  return BorekSpacing.footerHeight;
}

/** Band above the track for date/week labels. */
export function timelineDateBandHeight(): number {
  return BorekSpacing.footerHeight;
}

/** Band below the track for phase descriptions. */
export function timelineDescriptionBandHeight(): number {
  return BorekSpacing.footerHeight * 2;
}

/** Vertical gap between label bands and the track. */
export function timelineBandGap(): number {
  return BorekGrid.rowGap;
}

/** Parse relative week labels such as "Week 2" into a numeric week index. */
export function parseTimelineWeekLabel(label: string): number | null {
  const match = label.trim().match(/^week\s*(\d+(?:\.\d+)?)$/i);
  if (!match?.[1]) {
    return null;
  }

  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

/** Resolve proportional positions; falls back to equal-width segments when unspecified. */
export function resolveTimelinePhasePositions(
  phases: readonly TimelinePhaseItem[],
): TimelinePhasePosition[] {
  if (phases.length === 0) {
    return [];
  }

  const explicit = phases.every(
    (phase) => phase.positionStart !== undefined && phase.positionEnd !== undefined,
  );

  if (explicit) {
    return phases.map((phase) => {
      const start = phase.positionStart!;
      const end = phase.positionEnd!;
      if (end <= start) {
        throw new Error(
          `Timeline phase "${phase.name}" has invalid range: start ${start} must be less than end ${end}`,
        );
      }

      return { start, end };
    });
  }

  return phases.map((_, index) => ({
    start: index,
    end: index + 1,
  }));
}

/** Upper bound of the timeline scale — max phase end across all segments. */
export function computeTimelineScaleEnd(positions: readonly TimelinePhasePosition[]): number {
  if (positions.length === 0) {
    return 1;
  }

  return Math.max(...positions.map((position) => position.end));
}

/** True when any two phase ranges occupy overlapping intervals on the shared scale. */
export function timelinePhasesOverlap(positions: readonly TimelinePhasePosition[]): boolean {
  for (let left = 0; left < positions.length; left += 1) {
    for (let right = left + 1; right < positions.length; right += 1) {
      const first = positions[left]!;
      const second = positions[right]!;
      if (first.start < second.end && first.end > second.start) {
        return true;
      }
    }
  }
  return false;
}

/**
 * Map TIMELINE_01 SlideSpec phases + milestones into positioned timeline items.
 * Uses milestone week labels (e.g. "Week 6") for segment end ticks; falls back to equal spans.
 */
export function buildTimelinePhasesFromSlideSpec(
  phases: readonly SlideSpecTimelinePhase[],
  milestones: readonly SlideSpecTimelineMilestone[],
): TimelinePhaseItem[] {
  if (phases.length === 0) {
    return [];
  }

  const milestoneDates = phases.map((phase) => {
    const milestone = milestones.find((entry) => entry.phaseId === phase.id);
    return milestone?.date ?? null;
  });

  const parsedEnds = milestoneDates.map((date) => (date ? parseTimelineWeekLabel(date) : null));
  const allWeeksParsed = parsedEnds.every((value) => value !== null);

  if (allWeeksParsed) {
    let cursor = 0;

    return phases.map((phase, index) => {
      const end = parsedEnds[index]!;
      const item: TimelinePhaseItem = {
        name: phase.name,
        description: phase.description,
        dateLabel: milestoneDates[index] ?? undefined,
        positionStart: cursor,
        positionEnd: end,
      };
      cursor = end;
      return item;
    });
  }

  return phases.map((phase, index) => ({
    name: phase.name,
    description: phase.description,
    dateLabel: milestoneDates[index] ?? undefined,
    positionStart: index,
    positionEnd: index + 1,
  }));
}

function timelineDateLabelWidth(segmentWidth: number): number {
  return Math.min(segmentWidth, timelineDateBandHeight() * 2);
}

/** Compute segment and label regions using date/week-proportional positioning. */
export function computeTimelineLayout(
  rect: TimelineRect,
  phases: readonly TimelinePhaseItem[],
): TimelineLayout {
  if (phases.length === 0) {
    return {
      trackY: rect.y,
      track: { x: rect.x, y: rect.y, w: rect.w, h: 0 },
      scaleEnd: 1,
      phases: [],
    };
  }

  const positions = resolveTimelinePhasePositions(phases);
  const scaleEnd = computeTimelineScaleEnd(positions);
  const overlapping = timelinePhasesOverlap(positions);
  const gap = overlapping ? 0 : timelinePhaseGap();
  const dateH = timelineDateBandHeight();
  const trackH = timelineTrackHeight();
  const bandGap = timelineBandGap();
  const usableW = overlapping ? rect.w : rect.w - gap * (phases.length - 1);
  const trackY = rect.y + dateH + bandGap;

  const phaseLayouts: TimelinePhaseLayout[] = positions.map((position, index) => {
    const segmentW = ((position.end - position.start) / scaleEnd) * usableW;
    const segmentX = rect.x + (position.start / scaleEnd) * usableW + index * gap;
    const dateLabelW = timelineDateLabelWidth(segmentW);

    return {
      segment: {
        x: segmentX,
        y: trackY,
        w: segmentW,
        h: trackH,
      },
      dateLabel: {
        x: segmentX + segmentW - dateLabelW / 2,
        y: rect.y,
        w: dateLabelW,
        h: dateH,
      },
      name: {
        x: segmentX,
        y: trackY,
        w: segmentW,
        h: trackH,
      },
      description: {
        x: segmentX,
        y: trackY + trackH + bandGap,
        w: segmentW,
        h: timelineDescriptionBandHeight(),
      },
    };
  });

  return {
    trackY,
    track: {
      x: rect.x,
      y: trackY + trackH / 2,
      w: rect.w,
      h: 0,
    },
    scaleEnd,
    phases: phaseLayouts,
  };
}

/** Baseline connector line behind phase segments. */
export function timelineTrackLineOptions(track: TimelineTextRect) {
  const { divider } = BorekBorders;

  return {
    x: track.x,
    y: track.y,
    w: track.w,
    h: track.h,
    line: {
      color: divider.color,
      width: divider.lineWidthPt,
    },
  };
}

/** Phase segment block styling. */
export function timelinePhaseShapeOptions(segment: TimelineTextRect) {
  const { card } = BorekBorders;

  return {
    x: segment.x,
    y: segment.y,
    w: segment.w,
    h: segment.h,
    fill: { color: BorekColors.primary },
    line: {
      color: BorekColors.primary,
      width: card.lineWidthPt,
    },
    rectRadius: card.borderRadiusInches,
  };
}

export function timelineDateLabelTextOptions(labelRect: TimelineTextRect) {
  return {
    x: labelRect.x,
    y: labelRect.y,
    w: labelRect.w,
    h: labelRect.h,
    color: BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "center" as const,
    valign: "bottom" as const,
    wrap: true,
    shrinkText: true,
  };
}

export function timelinePhaseNameTextOptions(nameRect: TimelineTextRect) {
  return {
    x: nameRect.x,
    y: nameRect.y,
    w: nameRect.w,
    h: nameRect.h,
    color: BorekColors.background,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    bold: true,
    align: "center" as const,
    valign: "middle" as const,
    wrap: true,
    shrinkText: true,
  };
}

export function timelinePhaseDescriptionTextOptions(descriptionRect: TimelineTextRect) {
  return {
    x: descriptionRect.x,
    y: descriptionRect.y,
    w: descriptionRect.w,
    h: descriptionRect.h,
    color: BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "center" as const,
    valign: "top" as const,
    wrap: true,
    shrinkText: true,
  };
}

/**
 * Render the upper-band timeline bar for the given phases.
 *
 * @example
 * addTimeline(slide, { x: 1, y: 2.2, w: 10, h: 1.6 }, {
 *   phases: buildTimelinePhasesFromSlideSpec(spec.phases, spec.milestones),
 * });
 */
export function addTimeline(
  slide: PptxGenJS.Slide,
  rect: TimelineRect,
  content: TimelineContent,
): void {
  if (content.phases.length === 0) {
    return;
  }

  const layout = computeTimelineLayout(rect, content.phases);

  slide.addShape(TIMELINE_TRACK_SHAPE, timelineTrackLineOptions(layout.track));

  content.phases.forEach((phase, index) => {
    const phaseLayout = layout.phases[index];
    if (!phaseLayout) {
      return;
    }

    slide.addShape(TIMELINE_PHASE_SHAPE, timelinePhaseShapeOptions(phaseLayout.segment));
    slide.addText(phase.name, timelinePhaseNameTextOptions(phaseLayout.name));

    if (phase.dateLabel) {
      slide.addText(phase.dateLabel, timelineDateLabelTextOptions(phaseLayout.dateLabel));
    }

    if (phase.description) {
      slide.addText(phase.description, timelinePhaseDescriptionTextOptions(phaseLayout.description));
    }
  });
}
