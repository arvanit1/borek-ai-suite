import type { PlannedSlide, PresentationPlanObject, SlidePreviewRow } from "./planTypes";

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

export function formatLayoutLabel(layoutId: string): string {
  return layoutId.replace(/_/g, " ");
}
