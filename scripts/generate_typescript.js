#!/usr/bin/env node
/**
 * Generate TypeScript types from canonical JSON Schemas (AT-5 partial: AT-1 + AT-2 + AT-3).
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
];

function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  for (const [schemaName, outputName] of SCHEMAS) {
    const schemaPath = path.join(CONTRACTS, schemaName);
    const outputPath = path.join(OUT_DIR, outputName);
    execSync(`npx --yes json-schema-to-typescript -i "${schemaPath}" -o "${outputPath}"`, {
      stdio: "inherit",
      cwd: ROOT,
      shell: true,
    });
  }

  const indexExports = SCHEMAS.map(([, out]) => `export * from "./${out.replace(".ts", "")}";`).join("\n");
  fs.writeFileSync(path.join(OUT_DIR, "index.ts"), `${indexExports}\n`, "utf8");
  console.log(`Generated ${SCHEMAS.length} TypeScript modules in ${OUT_DIR}`);
}

main();
