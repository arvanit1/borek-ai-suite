/**
 * AT-5 proof: contract fixtures assign to generated TypeScript interfaces.
 */
import type {
  FrameworkObject,
  FrameworkObjectChapters,
} from "../../generated/typescript/contracts/framework_object";
import type { PresentationPlan } from "../../generated/typescript/contracts/presentation_plan";
import type { SlideSpecBase } from "../../generated/typescript/contracts/slide_spec_base";
import type { Cover01SlideSpec } from "../../generated/typescript/contracts/slide_spec_group_a_cover_01";
import type { Context01SlideSpec } from "../../generated/typescript/contracts/slide_spec_group_a_context_01";
import type { ProblemSolution01SlideSpec } from "../../generated/typescript/contracts/slide_spec_group_a_problem_solution_01";
import type { Scope01SlideSpec } from "../../generated/typescript/contracts/slide_spec_group_a_scope_01";
import type { RequirementsMatrix01SlideSpec } from "../../generated/typescript/contracts/slide_spec_group_a_requirements_matrix_01";
import type { ProcessFlow01SlideSpec } from "../../generated/typescript/contracts/slide_spec_group_b_process_flow_01";
import type { Timeline01SlideSpec } from "../../generated/typescript/contracts/slide_spec_group_b_timeline_01";
import type { Milestones01SlideSpec } from "../../generated/typescript/contracts/slide_spec_group_b_milestones_01";
import type { TeamFte01SlideSpec } from "../../generated/typescript/contracts/slide_spec_group_b_team_fte_01";

import frameworkFixture from "../../packages/contracts/fixtures/framework_object.minimal.json";
import presentationPlanFixture from "../../packages/contracts/fixtures/presentation_plan.minimal.json";
import slideSpecFixture from "../../packages/contracts/fixtures/slide_spec/architecture_01.minimal.json";
import coverFixture from "../../packages/contracts/fixtures/slide_spec/group_a/cover_01.realistic.json";
import contextFixture from "../../packages/contracts/fixtures/slide_spec/group_a/context_01.realistic.json";
import problemSolutionFixture from "../../packages/contracts/fixtures/slide_spec/group_a/problem_solution_01.realistic.json";
import scopeFixture from "../../packages/contracts/fixtures/slide_spec/group_a/scope_01.realistic.json";
import requirementsMatrixFixture from "../../packages/contracts/fixtures/slide_spec/group_a/requirements_matrix_01.realistic.json";
import processFlowFixture from "../../packages/contracts/fixtures/slide_spec/group_b/process_flow_01.realistic.json";
import timelineFixture from "../../packages/contracts/fixtures/slide_spec/group_b/timeline_01.realistic.json";
import milestonesFixture from "../../packages/contracts/fixtures/slide_spec/group_b/milestones_01.realistic.json";
import teamFteFixture from "../../packages/contracts/fixtures/slide_spec/group_b/team_fte_01.realistic.json";

/** JSON imports widen literals; assert compatibility with generated contract types. */
const frameworkObject: FrameworkObject = frameworkFixture as unknown as FrameworkObject;
const presentationPlan: PresentationPlan = presentationPlanFixture as unknown as PresentationPlan;
const slideSpecBase: SlideSpecBase = slideSpecFixture as unknown as SlideSpecBase;
const cover: Cover01SlideSpec = coverFixture as unknown as Cover01SlideSpec;
const context: Context01SlideSpec = contextFixture as unknown as Context01SlideSpec;
const problemSolution: ProblemSolution01SlideSpec =
  problemSolutionFixture as unknown as ProblemSolution01SlideSpec;
const scope: Scope01SlideSpec = scopeFixture as unknown as Scope01SlideSpec;
const requirementsMatrix: RequirementsMatrix01SlideSpec =
  requirementsMatrixFixture as unknown as RequirementsMatrix01SlideSpec;
const processFlow: ProcessFlow01SlideSpec = processFlowFixture as unknown as ProcessFlow01SlideSpec;
const timeline: Timeline01SlideSpec = timelineFixture as unknown as Timeline01SlideSpec;
const milestones: Milestones01SlideSpec = milestonesFixture as unknown as Milestones01SlideSpec;
const teamFte: TeamFte01SlideSpec = teamFteFixture as unknown as TeamFte01SlideSpec;

/** Tuple chapter order/titles are fixed at codegen time from chapter_registry.json. */
const frameworkChapters: FrameworkObjectChapters =
  frameworkFixture.chapters as unknown as FrameworkObjectChapters;

type ExpectChapter0Title = FrameworkObjectChapters[0]["title"] extends "About this document" ? true : never;
const chapterTitleCheck: ExpectChapter0Title = true;

void frameworkObject;
void presentationPlan;
void slideSpecBase;
void cover;
void context;
void problemSolution;
void scope;
void requirementsMatrix;
void processFlow;
void timeline;
void milestones;
void teamFte;
void frameworkChapters;
void chapterTitleCheck;
