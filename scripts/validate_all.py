#!/usr/bin/env python3
"""Client delivery gate: schema tickets (AT-1..AT-12) and codegen checks must pass."""

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
<<<<<<< HEAD
                "import generated.python.contracts.slide_spec_group_c_architecture_01; "
                "import generated.python.contracts.slide_spec_group_c_compliance_01; "
                "import generated.python.contracts.slide_spec_group_c_success_metrics_01; "
                "import generated.python.contracts.slide_spec_group_c_open_questions_01; "
                "import generated.python.contracts.slide_spec_group_c_next_steps_01; "
=======
                "import generated.python.contracts.slide_spec_group_b_process_flow_01; "
                "import generated.python.contracts.slide_spec_group_b_timeline_01; "
                "import generated.python.contracts.slide_spec_group_b_milestones_01; "
                "import generated.python.contracts.slide_spec_group_b_team_fte_01; "
>>>>>>> origin/main
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
<<<<<<< HEAD
        "slide_spec_group_c_architecture_01.ts",
        "slide_spec_group_c_compliance_01.ts",
        "slide_spec_group_c_success_metrics_01.ts",
        "slide_spec_group_c_open_questions_01.ts",
        "slide_spec_group_c_next_steps_01.ts",
=======
        "slide_spec_group_b_process_flow_01.ts",
        "slide_spec_group_b_timeline_01.ts",
        "slide_spec_group_b_milestones_01.ts",
        "slide_spec_group_b_team_fte_01.ts",
>>>>>>> origin/main
    ):
        ts_path = ROOT / "generated" / "typescript" / "contracts" / ts_name
        if not ts_path.is_file():
            raise SystemExit(f"TypeScript codegen did not produce {ts_name}")
    run(["npm", "run", "typecheck", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at9", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at10", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at11", "--workspace", "borek-renderer"], shell=True)
    run(["npm", "run", "test:at12", "--workspace", "borek-renderer"], shell=True)
    print("typescript codegen ok")
    print("renderer contract types ok")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
