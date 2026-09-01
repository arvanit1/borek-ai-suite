export interface DeckSlidePreview {
  slide_id: string;
  slide_index: number;
  layout_id: string;
  preview_url: string;
}

export interface DeckCenterResponse {
  presentation_id: string;
  presentation_name: string;
  version_number: number;
  status: string;
  slides: DeckSlidePreview[];
  pptx_download_url: string;
  pdf_download_url: string;
}

export interface PresentationResponse {
  id: string;
  presentation_plan_id: string;
  name: string;
  status: string;
  created_at: string;
}

export interface PresentationGenerateResponse {
  job_id: string;
  status: string;
  presentation_id: string | null;
  presentation_plan_id: string | null;
  is_existing_job?: boolean;
}

export interface SlidePreviewTile {
  slideIndex: number;
  layoutId: string;
  previewUrl: string;
}
