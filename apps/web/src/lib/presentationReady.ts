export const LAYOUT_CATALOG: ReadonlyArray<{
  id: string;
  label: string;
  category: string;
}> = [
  { id: "COVER_01", label: "Cover", category: "cover" },
  { id: "EXECUTIVE_SUMMARY_01", label: "Executive summary", category: "summary" },
  { id: "CONTEXT_01", label: "Context", category: "context" },
  { id: "PROBLEM_SOLUTION_01", label: "Problem and solution", category: "problem_solution" },
  { id: "SCOPE_01", label: "Scope", category: "scope" },
  { id: "REQUIREMENTS_MATRIX_01", label: "Requirements", category: "requirements" },
  { id: "PROCESS_FLOW_01", label: "Process flow", category: "process" },
  { id: "TIMELINE_01", label: "Timeline", category: "timeline" },
  { id: "MILESTONES_01", label: "Milestones", category: "milestones" },
  { id: "TEAM_FTE_01", label: "Team", category: "team" },
  { id: "ARCHITECTURE_01", label: "Architecture", category: "architecture" },
  { id: "COMPLIANCE_01", label: "Compliance", category: "compliance" },
  { id: "SUCCESS_METRICS_01", label: "Success measures", category: "metrics" },
  { id: "OPEN_QUESTIONS_01", label: "Open questions", category: "questions" },
  { id: "NEXT_STEPS_01", label: "Next steps", category: "closing" },
];

const LAYOUT_BY_ID = new Map(LAYOUT_CATALOG.map((layout) => [layout.id, layout]));

export function formatLayoutLabel(layoutId: string): string {
  const known = LAYOUT_BY_ID.get(layoutId);
  if (known) {
    return known.label;
  }
  return layoutId
    .replace(/_0*\d+$/, "")
    .replace(/[_-]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function layoutCategory(layoutId: string): string | null {
  return LAYOUT_BY_ID.get(layoutId)?.category ?? null;
}

export function alternativeLayouts(layoutId: string): Array<{ id: string; label: string }> {
  const category = layoutCategory(layoutId);
  if (!category) {
    return [];
  }
  return LAYOUT_CATALOG.filter((layout) => layout.category === category && layout.id !== layoutId).map(
    (layout) => ({ id: layout.id, label: layout.label }),
  );
}

export function formatGeneratedAt(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function slideCountLabel(count: number): string {
  return `${count} slide${count === 1 ? "" : "s"}`;
}

export function versionLabel(versionNumber: number | null | undefined): string | null {
  if (versionNumber == null || Number.isNaN(versionNumber)) {
    return null;
  }
  return `Version ${versionNumber}`;
}

export function presentationReadyTitle(ready: boolean): string {
  return ready ? "Your presentation is ready" : "Your presentation";
}

export const DOWNLOAD_POWERPOINT_LABEL = "Download PowerPoint";
export const DOWNLOAD_PDF_LABEL = "Download PDF";
export const PREVIEW_UNAVAILABLE_LABEL = "This slide preview isn’t available yet.";
export const ARTIFACTS_PARTIAL_LABEL =
  "Some files are still missing. You can review available slides and download what’s ready.";
