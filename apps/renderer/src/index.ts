import type { FrameworkObject, PresentationPlan, SlideSpecBase } from "./contracts";

/** AT-5 wiring proof: renderer service depends on generated contract types. */
export type RendererContractTypes = {
  frameworkObject: FrameworkObject;
  presentationPlan: PresentationPlan;
  slideSpecBase: SlideSpecBase;
};

export function rendererContractTypesLoaded(): true {
  return true;
}
