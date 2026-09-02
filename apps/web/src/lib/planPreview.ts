import type { PlannedSlide, PresentationPlanObject, SlidePreviewRow } from "./planTypes";
import { formatLayoutLabel } from "./presentationReady";

export { formatLayoutLabel };

export function sortSlidesByOrder(slides: PlannedSlide[]): PlannedSlide[] {
  return [...slides].sort((left, right) => left.order - right.order);
}

export function extractSlidePreviewRows(plan: PresentationPlanObject): SlidePreviewRow[] {
  return sortSlidesByOrder(plan.slides).map((slide) => ({
    order: slide.order,
    purpose: slide.purpose,
    layoutId: slide.layoutId,
  }));
}
