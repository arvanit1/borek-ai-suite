#!/usr/bin/env python3
"""AT-4: Generate Pydantic v2 models from canonical JSON Schemas (AT-1, AT-2, AT-3)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "packages" / "contracts"
OUT_DIR = ROOT / "generated" / "python" / "contracts"

# Single registry for AT-4 scope. Extend when new core schemas land (e.g. layout SlideSpecs).
SCHEMAS = [
    ("framework_object.schema.json", "framework_object.py"),
    ("presentation_plan.schema.json", "presentation_plan.py"),
    ("slide_spec/base.schema.json", "slide_spec_base.py"),
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "generated" / "__init__.py").write_text("", encoding="utf-8")
    (ROOT / "generated" / "python" / "__init__.py").write_text("", encoding="utf-8")
    init_file = OUT_DIR / "__init__.py"
    init_file.write_text('"""Generated Pydantic models - do not edit."""\n', encoding="utf-8")

    for schema_name, output_name in SCHEMAS:
        schema_path = CONTRACTS / schema_name
        output_path = OUT_DIR / output_name
        cmd = [
            sys.executable,
            "-m",
            "datamodel_code_generator",
            "--input",
            str(schema_path),
            "--input-file-type",
            "jsonschema",
            "--output",
            str(output_path),
            "--output-model-type",
            "pydantic_v2.BaseModel",
            "--use-standard-collections",
            "--use-union-operator",
            "--field-constraints",
            "--use-default",
            "--formatters",
            "builtin",
            "--disable-timestamp",
        ]
        subprocess.run(cmd, check=True)

    print(f"Generated {len(SCHEMAS)} Pydantic modules in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
