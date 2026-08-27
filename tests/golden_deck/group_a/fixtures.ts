/** BT-24: deterministic Group A golden cases backed by canonical realistic SlideSpecs. */

import contextFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_a/context_01.realistic.json" with { type: "json" };
import coverFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_a/cover_01.realistic.json" with { type: "json" };
import problemSolutionFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_a/problem_solution_01.realistic.json" with { type: "json" };
import requirementsFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_a/requirements_matrix_01.realistic.json" with { type: "json" };
import scopeFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_a/scope_01.realistic.json" with { type: "json" };
import type { LayoutId, SlideSpecBase } from "../../../apps/renderer/src/contracts.js";
import { slideFileName } from "../compare.js";

export type GroupAGoldenCase = {
  id: string;
  layoutId: LayoutId;
  referenceFileName: string;
  sourceFixture: string;
  spec: SlideSpecBase;
};

export const GROUP_A_GOLDEN_CASES: readonly GroupAGoldenCase[] = [
  {
    id: "group-a-cover-01",
    layoutId: "COVER_01",
    referenceFileName: slideFileName(1),
    sourceFixture: "cover_01.realistic.json",
    spec: coverFixtureJson as unknown as SlideSpecBase,
  },
  {
    id: "group-a-context-01",
    layoutId: "CONTEXT_01",
    referenceFileName: slideFileName(2),
    sourceFixture: "context_01.realistic.json",
    spec: contextFixtureJson as unknown as SlideSpecBase,
  },
  {
    id: "group-a-problem-solution-01",
    layoutId: "PROBLEM_SOLUTION_01",
    referenceFileName: slideFileName(3),
    sourceFixture: "problem_solution_01.realistic.json",
    spec: problemSolutionFixtureJson as unknown as SlideSpecBase,
  },
  {
    id: "group-a-scope-01",
    layoutId: "SCOPE_01",
    referenceFileName: slideFileName(4),
    sourceFixture: "scope_01.realistic.json",
    spec: scopeFixtureJson as unknown as SlideSpecBase,
  },
  {
    id: "group-a-requirements-matrix-01",
    layoutId: "REQUIREMENTS_MATRIX_01",
    referenceFileName: slideFileName(5),
    sourceFixture: "requirements_matrix_01.realistic.json",
    spec: requirementsFixtureJson as unknown as SlideSpecBase,
  },
] as const;
