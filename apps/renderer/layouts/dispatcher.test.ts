/** AT-33 unit checks executed by pytest via `npm run test:at33 --workspace borek-renderer`. */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import PptxGenJS from "pptxgenjs";

import layoutRegistryJson from "../../../packages/contracts/layout_registry.json" with { type: "json" };
import {
  LAYOUT_REGISTRY,
  UnsupportedLayoutError,
  dispatchSlide,
} from "./dispatcher.js";
import type { LayoutId, SlideSpecBase } from "../src/contracts.js";

const LAYOUTS_DIR = fileURLToPath(new URL(".", import.meta.url));
const DISPATCHER_TS = join(LAYOUTS_DIR, "dispatcher.ts");
const STUBS_TS = join(LAYOUTS_DIR, "stubs.ts");

const REGISTRY_LAYOUT_IDS = Object.keys(layoutRegistryJson.layouts).sort();
const DISPATCHER_LAYOUT_IDS = Object.keys(LAYOUT_REGISTRY).sort();

assert.ok(existsSync(DISPATCHER_TS), "dispatcher.ts must exist");
assert.ok(existsSync(STUBS_TS), "stubs.ts must exist");

assert.equal(REGISTRY_LAYOUT_IDS.length, 15, "layout_registry.json must define exactly 15 layouts");
assert.equal(DISPATCHER_LAYOUT_IDS.length, 15, "LAYOUT_REGISTRY must contain exactly 15 entries");
assert.deepEqual(
  DISPATCHER_LAYOUT_IDS,
  REGISTRY_LAYOUT_IDS,
  "LAYOUT_REGISTRY keys must match layout_registry.json layouts exactly",
);

const dispatcherSource = readFileSync(DISPATCHER_TS, "utf8");
assert.doesNotMatch(
  dispatcherSource,
  /\bswitch\s*\(/,
  "dispatcher must be registry-based — no switch on layoutId in dispatcher.ts",
);
assert.doesNotMatch(
  dispatcherSource,
  /\bcase\s+"[A-Z0-9_]+"/,
  "dispatcher must be registry-based — no case branches in dispatcher.ts",
);
assert.match(
  dispatcherSource,
  /export const LAYOUT_REGISTRY/,
  "LAYOUT_REGISTRY must be the single registration point in dispatcher.ts",
);

function minimalSlideSpec(layoutId: LayoutId): SlideSpecBase {
  return {
    schema_version: "1.0",
    layoutId,
    title: `Dispatch test ${layoutId}`,
    sourceChapterIds: ["1"],
  };
}

const pptx = new PptxGenJS();

for (const layoutId of REGISTRY_LAYOUT_IDS as LayoutId[]) {
  assert.doesNotThrow(
    () => dispatchSlide(pptx, minimalSlideSpec(layoutId)),
    `dispatchSlide must not throw for registered layoutId ${layoutId}`,
  );
}

const unknownLayoutId = "UNKNOWN_LAYOUT_99";
let thrown: unknown;

try {
  dispatchSlide(pptx, {
    ...minimalSlideSpec("COVER_01"),
    layoutId: unknownLayoutId as LayoutId,
  });
} catch (error) {
  thrown = error;
}

assert.ok(thrown instanceof UnsupportedLayoutError, "unknown layoutId must throw UnsupportedLayoutError");
assert.notEqual(thrown instanceof Error && !(thrown instanceof UnsupportedLayoutError), true);
assert.equal((thrown as UnsupportedLayoutError).name, "UnsupportedLayoutError");
assert.match(
  (thrown as UnsupportedLayoutError).message,
  new RegExp(unknownLayoutId),
  "UnsupportedLayoutError message must include the layoutId",
);

process.stdout.write("AT-33 renderer unit checks passed\n");
