/** Shared date/week parsers for TIMELINE_01 and MILESTONES_01 positioning (JJ-16, JJ-17). */

import { parseTimelineWeekLabel } from "../../design_system/components/addTimeline.js";

export interface TimelineDateSpan {
  start: number;
  end: number;
  kind: "week" | "day";
}

const WEEK_RANGE =
  /^week\s*(\d+(?:\.\d+)?)\s*(?:to|through|until|[–—-])\s*(?:week\s*)?(\d+(?:\.\d+)?)$/i;
const ISO_RANGE =
  /^(\d{4}-\d{2}(?:-\d{2})?)\s*(?:to|through|until|[–—])\s*(\d{4}-\d{2}(?:-\d{2})?)$/i;
const ISO_SINGLE = /^(\d{4}-\d{2}(?:-\d{2})?)$/;

function isoToDayNumber(value: string): number | null {
  const iso = value.length === 7 ? `${value}-01` : value;
  const millis = Date.parse(`${iso}T00:00:00Z`);
  if (!Number.isFinite(millis)) {
    return null;
  }
  return millis / 86_400_000;
}

/** Parse a milestone date label into a numeric span on a week or day scale. */
export function parseTimelineDateRange(label: string): TimelineDateSpan | null {
  const trimmed = label.trim();
  const weekRange = trimmed.match(WEEK_RANGE);
  if (weekRange) {
    const start = Number(weekRange[1]);
    const end = Number(weekRange[2]);
    if (Number.isFinite(start) && Number.isFinite(end) && end > start) {
      return { start, end, kind: "week" };
    }
    return null;
  }

  const week = parseTimelineWeekLabel(trimmed);
  if (week !== null) {
    return { start: week, end: week, kind: "week" };
  }

  const isoRange = trimmed.match(ISO_RANGE);
  if (isoRange) {
    const start = isoToDayNumber(isoRange[1]!);
    const end = isoToDayNumber(isoRange[2]!);
    if (start !== null && end !== null && end > start) {
      return { start, end, kind: "day" };
    }
    return null;
  }

  const isoSingle = trimmed.match(ISO_SINGLE);
  if (isoSingle) {
    const value = isoToDayNumber(isoSingle[1]!);
    if (value !== null) {
      return { start: value, end: value, kind: "day" };
    }
  }

  return null;
}
