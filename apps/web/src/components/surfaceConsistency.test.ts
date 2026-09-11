import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const css = readFileSync("src/app/globals.css", "utf8");

function blocksFor(header: string): string[] {
  const blocks: string[] = [];
  let cursor = 0;
  while (cursor < css.length) {
    const start = css.indexOf(header, cursor);
    if (start < 0) {
      break;
    }
    const open = css.indexOf("{", start);
    let depth = 0;
    let end = open;
    for (; end < css.length; end += 1) {
      if (css[end] === "{") depth += 1;
      if (css[end] === "}") depth -= 1;
      if (depth === 0) {
        end += 1;
        break;
      }
    }
    blocks.push(css.slice(start, end));
    cursor = end;
  }
  return blocks;
}

assert.match(css, /--workspace-card-gap:\s*1\.25rem/);
assert.match(css, /--workspace-card-padding:\s*1\.5rem 1\.5rem 1\.65rem/);
assert.match(css, /--workspace-card-radius:\s*14px/);
assert.match(css, /--workspace-card-shadow:/);

const intakeMain = css.match(/\.intake-main\s*\{([^}]*)\}/)?.[1] ?? "";
assert.match(intakeMain, /width:\s*100%/);
assert.doesNotMatch(intakeMain, /max-width/);

const uploadLayout = css.match(/\.upload-layout\s*\{([^}]*)\}/)?.[1] ?? "";
assert.match(uploadLayout, /grid-template-columns:\s*minmax\(0, 1fr\)/);
assert.match(uploadLayout, /gap:\s*var\(--workspace-card-gap\)/);

const tabletLayout = blocksFor("@media (max-width: 1024px)").find((block) =>
  block.includes(".upload-layout"),
);
assert.ok(tabletLayout);
assert.match(tabletLayout, /\.upload-layout\s*\{[\s\S]*?gap:\s*var\(--workspace-card-gap\)/);

for (const selector of [
  ".recent-card",
  ".journey-upload-summary",
  ".archive-filters",
  ".upload-panel",
  ".upload-meta-card",
]) {
  const escaped = selector.replace(".", "\\.");
  const body = css.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
  assert.match(body, /padding:\s*var\(--workspace-card-padding\)/, selector);
  assert.match(body, /box-shadow:\s*var\(--workspace-card-shadow\)/, selector);
}

assert.match(
  css,
  /\.upload-meta-actions\s*\{[\s\S]*?grid-column:\s*2;[\s\S]*?grid-row:\s*1 \/ span 2;/,
);
assert.match(
  css,
  /\.recent-state-card,\s*\.recent-empty\s*\{[\s\S]*?padding:\s*var\(--workspace-card-padding\)/,
);

const mobileSurfaces = blocksFor("@media (max-width: 640px)").find((block) =>
  block.includes(".upload-meta-actions"),
);
assert.ok(mobileSurfaces);
assert.match(mobileSurfaces, /\.upload-meta-actions\s*\{[\s\S]*?grid-column:\s*1;/);
assert.match(mobileSurfaces, /\.recent-state-card,[\s\S]*?\.recent-empty,/);

for (const component of ["PlanPreviewPanel.tsx", "DeckCenterPanel.tsx"]) {
  const source = readFileSync(fileURLToPath(new URL(`./${component}`, import.meta.url)), "utf8");
  assert.match(source, /className="upload-meta-actions"/, component);
}

console.log("Workspace surface consistency tests passed");
