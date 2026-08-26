"""JJ-5..JJ-8 Group B content-generation entrypoints."""

from services.slides.content_generation.group_b.milestones_01 import generate_milestones_01
from services.slides.content_generation.group_b.process_flow_01 import (
    generate_process_flow_01,
)
from services.slides.content_generation.group_b.team_fte_01 import generate_team_fte_01
from services.slides.content_generation.group_b.timeline_01 import generate_timeline_01

__all__ = [
    "generate_milestones_01",
    "generate_process_flow_01",
    "generate_team_fte_01",
    "generate_timeline_01",
]
