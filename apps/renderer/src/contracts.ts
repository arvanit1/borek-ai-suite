/**
 * AT-5: renderer imports canonical contract types from generated output.
 * Regenerate after schema changes: npm run generate:typescript
 */
export type {
  FrameworkObject,
  FrameworkObjectChapters,
  ChapterBase,
  ConversationRef,
} from "../../../generated/typescript/contracts/framework_object";
export type {
  LayoutId,
  FrameworkReference,
  PresentationPlan,
  PlannedSlide,
} from "../../../generated/typescript/contracts/presentation_plan";
export type { ChapterId, SlideSpecBase } from "../../../generated/typescript/contracts/slide_spec_base";
