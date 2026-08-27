"""MS-6..MS-10 Group C content-generation entrypoints."""

from services.slides.content_generation.group_c.architecture_01 import (
    generate_architecture_01,
)
from services.slides.content_generation.group_c.compliance_01 import generate_compliance_01
from services.slides.content_generation.group_c.next_steps_01 import generate_next_steps_01
from services.slides.content_generation.group_c.open_questions_01 import (
    generate_open_questions_01,
)
from services.slides.content_generation.group_c.success_metrics_01 import (
    generate_success_metrics_01,
)

__all__ = [
    "generate_architecture_01",
    "generate_compliance_01",
    "generate_next_steps_01",
    "generate_open_questions_01",
    "generate_success_metrics_01",
]
