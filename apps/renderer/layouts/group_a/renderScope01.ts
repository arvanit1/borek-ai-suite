/** BT-20: deterministic SCOPE_01 renderer. */

import type PptxGenJS from "pptxgenjs";

import type { Scope01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_a_scope_01.js";
import { addBulletList, type BulletListRect } from "../../design_system/components/addBulletList.js";
import type { ContentCardRect } from "../../design_system/components/addContentCard.js";
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
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { BorekTypography } from "../../design_system/tokens/typography.js";

export interface Scope01Layout {
  subtitle?: ContentCardRect;
  included: ScopeAreaLayout;
  later: ScopeAreaLayout;
  divider: ContentCardRect;
}

export interface ScopeAreaLayout {
  label: ContentCardRect;
  list: BulletListRect;
}

/** Compute two clearly separated scope areas from shared master/grid tokens. */
export function computeScope01Layout(hasSubtitle: boolean): Scope01Layout {
  const master = computeMasterContentLayout();
  const contentWidth = BorekSlide.widthInches - BorekSpacing.marginX * 2;
  const subtitlePresence = Number(hasSubtitle);
  const subtitleHeight = BorekSpacing.footerHeight * subtitlePresence;
  const subtitleGap = BorekGrid.rowGap * subtitlePresence;
  const areasTop = master.contentTopY + subtitleHeight + subtitleGap;
  const areasBottom = master.branding.footer.y - BorekGrid.rowGap;
  const includedWidth = (contentWidth - BorekGrid.columnGap) * (3 / 5);
  const laterWidth = contentWidth - BorekGrid.columnGap - includedWidth;
  const areaHeight = areasBottom - areasTop;
  const labelHeight = BorekSpacing.footerHeight;
  const listTop = areasTop + labelHeight + BorekGrid.rowGap / 2;
  const listHeight = areasBottom - listTop;
  const laterX = BorekSpacing.marginX + includedWidth + BorekGrid.columnGap;

  return {
    subtitle: hasSubtitle
      ? {
          x: BorekSpacing.marginX,
          y: master.contentTopY,
          w: contentWidth,
          h: subtitleHeight,
        }
      : undefined,
    included: {
      label: {
        x: BorekSpacing.marginX,
        y: areasTop,
        w: includedWidth,
        h: labelHeight,
      },
      list: {
        x: BorekSpacing.marginX,
        y: listTop,
        w: includedWidth,
        h: listHeight,
      },
    },
    later: {
      label: {
        x: laterX,
        y: areasTop,
        w: laterWidth,
        h: labelHeight,
      },
      list: {
        x: laterX,
        y: listTop,
        w: laterWidth,
        h: listHeight,
      },
    },
    divider: {
      x: laterX - BorekGrid.columnGap / 2,
      y: areasTop,
      w: 0,
      h: areaHeight,
    },
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

function addScopeArea(
  slide: PptxGenJS.Slide,
  area: ScopeAreaLayout,
  title: string,
  items: readonly string[],
): void {
  slide.addText(title, {
    ...area.label,
    color: BorekColors.text,
    fontFace: BorekTypography.fonts.heading,
    fontSize: BorekTypography.defaultSizes.body,
    bold: true,
    align: "left",
    valign: "top",
  });
  addBulletList(slide, area.list, items);
}

/** Render one validated SCOPE_01 SlideSpec using shared content primitives. */
export function renderScope01(
  pptx: PptxGenJS,
  spec: Readonly<Scope01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const layout = computeScope01Layout(Boolean(spec.subtitle));

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }

  slide.addShape("line", {
    ...layout.divider,
    line: {
      color: BorekBorders.divider.color,
      width: BorekBorders.divider.lineWidthPt,
    },
  });
  addScopeArea(slide, layout.included, "Included", spec.included);
  addScopeArea(slide, layout.later, "Later", spec.later);

  return slide;
}
