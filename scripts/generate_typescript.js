#!/usr/bin/env node
/**
 * AT-5: Generate TypeScript types from canonical JSON Schemas (AT-1 + AT-2 + AT-3).
 */
const { execSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const CONTRACTS = path.join(ROOT, "packages", "contracts");
const OUT_DIR = path.join(ROOT, "generated", "typescript", "contracts");

const SCHEMAS = [
  ["framework_object.schema.json", "framework_object.ts"],
  ["presentation_plan.schema.json", "presentation_plan.ts"],
  ["slide_spec/base.schema.json", "slide_spec_base.ts"],
  ["slide_spec/group_a/cover_01.schema.json", "slide_spec_group_a_cover_01.ts"],
  ["slide_spec/group_a/context_01.schema.json", "slide_spec_group_a_context_01.ts"],
  [
    "slide_spec/group_a/problem_solution_01.schema.json",
    "slide_spec_group_a_problem_solution_01.ts",
  ],
  ["slide_spec/group_a/scope_01.schema.json", "slide_spec_group_a_scope_01.ts"],
  [
    "slide_spec/group_a/requirements_matrix_01.schema.json",
    "slide_spec_group_a_requirements_matrix_01.ts",
  ],
  ["slide_spec/group_b/process_flow_01.schema.json", "slide_spec_group_b_process_flow_01.ts"],
  ["slide_spec/group_b/timeline_01.schema.json", "slide_spec_group_b_timeline_01.ts"],
  ["slide_spec/group_b/milestones_01.schema.json", "slide_spec_group_b_milestones_01.ts"],
  ["slide_spec/group_b/team_fte_01.schema.json", "slide_spec_group_b_team_fte_01.ts"],
  ["slide_spec/group_c/architecture_01.schema.json", "slide_spec_group_c_architecture_01.ts"],
  ["slide_spec/group_c/compliance_01.schema.json", "slide_spec_group_c_compliance_01.ts"],
  [
    "slide_spec/group_c/success_metrics_01.schema.json",
    "slide_spec_group_c_success_metrics_01.ts",
  ],
  [
    "slide_spec/group_c/open_questions_01.schema.json",
    "slide_spec_group_c_open_questions_01.ts",
  ],
  ["slide_spec/group_c/next_steps_01.schema.json", "slide_spec_group_c_next_steps_01.ts"],
];

function loadChapterRegistry() {
  const registryPath = path.join(CONTRACTS, "chapter_registry.json");
  const registry = JSON.parse(fs.readFileSync(registryPath, "utf8"));
  if (!Array.isArray(registry.chapters) || registry.chapters.length !== 14) {
    throw new Error("chapter_registry.json must define exactly 14 chapters");
  }
  return registry;
}

/**
 * json-schema-to-typescript does not emit usable types for prefixItems tuples.
 * Patch FrameworkObject.chapters using chapter_registry.json (aligned with AT-1 schema).
 */
function buildFrameworkObjectChapterTypes(registry) {
  const chapterTypes = registry.chapters.map((chapter, index) => {
    const idLiteral = JSON.stringify(chapter.chapter_id);
    const titleLiteral = JSON.stringify(chapter.title);
    return `export type ChapterAtIndex${index} = ChapterBase & { chapter_id: ${idLiteral}; title: ${titleLiteral}; };`;
  });
  const tupleMembers = registry.chapters.map((_chapter, index) => `ChapterAtIndex${index}`).join(", ");

  return `/**
 * Chapter tuple types for FrameworkObject.chapters (AT-1 prefixItems).
 * Patched by scripts/generate_typescript.js because json-schema-to-typescript emits never[].
 */
export interface ConversationRef {
  conversation_id: string;
  speaker_role: string;
  excerpt_pointer: string;
}
export interface ChapterBase {
  body: string | Array<Record<string, unknown>>;
  source_refs: ConversationRef[];
}
${chapterTypes.join("\n")}
export type FrameworkObjectChapters = [${tupleMembers}];
`;
}

function patchFrameworkObjectTypes(source, registry) {
  if (!source.includes("chapters: never[];")) {
    throw new Error(
      "Expected framework_object.ts to contain chapters: never[]; apply patch after json-schema-to-typescript",
    );
  }

  const chapterTypes = buildFrameworkObjectChapterTypes(registry);
  return source
    .replace("export interface FrameworkObject {", `${chapterTypes}\nexport interface FrameworkObject {`)
    .replace("  chapters: never[];", "  chapters: FrameworkObjectChapters;");
}

function writeIndex() {
  const indexContent = `export * from "./framework_object";
export type {
  LayoutId,
  FrameworkReference,
  PresentationPlan,
  PlannedSlide,
} from "./presentation_plan";
export type { ChapterId, SlideSpecBase } from "./slide_spec_base";
export type { Cover01SlideSpec } from "./slide_spec_group_a_cover_01";
export type { Context01SlideSpec } from "./slide_spec_group_a_context_01";
export type { ProblemSolution01SlideSpec } from "./slide_spec_group_a_problem_solution_01";
export type { Scope01SlideSpec } from "./slide_spec_group_a_scope_01";
export type { RequirementsMatrix01SlideSpec } from "./slide_spec_group_a_requirements_matrix_01";
export type { ProcessFlow01SlideSpec } from "./slide_spec_group_b_process_flow_01";
export type { Timeline01SlideSpec } from "./slide_spec_group_b_timeline_01";
export type { Milestones01SlideSpec } from "./slide_spec_group_b_milestones_01";
export type { TeamFte01SlideSpec } from "./slide_spec_group_b_team_fte_01";
export type { Architecture01SlideSpec } from "./slide_spec_group_c_architecture_01";
export type { Compliance01SlideSpec } from "./slide_spec_group_c_compliance_01";
export type { SuccessMetrics01SlideSpec } from "./slide_spec_group_c_success_metrics_01";
export type { OpenQuestions01SlideSpec } from "./slide_spec_group_c_open_questions_01";
export type { NextSteps01SlideSpec } from "./slide_spec_group_c_next_steps_01";
`;
  fs.writeFileSync(path.join(OUT_DIR, "index.ts"), `${indexContent}\n`, "utf8");
}

function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const chapterRegistry = loadChapterRegistry();

  for (const [schemaName, outputName] of SCHEMAS) {
    const schemaPath = path.join(CONTRACTS, schemaName);
    const outputPath = path.join(OUT_DIR, outputName);
    execSync(
      `npx --yes json-schema-to-typescript --cwd="${path.dirname(schemaPath)}" -i "${schemaPath}" -o "${outputPath}"`,
      {
        stdio: "inherit",
        cwd: ROOT,
        shell: true,
      },
    );

    if (outputName === "framework_object.ts") {
      const generated = fs.readFileSync(outputPath, "utf8");
      fs.writeFileSync(outputPath, patchFrameworkObjectTypes(generated, chapterRegistry), "utf8");
    }
  }

  writeIndex();
  console.log(`Generated ${SCHEMAS.length} TypeScript modules in ${OUT_DIR}`);
}

main();
