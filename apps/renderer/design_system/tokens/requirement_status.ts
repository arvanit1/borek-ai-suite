/**
 * Requirement status token resolver (BT-8 / BT-21 — REQUIREMENTS_MATRIX_01).
 *
 * SlideSpec carries semantic status strings only; renderers map them here.
 */

import {
  BorekRequirementStatusColors,
  type RequirementStatus,
  REQUIREMENT_STATUSES,
} from "./colors.js";

export { REQUIREMENT_STATUSES, type RequirementStatus };

/** Resolve fill/text/border colors for a requirement status pill. */
export function resolveRequirementStatusColors(status: RequirementStatus) {
  return BorekRequirementStatusColors[status];
}

/** Human-readable pill label for deck output. */
export function formatRequirementStatusLabel(status: RequirementStatus): string {
  switch (status) {
    case "included":
      return "Included";
    case "partial":
      return "Partial";
    case "later":
      return "Later";
  }
}

/** Narrow arbitrary strings — returns undefined when not a registered status. */
export function parseRequirementStatus(value: string): RequirementStatus | undefined {
  return (REQUIREMENT_STATUSES as readonly string[]).includes(value)
    ? (value as RequirementStatus)
    : undefined;
}
