/** JJ-18: deterministic TEAM_FTE_01 renderer — role cards + bottom summary stat row. */

import type PptxGenJS from "pptxgenjs";

import type { TeamFte01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_b_team_fte_01.js";
import {
  addContentCard,
  type ContentCardRect,
} from "../../design_system/components/addContentCard.js";
import { addKpiCard, type KpiCardRect } from "../../design_system/components/addKpiCard.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import { MASTER_CONTENT_NAME } from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { addSubtitle, computeContentBand, type ContentBand } from "./contentBand.js";

export interface TeamFte01Layout {
  subtitle?: ContentBand["subtitle"];
  roles: readonly ContentCardRect[];
  summary: readonly KpiCardRect[];
}

/** Pack 1–6 role cards into one or two rows (max 3 columns). */
export function teamFteRowSizes(count: number): readonly number[] {
  if (count <= 0) {
    return [];
  }
  if (count <= 3) {
    return [count];
  }
  if (count === 4) {
    return [2, 2];
  }
  return [3, count - 3];
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

function summaryRowHeight(): number {
  return BorekSpacing.footerHeight * 3;
}

/** Compute role-card grid and bottom summary KPI row from shared master/grid tokens. */
export function computeTeamFte01Layout(
  hasSubtitle: boolean,
  roleCount: number,
  summaryCount: number,
): TeamFte01Layout {
  const band = computeContentBand(hasSubtitle);
  const rowGap = BorekGrid.rowGap;
  const summaryHeight = summaryRowHeight();
  const summaryTop = band.bodyBottom - summaryHeight;
  const rolesBottom = summaryTop - rowGap;
  const rowSizes = teamFteRowSizes(roleCount);
  const rowCount = Math.max(rowSizes.length, 1);
  const roleHeight = (rolesBottom - band.bodyTop - rowGap * (rowCount - 1)) / rowCount;

  const roleRows = rowSizes.map((size, rowIndex) =>
    cardsInRow(
      size,
      band.bodyTop + rowIndex * (roleHeight + rowGap),
      roleHeight,
      band.contentWidth,
    ),
  );

  const summary =
    summaryCount <= 0
      ? []
      : cardsInRow(summaryCount, summaryTop, summaryHeight, band.contentWidth);

  return {
    subtitle: band.subtitle,
    roles: roleRows.flat(),
    summary,
  };
}

/** Render one validated TEAM_FTE_01 SlideSpec using content cards and KPI stats. */
export function renderTeamFte01(
  pptx: PptxGenJS,
  spec: Readonly<TeamFte01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const layout = computeTeamFte01Layout(
    Boolean(spec.subtitle),
    spec.roles.length,
    spec.summary.length,
  );

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }

  spec.roles.forEach((role, index) => {
    const rect = layout.roles[index];
    if (!rect) {
      return;
    }
    addContentCard(slide, rect, {
      title: role.role,
      description: `${role.fte} FTE. ${role.responsibility}`,
    });
  });

  spec.summary.forEach((stat, index) => {
    const rect = layout.summary[index];
    if (!rect) {
      return;
    }
    addKpiCard(slide, rect, {
      value: stat.value,
      label: stat.label,
    });
  });

  return slide;
}
