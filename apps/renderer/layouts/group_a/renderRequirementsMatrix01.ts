/** BT-21: deterministic REQUIREMENTS_MATRIX_01 renderer. */

import type PptxGenJS from "pptxgenjs";

import type { RequirementsMatrix01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_a_requirements_matrix_01.js";
import { CONTENT_CARD_SHAPE, type ContentCardRect } from "../../design_system/components/addContentCard.js";
import { addDataTable, type DataTableRect } from "../../design_system/components/addDataTable.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import {
  computeMasterContentLayout,
  MASTER_CONTENT_NAME,
} from "../../design_system/masters/MASTER_CONTENT.js";
import { BorekBorders } from "../../design_system/tokens/borders.js";
import { BorekSlide } from "../../design_system/tokens/branding.js";
import { BorekColors } from "../../design_system/tokens/colors.js";
import { BorekGrid } from "../../design_system/tokens/grid.js";
import {
  formatRequirementStatusLabel,
  parseRequirementStatus,
  resolveRequirementStatusColors,
  type RequirementStatus,
} from "../../design_system/tokens/requirement_status.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { BorekTypography } from "../../design_system/tokens/typography.js";

export interface RequirementsMatrix01Layout {
  subtitle?: ContentCardRect;
  tables: readonly DataTableRect[];
  statusPills: readonly ContentCardRect[];
}

/** Compute table and status-pill regions from the shared content master and grid tokens. */
export function computeRequirementsMatrix01Layout(
  hasSubtitle: boolean,
  requirementCount: number,
): RequirementsMatrix01Layout {
  const master = computeMasterContentLayout();
  const contentWidth = BorekSlide.widthInches - BorekSpacing.marginX * 2;
  const subtitlePresence = Number(hasSubtitle);
  const subtitleHeight = BorekSpacing.footerHeight * subtitlePresence;
  const subtitleGap = BorekGrid.rowGap * subtitlePresence;
  const tableTop = master.contentTopY + subtitleHeight + subtitleGap;
  const tableBottom = master.branding.footer.y - BorekGrid.rowGap;
  const tableCount = requirementCount > 3 ? 2 : 1;
  const tableWidth = (contentWidth - BorekGrid.columnGap * (tableCount - 1)) / tableCount;
  const firstTableRequirementCount = Math.ceil(requirementCount / tableCount);
  const requirementsPerTable = tableCount === 1
    ? [requirementCount]
    : [firstTableRequirementCount, requirementCount - firstTableRequirementCount];
  const tables = requirementsPerTable.map((_, index) => ({
    x: BorekSpacing.marginX + index * (tableWidth + BorekGrid.columnGap),
    y: tableTop,
    w: tableWidth,
    h: tableBottom - tableTop,
  }));
  const pillInset = BorekGrid.rowGap / 2;
  const statusPills = tables.flatMap((table, tableIndex) => {
    const tableRequirementCount = requirementsPerTable[tableIndex];
    const columnWidth = table.w / 2;
    const rowHeight = table.h / (tableRequirementCount + 1);
    return Array.from({ length: tableRequirementCount }, (_, rowIndex) => ({
      x: table.x + columnWidth + pillInset,
      y: table.y + rowHeight * (rowIndex + 1) + pillInset,
      w: columnWidth - pillInset * 2,
      h: rowHeight - pillInset * 2,
    }));
  });

  return {
    subtitle: hasSubtitle
      ? {
          x: BorekSpacing.marginX,
          y: master.contentTopY,
          w: contentWidth,
          h: subtitleHeight,
        }
      : undefined,
    tables,
    statusPills,
  };
}

function addSubtitle(slide: PptxGenJS.Slide, subtitle: string, rect: ContentCardRect): void {
  slide.addText(subtitle, {
    ...rect,
    color: BorekColors.mutedText,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "left",
    valign: "top",
  });
}

function addStatusPill(
  slide: PptxGenJS.Slide,
  rect: ContentCardRect,
  status: RequirementStatus,
): void {
  const colors = resolveRequirementStatusColors(status);

  slide.addShape(CONTENT_CARD_SHAPE, {
    ...rect,
    fill: { color: colors.fill },
    line: { color: colors.border, width: BorekBorders.divider.lineWidthPt },
    rectRadius: BorekBorders.card.borderRadiusInches,
  });
  slide.addText(formatRequirementStatusLabel(status), {
    ...rect,
    color: colors.text,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    bold: true,
    align: "center",
    valign: "middle",
  });
}

/** Render one validated requirements matrix with native table cells and semantic status pills. */
export function renderRequirementsMatrix01(
  pptx: PptxGenJS,
  spec: Readonly<RequirementsMatrix01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const layout = computeRequirementsMatrix01Layout(Boolean(spec.subtitle), spec.requirements.length);

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }

  const requirementsPerTable = layout.tables.length === 1
    ? [spec.requirements]
    : [
        spec.requirements.slice(0, Math.ceil(spec.requirements.length / 2)),
        spec.requirements.slice(Math.ceil(spec.requirements.length / 2)),
      ];
  layout.tables.forEach((table, index) => {
    addDataTable(slide, table, {
      headers: ["Requirement", "Status"],
      rows: requirementsPerTable[index].map((requirement) => [
        `${requirement.category} — ${requirement.title}`,
        "",
      ]),
    });
  });

  spec.requirements.forEach((requirement, index) => {
    const status = parseRequirementStatus(requirement.status);
    if (!status) {
      throw new Error(`Unsupported requirement status: ${requirement.status}`);
    }
    addStatusPill(slide, layout.statusPills[index], status);
  });

  return slide;
}
