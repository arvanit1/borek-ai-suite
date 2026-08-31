/**
 * AT-32: Milestone marker component (technical plan v2 §17.1).
 *
 * Point-in-time marker with label (and optional date) for TIMELINE_01 lower band (JJ-16)
 * and MILESTONES_01 (JJ-17). Distinct from addTimeline phase segments (AT-28).
 * Layout renderers must call this — never define their own milestone styling.
 */

import type PptxGenJS from "pptxgenjs";

import { BorekColors } from "../tokens/colors.js";
import { BorekGrid } from "../tokens/grid.js";
import { BorekSpacing } from "../tokens/spacing.js";
import { BorekTypography } from "../tokens/typography.js";

/** PptxGenJS shape name for milestone point markers. */
export const MILESTONE_MARKER_SHAPE = "diamond" as const;

export interface MilestoneAnchor {
  x: number;
  y: number;
}

/** Semantic milestone — label required; optional date for timeline alignment. */
export interface MilestoneContent {
  label: string;
  date?: string;
}

export interface MilestoneTextRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface MilestoneLayout {
  marker: MilestoneTextRect;
  label: MilestoneTextRect;
  date?: MilestoneTextRect;
}

/** Marker diameter — derived from grid row gap (AT-13): rowGap × 2. */
export function milestoneMarkerDiameter(): number {
  return BorekGrid.rowGap * 2;
}

/** Label band width — wide enough for two wrapped words without stacking neighbors. */
export function milestoneLabelWidth(): number {
  return milestoneMarkerDiameter() * 6;
}

/** Label band height — from spacing token (AT-13). */
export function milestoneLabelBandHeight(): number {
  return BorekSpacing.footerHeight;
}

/** Gap between marker and label text — from grid row gap. */
export function milestoneBandGap(): number {
  return BorekGrid.rowGap;
}

/** Compute marker and text regions; position is the marker center anchor. */
export function computeMilestoneLayout(
  position: MilestoneAnchor,
  milestone: MilestoneContent,
): MilestoneLayout {
  const diameter = milestoneMarkerDiameter();
  const half = diameter / 2;
  const labelW = milestoneLabelWidth();
  const labelH = milestoneLabelBandHeight();
  const gap = milestoneBandGap();

  const marker: MilestoneTextRect = {
    x: position.x - half,
    y: position.y - half,
    w: diameter,
    h: diameter,
  };

  const label: MilestoneTextRect = {
    x: position.x - labelW / 2,
    y: position.y + half + gap,
    w: labelW,
    h: labelH,
  };

  if (!milestone.date) {
    return { marker, label };
  }

  return {
    marker,
    label,
    date: {
      x: label.x,
      y: label.y + labelH + gap,
      w: labelW,
      h: labelH,
    },
  };
}

/** Diamond marker styling — primary fill from color tokens (AT-11). */
export function milestoneMarkerShapeOptions(marker: MilestoneTextRect) {
  return {
    x: marker.x,
    y: marker.y,
    w: marker.w,
    h: marker.h,
    fill: { color: BorekColors.primary },
    line: {
      color: BorekColors.primary,
      width: 0,
    },
  };
}

export function milestoneLabelTextOptions(label: MilestoneTextRect) {
  return {
    x: label.x,
    y: label.y,
    w: label.w,
    h: label.h,
    color: BorekColors.text,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "center" as const,
    valign: "top" as const,
    wrap: true,
    shrinkText: true,
  };
}

export function milestoneDateTextOptions(date: MilestoneTextRect) {
  return {
    x: date.x,
    y: date.y,
    w: date.w,
    h: date.h,
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
 * Render a milestone point marker at the given anchor (marker center).
 *
 * @example
 * addMilestone(slide, { x: 4.5, y: 5.0 }, { label: "Pilot go-live", date: "Week 10" });
 */
export function addMilestone(
  slide: PptxGenJS.Slide,
  position: MilestoneAnchor,
  milestone: MilestoneContent,
): void {
  const layout = computeMilestoneLayout(position, milestone);

  slide.addShape(MILESTONE_MARKER_SHAPE, milestoneMarkerShapeOptions(layout.marker));
  slide.addText(milestone.label, milestoneLabelTextOptions(layout.label));

  if (milestone.date && layout.date) {
    slide.addText(milestone.date, milestoneDateTextOptions(layout.date));
  }
}
