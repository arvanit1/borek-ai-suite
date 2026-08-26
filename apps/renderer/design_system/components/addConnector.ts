/**
 * AT-30: Line/connector component between positioned elements (technical plan v2 §17.1).
 *
 * Structural connector for architecture diagrams (MS-16) and process flows (JJ-15).
 * Layout renderers must call this — never define their own connector styling.
 */

import type PptxGenJS from "pptxgenjs";

import { BorekBorders } from "../tokens/borders.js";
import { BorekColors, type BorekColorHex } from "../tokens/colors.js";

/** PptxGenJS shape name for straight connectors. */
export const CONNECTOR_SHAPE = "line" as const;

export interface ConnectorPoint {
  x: number;
  y: number;
}

export type AddConnectorOptions = {
  /** Must be a BorekColors token value — callers pass BorekColors.primary, not hex literals. */
  color?: BorekColorHex;
  /** Line width in points — defaults to BorekBorders.divider.lineWidthPt. */
  lineWidth?: number;
};

/** Build PptxGenJS line shape options from from/to anchor points. */
export function connectorShapeOptions(
  from: ConnectorPoint,
  to: ConnectorPoint,
  options: AddConnectorOptions = {},
) {
  const { divider } = BorekBorders;

  return {
    x: from.x,
    y: from.y,
    w: to.x - from.x,
    h: to.y - from.y,
    line: {
      color: options.color ?? BorekColors.border,
      width: options.lineWidth ?? divider.lineWidthPt,
    },
  };
}

/**
 * Render a straight connector between two slide coordinates.
 *
 * @example
 * addConnector(slide, { x: 2.0, y: 3.0 }, { x: 5.5, y: 3.0 });
 * addConnector(slide, from, to, { color: BorekColors.primary });
 */
export function addConnector(
  slide: PptxGenJS.Slide,
  from: ConnectorPoint,
  to: ConnectorPoint,
  options: AddConnectorOptions = {},
): void {
  slide.addShape(CONNECTOR_SHAPE, connectorShapeOptions(from, to, options));
}
