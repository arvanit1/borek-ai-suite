/** BT-17: deterministic COVER_01 renderer. */

import type PptxGenJS from "pptxgenjs";

import type { Cover01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_a_cover_01.js";
import {
  addKpiCard,
  type KpiCardRect,
} from "../../design_system/components/addKpiCard.js";
import {
  addSectionLabel,
  COVER_SECTION_LABEL_PLACEHOLDER,
} from "../../design_system/components/addSectionLabel.js";
import {
  addSlideTitle,
  COVER_TITLE_PLACEHOLDER,
} from "../../design_system/components/addSlideTitle.js";
import {
  computeMasterCoverLayout,
  MASTER_COVER_NAME,
  MASTER_COVER_SUBTITLE_PLACEHOLDER,
} from "../../design_system/masters/MASTER_COVER.js";
import { BorekColors } from "../../design_system/tokens/colors.js";
import { BorekSpacing } from "../../design_system/tokens/spacing.js";
import { BorekTypography } from "../../design_system/tokens/typography.js";

/** Select balanced slots from the three token-derived MASTER_COVER badge regions. */
export function computeCover01BadgeRects(count: number): readonly KpiCardRect[] {
  const slots = computeMasterCoverLayout().statBadges.map((slot) => ({
    ...slot,
    y: slot.y - BorekSpacing.footerHeight,
    h: slot.h + BorekSpacing.footerHeight,
  })) as [KpiCardRect, KpiCardRect, KpiCardRect];

  if (count <= 0) {
    return [];
  }
  if (count === 1) {
    return [slots[1]];
  }
  if (count === 2) {
    return [slots[0], slots[2]];
  }
  return slots.slice(0, 3);
}

function addCoverSubtitle(slide: PptxGenJS.Slide, subtitle: string): void {
  slide.addText(subtitle, {
    placeholder: MASTER_COVER_SUBTITLE_PLACEHOLDER,
    color: BorekColors.background,
    fontFace: BorekTypography.fonts.body,
    fontSize: BorekTypography.defaultSizes.body,
    align: "left",
    valign: "top",
  });
}

/** Render one validated COVER_01 SlideSpec using the shared cover master and primitives. */
export function renderCover01(
  pptx: PptxGenJS,
  spec: Readonly<Cover01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_COVER_NAME });
  const badgeRects = computeCover01BadgeRects(spec.statBadges.length);

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel, {
      placeholder: COVER_SECTION_LABEL_PLACEHOLDER,
      variant: "inverse",
    });
  }
  addSlideTitle(slide, spec.title, {
    placeholder: COVER_TITLE_PLACEHOLDER,
    variant: "dark",
  });
  addCoverSubtitle(slide, spec.subtitle);

  spec.statBadges.forEach((badge, index) => {
    addKpiCard(slide, badgeRects[index], badge, { variant: "inverse" });
  });

  return slide;
}
