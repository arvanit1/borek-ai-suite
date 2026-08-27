#!/usr/bin/env python3
"""Client delivery gate: schema tickets (AT-1..AT-28) and codegen checks must pass."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, shell: bool = False) -> None:
    print("+", " ".join(command) if isinstance(command, list) else command)
    subprocess.run(command, cwd=ROOT, check=True, shell=shell)


def main() -> int:
    run([sys.executable, "-m", "pytest", "tests/unit", "-v"])
    run([sys.executable, "-m", "pytest", "tests/integration/full_pipeline", "-v"])
    run([sys.executable, "scripts/generate_pydantic.py"])
    run(["node", "scripts/generate_typescript.js"])
    run(
        [
            sys.executable,
            "-c",
            (
                "import generated.python.contracts.framework_object; "
                "import generated.python.contracts.presentation_plan; "
                "import generated.python.contracts.slide_spec_base; "
                "import generated.python.contracts.slide_spec_group_a_cover_01; "
                "import generated.python.contracts.slide_spec_group_a_context_01; "
                "import generated.python.contracts.slide_spec_group_a_problem_solution_01; "
                "import generated.python.contracts.slide_spec_group_a_scope_01; "
                "import generated.python.contracts.slide_spec_group_a_requirements_matrix_01; "
                "import generated.python.contracts.slide_spec_group_b_process_flow_01; "
                "import generated.python.contracts.slide_spec_group_b_timeline_01; "
                "import generated.python.contracts.slide_spec_group_b_milestones_01; "
                "import generated.python.contracts.slide_spec_group_b_team_fte_01; "
                "import generated.python.contracts.slide_spec_group_c_architecture_01; "
                "import generated.python.contracts.slide_spec_group_c_compliance_01; "
                "import generated.python.contracts.slide_spec_group_c_success_metrics_01; "
                "import generated.python.contracts.slide_spec_group_c_open_questions_01; "
                "import generated.python.contracts.slide_spec_group_c_next_steps_01; "
                "print('python codegen imports ok')"
            ),
        ]
    )
    for ts_name in (
        "framework_object.ts",
        "presentation_plan.ts",
        "slide_spec_base.ts",
        "slide_spec_group_a_cover_01.ts",
        "slide_spec_group_a_context_01.ts",
        "slide_spec_group_a_problem_solution_01.ts",
        "slide_spec_group_a_scope_01.ts",
        "slide_spec_group_a_requirements_matrix_01.ts",
        "slide_spec_group_b_process_flow_01.ts",
        "slide_spec_group_b_timeline_01.ts",
        "slide_spec_group_b_milestones_01.ts",
        "slide_spec_group_b_team_fte_01.ts",
        "slide_spec_group_c_architecture_01.ts",
        "slide_spec_group_c_compliance_01.ts",
        "slide_spec_group_c_success_metrics_01.ts",
        "slide_spec_group_c_open_questions_01.ts",
        "slide_spec_group_c_next_steps_01.ts",
    ):
        ts_path = ROOT / "generated" / "typescript" / "contracts" / ts_name
        if not ts_path.is_file():
            raise SystemExit(f"TypeScript codegen did not produce {ts_name}")
    run(["npm", "run", "typecheck", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "typecheck", "--workspace", "borek-web"], shell=True)
    run(["npm", "run", "test:at46", "--workspace", "borek-web"], shell=True)
    run(["npm", "run", "test:at47", "--workspace", "borek-web"], shell=True)
    run(["npm", "run", "test:at48", "--workspace", "borek-web"], shell=True)
    run(["npm", "run", "test:at49", "--workspace", "borek-web"], shell=True)
    run(["npm", "run", "test:at9", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at10", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at11", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:requirement-status", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at12", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at13", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:grid", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:borders", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:branding", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at14", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at15", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at16", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at17", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at18", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at19", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at20", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at21", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at22", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at23", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at24", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at25", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at26", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at27", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at28", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at29", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at30", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at31", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at32", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at33", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at55", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:bt17", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:bt18", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:bt19", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:bt20", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:bt21", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:jj15", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:jj16", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:jj17", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:jj18", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:jj19", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:jj21", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:jj22", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:ms16", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:ms17", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:ms18", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:ms19", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:ms20", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:ms21", "--workspace", "borek-renderer"], shell=True)
    print("typescript codegen ok")
    print("renderer contract types ok")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
