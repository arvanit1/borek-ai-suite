/** MS-16: deterministic ARCHITECTURE_01 renderer — numbered nodes + connectors. */

import type PptxGenJS from "pptxgenjs";

import type { Architecture01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_c_architecture_01.js";
import {
  addArchitectureNode,
  architectureNodeBadgeSize,
  type ArchitectureNodeRect,
} from "../../design_system/components/addArchitectureNode.js";
import { addConnector } from "../../design_system/components/addConnector.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import {
  computeMasterContentLayout,
  MASTER_CONTENT_NAME,
} from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekSlide } from "../../design_system/tokens/branding.js";
import { BorekColors } from "../../design_system/tokens/colors.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { BorekTypography } from "../../design_system/tokens/typography.js";

export interface Architecture01Layout {
  subtitle?: ArchitectureNodeRect;
  rows: readonly (readonly ArchitectureNodeRect[])[];
  nodes: readonly ArchitectureNodeRect[];
}

/** Split 2–8 nodes into one row (≤3) or two balanced rows (4–8). Invoice 4-node is 2×2. */
export function architectureRowSizes(count: number): readonly number[] {
  if (count <= 0) {
    return [];
  }
  if (count <= 3) {
    return [count];
  }
  const first = Math.ceil(count / 2);
  return [first, count - first];
}

function nodesInRow(
  count: number,
  y: number,
  height: number,
  gridX: number,
  gridWidth: number,
): ArchitectureNodeRect[] {
  const gap = BorekGrid.columnGap;
  const cardWidth = (gridWidth - gap * (count - 1)) / count;
  return Array.from({ length: count }, (_, index) => ({
    x: gridX + index * (cardWidth + gap),
    y,
    w: cardWidth,
    h: height,
  }));
}

/** Compute numbered node rectangles from shared master/grid tokens. */
export function computeArchitecture01Layout(
  hasSubtitle: boolean,
  nodeCount: number,
): Architecture01Layout {
  const master = computeMasterContentLayout();
  const contentWidth = BorekSlide.widthInches - BorekSpacing.marginX * 2;
  const subtitlePresence = Number(hasSubtitle);
  const subtitleHeight = BorekSpacing.footerHeight * subtitlePresence;
  const subtitleGap = BorekGrid.rowGap * subtitlePresence;
  const bodyTop = master.contentTopY + subtitleHeight + subtitleGap;
  const bodyBottom = master.branding.footer.y - BorekGrid.rowGap;
  const badgeHalf = architectureNodeBadgeSize() / 2;
  const gridX = BorekSpacing.marginX + badgeHalf;
  const gridWidth = contentWidth - badgeHalf;
  const gridTop = bodyTop + badgeHalf;
  const rowSizes = architectureRowSizes(nodeCount);
  const rowCount = Math.max(rowSizes.length, 1);
  const availableHeight = bodyBottom - gridTop;
  const cardHeight = (availableHeight - BorekGrid.rowGap * (rowCount - 1)) / rowCount;

  const rows = rowSizes.map((size, rowIndex) =>
    nodesInRow(
      size,
      gridTop + rowIndex * (cardHeight + BorekGrid.rowGap),
      cardHeight,
      gridX,
      gridWidth,
    ),
  );

  return {
    subtitle: hasSubtitle
      ? {
          x: BorekSpacing.marginX,
          y: master.contentTopY,
          w: contentWidth,
          h: subtitleHeight,
        }
      : undefined,
    rows,
    nodes: rows.flat(),
  };
}

function addSubtitle(slide: PptxGenJS.Slide, subtitle: string, rect: ArchitectureNodeRect): void {
  slide.addText(subtitle, {
    ...rect,
    color: BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "left",
    valign: "top",
  });
}

function addRowConnectors(slide: PptxGenJS.Slide, row: readonly ArchitectureNodeRect[]): void {
  for (let index = 0; index < row.length - 1; index += 1) {
    const from = row[index]!;
    const to = row[index + 1]!;
    addConnector(
      slide,
      { x: from.x + from.w, y: from.y + from.h / 2 },
      { x: to.x, y: to.y + to.h / 2 },
    );
  }
}

function addColumnConnectors(
  slide: PptxGenJS.Slide,
  topRow: readonly ArchitectureNodeRect[],
  bottomRow: readonly ArchitectureNodeRect[],
): void {
  const shared = Math.min(topRow.length, bottomRow.length);
  for (let index = 0; index < shared; index += 1) {
    const from = topRow[index]!;
    const to = bottomRow[index]!;
    addConnector(
      slide,
      { x: from.x + from.w / 2, y: from.y + from.h },
      { x: to.x + to.w / 2, y: to.y },
    );
  }
}

/** Render one validated ARCHITECTURE_01 SlideSpec using shared architecture primitives. */
export function renderArchitecture01(
  pptx: PptxGenJS,
  spec: Readonly<Architecture01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const components = [...spec.components].sort((left, right) => left.number - right.number);
  const layout = computeArchitecture01Layout(Boolean(spec.subtitle), components.length);

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }

  layout.rows.forEach((row) => {
    addRowConnectors(slide, row);
  });
  if (layout.rows.length === 2) {
    addColumnConnectors(slide, layout.rows[0]!, layout.rows[1]!);
  }

  components.forEach((component, index) => {
    const node = layout.nodes[index];
    if (!node) {
      return;
    }
    addArchitectureNode(slide, node, {
      number: component.number,
      title: component.title,
      description: component.description,
    });
  });

  return slide;
}
