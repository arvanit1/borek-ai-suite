/** MS-17: deterministic COMPLIANCE_01 renderer — cards + optional MASTER_CLOSING. */

import type PptxGenJS from "pptxgenjs";

import type { Compliance01SlideSpec } from "../../../../generated/typescript/contracts/slide_spec_group_c_compliance_01.js";
import { addContentCard } from "../../design_system/components/addContentCard.js";
import { addSectionLabel } from "../../design_system/components/addSectionLabel.js";
import { addSlideTitle } from "../../design_system/components/addSlideTitle.js";
import { MASTER_CLOSING_NAME } from "../../design_system/masters/MASTER_CLOSING.js";
import { MASTER_CONTENT_NAME } from "../../design_system/masters/MASTER_CONTENT.js";
import { computeCardGridLayout } from "./cardGrid.js";
import { addSubtitle } from "./contentBand.js";

/** Map Lucide-style icon keys to a human card title. Unknown keys are title-cased. */
export function complianceItemTitle(icon: string): string {
  const labels: Record<string, string> = {
    lock: "Confidentiality",
    "no-entry": "Guardrails",
    "shield-check": "Audit trail",
    shield: "Protection",
    key: "Access control",
    "user-check": "Human approval",
    "user-shield": "Posting control",
  };
  if (labels[icon]) {
    return labels[icon];
  }
  return icon
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/** Render one validated COMPLIANCE_01 SlideSpec using shared content-card primitives. */
export function renderCompliance01(
  pptx: PptxGenJS,
  spec: Readonly<Compliance01SlideSpec>,
): PptxGenJS.Slide {
  const dark = spec.darkBackground;
  const slide = pptx.addSlide({
    masterName: dark ? MASTER_CLOSING_NAME : MASTER_CONTENT_NAME,
  });
  const layout = computeCardGridLayout(Boolean(spec.subtitle), spec.items.length, dark);

  if (spec.sectionLabel) {
    addSectionLabel(slide, spec.sectionLabel);
  }
  addSlideTitle(slide, spec.title, dark ? { variant: "dark" } : undefined);
  if (spec.subtitle && layout.subtitle) {
    addSubtitle(slide, spec.subtitle, layout.subtitle, dark ? "dark" : "light");
  }

  spec.items.forEach((item, index) => {
    const card = layout.cards[index];
    if (!card) {
      return;
    }
    addContentCard(slide, card, {
      title: complianceItemTitle(item.icon),
      description: item.text,
    });
  });

  return slide;
}
