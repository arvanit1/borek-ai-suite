"""BT-9..BT-13 Group A content-generation entrypoints."""

from services.slides.content_generation.group_a.context_01 import generate_context_01
from services.slides.content_generation.group_a.cover_01 import generate_cover_01
from services.slides.content_generation.group_a.problem_solution_01 import (
    generate_problem_solution_01,
)
from services.slides.content_generation.group_a.requirements_matrix_01 import (
    generate_requirements_matrix_01,
)
from services.slides.content_generation.group_a.scope_01 import generate_scope_01

__all__ = [
    "generate_context_01",
    "generate_cover_01",
    "generate_problem_solution_01",
    "generate_requirements_matrix_01",
    "generate_scope_01",
]
