/** Requirement status token resolver unit checks (BT-8 / BT-21 platform support). */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  BorekColors,
  BorekRequirementStatusColors,
  type RequirementStatus,
} from "./colors.js";
import {
  formatRequirementStatusLabel,
  parseRequirementStatus,
  REQUIREMENT_STATUSES,
  resolveRequirementStatusColors,
} from "./requirement_status.js";

const RESOLVER_FILE = join(fileURLToPath(new URL(".", import.meta.url)), "requirement_status.ts");
const HARDCODED_HEX_PATTERN = /#?[0-9A-Fa-f]{6}\b/g;

assert.deepEqual(REQUIREMENT_STATUSES, ["included", "partial", "later"]);

for (const status of REQUIREMENT_STATUSES) {
  const colors = resolveRequirementStatusColors(status);
  assert.equal(colors, BorekRequirementStatusColors[status]);
  for (const value of Object.values(colors)) {
    assert.match(value, /^[0-9A-Fa-f]{6}$/);
  }
}

assert.deepEqual(resolveRequirementStatusColors("included"), {
  fill: BorekColors.primary,
  text: BorekColors.background,
  border: BorekColors.primary,
});

assert.deepEqual(resolveRequirementStatusColors("partial"), {
  fill: BorekColors.background,
  text: BorekColors.primary,
  border: BorekColors.primary,
});

assert.deepEqual(resolveRequirementStatusColors("later"), {
  fill: BorekColors.border,
  text: BorekColors.mutedText,
  border: BorekColors.border,
});

assert.equal(formatRequirementStatusLabel("included"), "Included");
assert.equal(formatRequirementStatusLabel("partial"), "Partial");
assert.equal(formatRequirementStatusLabel("later"), "Later");

assert.equal(parseRequirementStatus("included"), "included");
assert.equal(parseRequirementStatus("unknown"), undefined);

const resolverSource = readFileSync(RESOLVER_FILE, "utf8");
assert.deepEqual([...resolverSource.matchAll(HARDCODED_HEX_PATTERN)], []);

process.stdout.write("requirement status token unit checks passed\n");
