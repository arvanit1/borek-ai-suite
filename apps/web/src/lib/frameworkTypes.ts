export interface ConversationRef {
  conversation_id: string;
  speaker_role: string;
  excerpt_pointer: string;
}

export interface FrameworkChapter {
  chapter_id: string;
  title: string;
  body: string | Record<string, unknown>[];
  source_refs: ConversationRef[];
}

export interface FrameworkObject {
  schema_version: string;
  opportunity_id: string;
  title: string;
  department: string;
  status: string;
  priority_rank: number | null;
  quality_scores: {
    opportunity_rating: number;
    conversation_quality: number;
    build_readiness: number;
    rationale: Record<string, string>;
  };
  kpis: Record<string, unknown>[];
  systems: Record<string, unknown>[];
  rules: Record<string, unknown>[];
  exceptions: Record<string, unknown>[];
  access_needs: Record<string, unknown>[];
  evolution_stages: Record<string, unknown>[];
  open_items: Record<string, unknown>[];
  chapters: FrameworkChapter[];
  version: number;
  generated_from: string[];
  previous_version_id: string | null;
  change_log: string[];
  created_at: string;
  updated_at: string;
}

export interface FrameworkVersionResponse {
  id: string;
  opportunity_id: string;
  version_number: number;
  status: string;
  framework_json: FrameworkObject;
  created_by: string;
  created_at: string;
}
