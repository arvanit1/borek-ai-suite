import type { DeckCenterResponse, SlidePreviewTile } from "./deckTypes";

export function mapDeckSlides(deck: DeckCenterResponse): SlidePreviewTile[] {
  return deck.slides
    .slice()
    .sort((left, right) => left.slide_index - right.slide_index)
    .map((slide) => ({
      slideIndex: slide.slide_index,
      layoutId: slide.layout_id,
      previewUrl: slide.preview_url,
    }));
}

export function buildDownloadFilename(presentationName: string, extension: "pptx" | "pdf"): string {
  const safe = presentationName.trim().replace(/[^\w\- ]+/g, "").replace(/\s+/g, "-") || "presentation";
  return `${safe}.${extension}`;
}
