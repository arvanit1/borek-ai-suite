/** Token-derived card grid for Group C 1–6 item layouts (compliance, success metrics). */

import type { ContentCardRect } from "../../design_system/components/addContentCard.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { computeContentBand, type ContentBand } from "./contentBand.js";

export interface CardGridLayout {
  subtitle?: ContentBand["subtitle"];
  rows: readonly (readonly ContentCardRect[])[];
  cards: readonly ContentCardRect[];
}

/** Split 1–6 cards into one row (≤3) or two balanced rows (4–6). */
export function cardRowSizes(count: number): readonly number[] {
  if (count <= 0) {
    return [];
  }
  if (count <= 3) {
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
): ContentCardRect[] {
  const gap = BorekGrid.columnGap;
  const cardWidth = (contentWidth - gap * (count - 1)) / count;
  return Array.from({ length: count }, (_, index) => ({
    x: BorekSpacing.marginX + index * (cardWidth + gap),
    y,
    w: cardWidth,
    h: height,
  }));
}

/** Compute a 1–6 card grid from the shared content/closing body band. */
export function computeCardGridLayout(
  hasSubtitle: boolean,
  count: number,
  dark = false,
): CardGridLayout {
  const band = computeContentBand(hasSubtitle, dark);
  const rowSizes = cardRowSizes(count);
  const rowCount = Math.max(rowSizes.length, 1);
  const availableHeight = band.bodyBottom - band.bodyTop;
  const cardHeight = (availableHeight - BorekGrid.rowGap * (rowCount - 1)) / rowCount;

  const rows = rowSizes.map((size, rowIndex) =>
    cardsInRow(
      size,
      band.bodyTop + rowIndex * (cardHeight + BorekGrid.rowGap),
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
