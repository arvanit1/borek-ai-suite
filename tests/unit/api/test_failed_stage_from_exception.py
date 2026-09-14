"""Map classified failures to the pipeline stage that actually failed."""

from __future__ import annotations

from app.schemas.jobs import JobStage
from app.services.api_errors import failed_stage_from_exception
from services.gamma.contract import GammaAuthError, GammaTimeoutError


def test_gamma_timeout_maps_to_gamma_rendering_stage() -> None:
    assert failed_stage_from_exception(GammaTimeoutError()) == JobStage.GAMMA_RENDERING


def test_gamma_auth_maps_to_gamma_rendering_stage() -> None:
    assert failed_stage_from_exception(GammaAuthError()) == JobStage.GAMMA_RENDERING


def test_pre_generation_errors_default_to_slide_generating() -> None:
    class PlanError(Exception):
        code = "PRESENTATION_PLAN_NOT_GENERATABLE"

    assert failed_stage_from_exception(PlanError("bad plan")) == JobStage.SLIDE_GENERATING
