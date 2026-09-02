const FIELD_LABELS: Record<string, string> = {
  access_needs: "Access needs",
  action: "Suggested next step",
  ai_split: "Where AI is used",
  assumptions_banner: "Assumptions apply",
  automation_rate: "Automation rate",
  band: "Readiness",
  block: "Section type",
  blocking_items: "Issues to resolve",
  body: "Content",
  build_readiness: "Build readiness",
  bullets: "Highlights",
  business_case: "Business case",
  caption: "Caption",
  category: "Category",
  chapter_id: "Chapter",
  conversation_id: "Conversation",
  conversation_quality: "Conversation quality",
  created_at: "Created",
  cycle_time: "Cycle time",
  department: "Department",
  description: "Description",
  detail: "Detail",
  evolution_stages: "Evolution stages",
  exceptions: "Exceptions",
  excerpt_pointer: "Excerpt",
  headline: "Headline",
  item: "Item",
  item_type: "Type",
  kpis: "Success measures",
  lead: "Lead",
  metric: "Measure",
  name: "Name",
  not_used_for: "AI is not used for",
  open_items: "Open items",
  opportunity_rating: "Opportunity rating",
  owner: "Owner",
  priority_rank: "Priority",
  prose: "Narrative",
  quality_scores: "Quality scores",
  rationale: "Why this score",
  rules: "Rules",
  source_refs: "Cited sources",
  speaker_role: "Speaker",
  specifically: "Specifically",
  status: "Status",
  summary: "Summary",
  systems: "Systems",
  table: "Table",
  target: "Target",
  text: "Text",
  title: "Title",
  used_for: "AI is used for",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  in_review: "In review",
  confirmed: "Approved",
  READY_TO_APPROVE: "Ready to approve",
  REVIEW_RECOMMENDED: "Review recommended",
  BLOCKING_CONTRADICTION: "Contradiction must be resolved",
  MISSING_REQUIRED_INFORMATION: "Required information is missing",
  WEAK_EVIDENCE: "Evidence is weak",
};

function titleCaseWords(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export function customerFieldLabel(key: string): string {
  const trimmed = key.trim();
  if (!trimmed) {
    return "";
  }
  if (FIELD_LABELS[trimmed]) {
    return FIELD_LABELS[trimmed];
  }
  const snake = trimmed.toLowerCase().replace(/[\s-]+/g, "_");
  if (FIELD_LABELS[snake]) {
    return FIELD_LABELS[snake];
  }
  return titleCaseWords(trimmed.replace(/[_-]+/g, " "));
}

export function customerStatusLabel(status: string): string {
  const trimmed = status.trim();
  if (!trimmed) {
    return "";
  }
  if (STATUS_LABELS[trimmed]) {
    return STATUS_LABELS[trimmed];
  }
  return customerFieldLabel(trimmed);
}

export function customerBlockLabel(blockType: string | null | undefined): string | null {
  if (!blockType || !blockType.trim()) {
    return null;
  }
  return customerFieldLabel(blockType);
}
