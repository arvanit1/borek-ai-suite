export interface PlannedSlide {
  order: number;
  purpose: string;
  layoutId: string;
  frameworkReferences: string[];
}

export interface PresentationPlanObject {
  schema_version: string;
  title: string;
  slides: PlannedSlide[];
}

export interface PresentationPlanResponse {
  id: string;
  framework_version_id: string;
  plan_json: PresentationPlanObject;
  created_at: string;
}

export interface PresentationPlanGenerateResponse {
  job_id: string;
  status: string;
  presentation_plan_id: string;
  is_existing_job?: boolean;
}

export interface SlidePreviewRow {
  order: number;
  purpose: string;
  layoutId: string;
}
