/**
 * AT-5 proof: contract fixtures assign to generated TypeScript interfaces.
 */
import type {
  FrameworkObject,
  FrameworkObjectChapters,
} from "../../generated/typescript/contracts/framework_object";
import type { PresentationPlan } from "../../generated/typescript/contracts/presentation_plan";
import type { SlideSpecBase } from "../../generated/typescript/contracts/slide_spec_base";

import frameworkFixture from "../../packages/contracts/fixtures/framework_object.minimal.json";
import presentationPlanFixture from "../../packages/contracts/fixtures/presentation_plan.minimal.json";
import slideSpecFixture from "../../packages/contracts/fixtures/slide_spec/architecture_01.minimal.json";

/** JSON imports widen literals; assert compatibility with generated contract types. */
const frameworkObject: FrameworkObject = frameworkFixture as unknown as FrameworkObject;
const presentationPlan: PresentationPlan = presentationPlanFixture as unknown as PresentationPlan;
const slideSpecBase: SlideSpecBase = slideSpecFixture as unknown as SlideSpecBase;

/** Tuple chapter order/titles are fixed at codegen time from chapter_registry.json. */
const frameworkChapters: FrameworkObjectChapters =
  frameworkFixture.chapters as unknown as FrameworkObjectChapters;

type ExpectChapter0Title = FrameworkObjectChapters[0]["title"] extends "About this document" ? true : never;
const chapterTitleCheck: ExpectChapter0Title = true;

void frameworkObject;
void presentationPlan;
void slideSpecBase;
void frameworkChapters;
void chapterTitleCheck;
