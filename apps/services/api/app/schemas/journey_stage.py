"""BT-31 journey-stage eligibility contract for MS-31."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

JOURNEY_STAGES = ("first_contact", "deepening", "concretisation")
JourneyStageName = Literal["first_contact", "deepening", "concretisation"]
PrerequisiteStageName = Literal["first_contact", "deepening"]
EligibilityReason = Literal[
    "NO_COMPLETED_PREREQUISITE",
    "PREREQUISITE_INCOMPLETE",
    "PREREQUISITE_SUPERSEDED",
    "PRIOR_FRAMEWORK_UNAVAILABLE",
    "JOURNEY_STAGE_UNKNOWN",
]
EligibilityNextAction = Literal[
    "complete_first_contact",
    "complete_deepening",
    "regenerate_prior_stage",
    "select_journey_stage",
]


class StageEligibility(BaseModel):
    journey_stage: JourneyStageName
    startable: bool
    prerequisite_stage: PrerequisiteStageName | None = None
    prior_stage_presentation_version_id: UUID | None = None
    reason: EligibilityReason | None = None
    next_action: EligibilityNextAction | None = None


class JourneyStageEligibilityResponse(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    opportunity_id: UUID
    requested_journey_stage: JourneyStageName | None = None
    startable: bool
    prerequisite_stage: PrerequisiteStageName | None = None
    prior_stage_presentation_version_id: UUID | None = None
    reason: EligibilityReason | None = None
    next_action: EligibilityNextAction | None = None
    stages: list[StageEligibility] = Field(min_length=3, max_length=3)
