/** MS-23: deterministic Group C golden cases backed by canonical realistic SlideSpecs. */

import architectureFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_c/architecture_01.realistic.json" with { type: "json" };
import complianceFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_c/compliance_01.realistic.json" with { type: "json" };
import nextStepsFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_c/next_steps_01.realistic.json" with { type: "json" };
import openQuestionsFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_c/open_questions_01.realistic.json" with { type: "json" };
import successMetricsFixtureJson from "../../../packages/contracts/fixtures/slide_spec/group_c/success_metrics_01.realistic.json" with { type: "json" };
import type { LayoutId, SlideSpecBase } from "../../../apps/renderer/src/contracts.js";
import { slideFileName } from "../compare.js";

export type GroupCGoldenCase = {
  id: string;
  layoutId: LayoutId;
  referenceFileName: string;
  sourceFixture: string;
  spec: SlideSpecBase;
};

export const GROUP_C_GOLDEN_CASES: readonly GroupCGoldenCase[] = [
  {
    id: "group-c-architecture-01",
    layoutId: "ARCHITECTURE_01",
    referenceFileName: slideFileName(1),
    sourceFixture: "architecture_01.realistic.json",
    spec: architectureFixtureJson as unknown as SlideSpecBase,
  },
  {
    id: "group-c-compliance-01",
    layoutId: "COMPLIANCE_01",
    referenceFileName: slideFileName(2),
    sourceFixture: "compliance_01.realistic.json",
    spec: complianceFixtureJson as unknown as SlideSpecBase,
  },
  {
    id: "group-c-success-metrics-01",
    layoutId: "SUCCESS_METRICS_01",
    referenceFileName: slideFileName(3),
    sourceFixture: "success_metrics_01.realistic.json",
    spec: successMetricsFixtureJson as unknown as SlideSpecBase,
  },
  {
    id: "group-c-open-questions-01",
    layoutId: "OPEN_QUESTIONS_01",
    referenceFileName: slideFileName(4),
    sourceFixture: "open_questions_01.realistic.json",
    spec: openQuestionsFixtureJson as unknown as SlideSpecBase,
  },
  {
    id: "group-c-next-steps-01",
    layoutId: "NEXT_STEPS_01",
    referenceFileName: slideFileName(5),
    sourceFixture: "next_steps_01.realistic.json",
    spec: nextStepsFixtureJson as unknown as SlideSpecBase,
  },
] as const;
