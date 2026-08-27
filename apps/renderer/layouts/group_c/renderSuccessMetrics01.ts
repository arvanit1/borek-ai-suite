/** MS-18: deterministic SUCCESS_METRICS_01 renderer — non-monetary criteria cards. */

import type PptxGenJS from "pptxgenjs";

import type { SuccessMetrics01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_c_success_metrics_01.js";
import { addKpiCard } from "../../design_system/components/addKpiCard.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import { MASTER_CONTENT_NAME } from "../../design_system/masters/MASTER_CONTENT.js";
import { computeCardGridLayout } from "./cardGrid.js";
import { addSubtitle } from "./contentBand.js";

/** Render one validated SUCCESS_METRICS_01 SlideSpec. Criteria are labels, never currency. */
export function renderSuccessMetrics01(
  pptx: PptxGenJS,
  spec: Readonly<SuccessMetrics01SlideSpec>,
): PptxGenJS.Slide {
  const slide = pptx.addSlide({ masterName: MASTER_CONTENT_NAME });
  const layout = computeCardGridLayout(Boolean(spec.subtitle), spec.criteria.length);

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle);
  }

  spec.criteria.forEach((criterion, index) => {
    const card = layout.cards[index];
    if (!card) {
      return;
    }
    addKpiCard(slide, card, {
      value: criterion.title,
      label: criterion.description,
    });
  });

  return slide;
}
