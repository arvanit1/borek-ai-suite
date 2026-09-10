"""BT-32: provider-egress classification closure. O4 sign-off is still pending."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import yaml

from app.services.data.memory_store import MemoryDataStore
from app.services.gamma_generation import generate_with_egress_policy
from services.gamma.contract import (
    LOCKED_BOREK_TEMPLATE_ID,
    LOCKED_BOREK_TEMPLATE_VERSION,
    GammaContentSlot,
    GammaGenerateRequest,
    GammaPayloadError,
)
from services.gamma.fixture_client import FixtureGammaClient
from services.gamma.live_client import LiveGammaClient
from services.gamma.provider_egress import (
    FORBIDDEN_RAW_EGRESS_ROOTS,
    GAMMA_LIVE_HTTP_KEYS,
    fetchable_client_logo_url,
    gamma_content_egress_inventory,
)
from services.gamma.template import load_gamma_template
from services.security.egress_audit import list_egress_decisions, reset_egress_decisions
from services.security.egress_policy import (
    EgressBlockedError,
    enforce_external_egress,
    load_egress_approval,
    load_field_classifications,
    reset_egress_policy_cache,
    slot_classifications_from_policy,
)

ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = ROOT / "config" / "data_egress_policy.yaml"
OWNED_LOGO = "https://api.borek.test/public/client-logos/acme.png"
SECRET_MARKER = "CONFIDENTIAL-CLIENT-BODY-MUST-NOT-BE-AUDITED"
ACTOR = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


@pytest.fixture(autouse=True)
def _reset_policy_and_audit() -> None:
    reset_egress_decisions()
    reset_egress_policy_cache()
    yield
    reset_egress_decisions()
    reset_egress_policy_cache()


def _policy() -> dict:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def _slots_for(stage: str) -> tuple[GammaContentSlot, ...]:
    return tuple(
        GammaContentSlot(name=slot.name, value=f"{slot.name}:{SECRET_MARKER}")
        for slot in load_gamma_template().slots_for_stage(stage)
    )


def _request(
    *,
    stage_slots: str = "first_contact",
    logo: str | None = None,
    opportunity_id: str | None = None,
    presentation_version_id: str | None = None,
) -> GammaGenerateRequest:
    return GammaGenerateRequest(
        template_id=LOCKED_BOREK_TEMPLATE_ID,
        template_version=LOCKED_BOREK_TEMPLATE_VERSION,
        opportunity_id=opportunity_id or str(uuid.uuid4()),
        presentation_version_id=presentation_version_id or str(uuid.uuid4()),
        output_formats=("pptx",),
        slots=_slots_for(stage_slots),
        client_logo_ref=logo,
        timeout_seconds=30.0,
    )


def _generate(request: GammaGenerateRequest, *, store=None, journey_stage: str, attempt: int = 1):
    names = tuple(slot.name for slot in request.slots)
    return generate_with_egress_policy(
        request,
        provider=FixtureGammaClient(),
        slot_classifications=slot_classifications_from_policy(names),
        store=store,
        actor_id=ACTOR,
        journey_stage=journey_stage,
        attempt=attempt,
    )


def test_o4_approval_is_explicitly_pending() -> None:
    approval = load_egress_approval()
    assert approval["status"] == "pending"
    assert approval["signed_off"] is False
    raw = _policy()
    assert raw["approval"]["status"] == "pending"
    assert raw["approval"]["signed_off"] is False
    assert "approver" not in raw["approval"]
    assert "approved_at" not in raw["approval"]


@pytest.mark.parametrize("stage", ("first_contact", "deepening", "concretisation"))
def test_each_stage_profile_egress_surface_is_classified(stage: str) -> None:
    policy = _policy()
    classifications = policy["field_classifications"]
    allowlist = set(policy["client_confidential_allowlist"]["gamma"])
    profile = load_gamma_template().profile(stage)
    request = _request(stage_slots=stage)
    inventory = gamma_content_egress_inventory(request)

    assert "grounded_facts" not in inventory
    assert "prior_stage_context" not in inventory
    assert set(inventory["slots"]) == {slot.name for slot in load_gamma_template().slots_for_stage(stage)}
    if stage == "first_contact":
        assert profile.client_logo is False
        assert "client_logo_url" not in inventory
        assert "team.body" not in inventory["slots"]
    else:
        assert profile.client_logo is True

    for name in inventory["slots"]:
        path = f"/slots/{name}"
        assert path in classifications, f"{stage}:{path}"
        if classifications[path] == "client_confidential":
            assert path in allowlist, f"{stage}:{path}"

    result = _generate(request, journey_stage=stage)
    assert result.branding_locked is True


def test_client_logo_has_explicit_policy_coverage() -> None:
    policy = _policy()
    assert policy["field_classifications"]["/client_logo_url"] == "client_confidential"
    assert "/client_logo_url" in policy["client_confidential_allowlist"]["gamma"]
    template = load_gamma_template()
    for stage, profile in template.stage_profiles.items():
        if profile.client_logo:
            assert "/client_logo_url" in policy["client_confidential_allowlist"]["gamma"], stage


def test_deepening_owned_logo_send_audits_path_not_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", "https://api.borek.test")
    store = MemoryDataStore()
    request = _request(stage_slots="deepening", logo=OWNED_LOGO)
    result = _generate(request, store=store, journey_stage="deepening")
    assert result.client_logo_applied is True
    row = store.list_egress_audits(presentation_version_id=request.presentation_version_id)[0]
    assert any(item["field"] == "/client_logo_url" for item in row["fields"])
    assert any(
        item["field"] == "/client_logo_url" and item["classification"] == "client_confidential"
        for item in row["fields"]
    )
    dumped = json.dumps(row, default=str)
    assert OWNED_LOGO not in dumped
    assert SECRET_MARKER not in dumped


def test_owned_logo_url_is_classified_and_private_refs_never_enter_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", "https://api.borek.test")
    owned = _request(stage_slots="deepening", logo=OWNED_LOGO)
    assert fetchable_client_logo_url(owned) == OWNED_LOGO
    assert gamma_content_egress_inventory(owned)["client_logo_url"] == OWNED_LOGO

    for banned in (
        f"artifact:logos/{uuid.uuid4()}",
        "s3://borek-client-logos/acme.png",
        "https://evil.example/logo.png",
    ):
        blocked = _request(stage_slots="deepening", logo=banned)
        assert fetchable_client_logo_url(blocked) is None
        assert "client_logo_url" not in gamma_content_egress_inventory(blocked)


def test_empty_owned_prefix_list_still_blocks_logo_egress(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", "")
    request = _request(stage_slots="deepening", logo=OWNED_LOGO)
    assert fetchable_client_logo_url(request) is None
    assert "client_logo_url" not in gamma_content_egress_inventory(request)


def test_live_http_keys_stay_within_the_known_classified_surface() -> None:
    client = LiveGammaClient(api_key="sk-test", theme_id="theme-1", template_id="tpl-1")
    payload = client._generation_payload(_request(stage_slots="first_contact"))
    assert set(payload) <= GAMMA_LIVE_HTTP_KEYS
    assert "grounded_facts" not in payload
    assert "prior_stage_context" not in payload
    assert payload["gammaId"] == "tpl-1"
    assert "prompt" in payload
    assert SECRET_MARKER in payload["prompt"]


def test_non_slot_provider_field_without_policy_fails_closed() -> None:
    with pytest.raises(EgressBlockedError) as raised:
        enforce_external_egress(
            {
                "slots": {"cover.title": "Invoice match"},
                "opportunity_name": "must not leave unclassified",
            },
            provider="gamma",
            stage="gamma_rendering",
        )
    assert raised.value.code == "EGRESS_BLOCKED"
    assert "/opportunity_name" in raised.value.blocked_paths


@pytest.mark.parametrize("raw_key", FORBIDDEN_RAW_EGRESS_ROOTS)
def test_raw_internal_objects_cannot_egress(raw_key: str) -> None:
    with pytest.raises(EgressBlockedError) as raised:
        enforce_external_egress(
            {
                "slots": {"cover.title": "Invoice match"},
                raw_key: {"secret": SECRET_MARKER},
            },
            provider="gamma",
            stage="gamma_rendering",
        )
    assert f"/{raw_key}/secret" in raised.value.blocked_paths
    dumped = json.dumps(list_egress_decisions()[0].to_json_dict())
    assert SECRET_MARKER not in dumped


def test_restricted_field_never_leaves() -> None:
    with pytest.raises(EgressBlockedError) as raised:
        enforce_external_egress(
            {"slots": {"cover.title": "Invoice match"}, "pricing": "EUR 120000"},
            provider="gamma",
            stage="gamma_rendering",
            extra_classifications={"/pricing": "restricted"},
        )
    assert raised.value.code == "EGRESS_BLOCKED"
    assert "/pricing" in raised.value.blocked_paths


def test_unclassified_field_fails_closed() -> None:
    with pytest.raises(EgressBlockedError) as raised:
        enforce_external_egress(
            {"slots": {"cover.title": "Invoice match"}, "novel_field": "no"},
            provider="gamma",
            stage="gamma_rendering",
        )
    assert "/novel_field" in raised.value.blocked_paths
    assert list_egress_decisions()[0].fields[-1].classification == "unclassified"


def test_successful_send_writes_durable_metadata_only_audit() -> None:
    store = MemoryDataStore()
    request = _request(stage_slots="first_contact")
    _generate(request, store=store, journey_stage="first_contact")
    rows = store.list_egress_audits(
        opportunity_id=request.opportunity_id,
        presentation_version_id=request.presentation_version_id,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "gamma"
    assert row["journey_stage"] == "first_contact"
    assert row["pipeline_stage"] == "gamma_rendering"
    assert row["decision"] == "allowed"
    assert row["opportunity_id"] == request.opportunity_id
    assert row["presentation_version_id"] == request.presentation_version_id
    names = {item["field"] for item in row["fields"]}
    assert "/slots/cover.client_name" in names
    assert all(item["decision"] == "allowed" for item in row["fields"])
    assert any(item["classification"] == "client_confidential" for item in row["fields"])
    dumped = json.dumps(row, default=str)
    assert SECRET_MARKER not in dumped
    assert "sk-" not in dumped
    in_memory = list_egress_decisions()
    assert len(in_memory) == 1
    assert in_memory[0].journey_stage == "first_contact"
    at52 = [item for item in store.list_audit_logs(actor_id=ACTOR) if item["action"] == "egress.allowed"]
    assert len(at52) == 1


def test_blocked_send_writes_durable_audit_without_values() -> None:
    store = MemoryDataStore()
    request = _request(stage_slots="first_contact")
    with pytest.raises(EgressBlockedError):
        enforce_external_egress(
            {**gamma_content_egress_inventory(request), "novel_field": SECRET_MARKER},
            provider="gamma",
            stage="gamma_rendering",
            journey_stage="deepening",
            opportunity_id=request.opportunity_id,
            presentation_version_id=request.presentation_version_id,
            store=store,
            actor_id=ACTOR,
        )
    rows = store.list_egress_audits(presentation_version_id=request.presentation_version_id)
    assert len(rows) == 1
    assert rows[0]["decision"] == "blocked"
    assert rows[0]["journey_stage"] == "deepening"
    assert any(item["field"] == "/novel_field" for item in rows[0]["fields"])
    assert SECRET_MARKER not in json.dumps(rows[0], default=str)
    assert any(item["action"] == "egress.blocked" for item in store.list_audit_logs(actor_id=ACTOR))


def test_retry_attempts_are_queryable_on_the_same_version() -> None:
    store = MemoryDataStore()
    request = _request(stage_slots="concretisation")
    _generate(request, store=store, journey_stage="concretisation", attempt=1)
    _generate(request, store=store, journey_stage="concretisation", attempt=2)
    rows = store.list_egress_audits(presentation_version_id=request.presentation_version_id)
    assert [row["attempt"] for row in rows] == [1, 2]
    assert {row["journey_stage"] for row in rows} == {"concretisation"}
    assert {row["opportunity_id"] for row in rows} == {request.opportunity_id}


def test_fixture_and_live_share_the_same_content_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", "https://api.borek.test")
    request = _request(stage_slots="deepening", logo=OWNED_LOGO)
    fixture_inventory = gamma_content_egress_inventory(request)
    live_safe = enforce_external_egress(
        fixture_inventory,
        provider="gamma",
        stage="gamma_rendering",
    )
    assert "client_logo_url" in live_safe
    assert set(live_safe["slots"]) == set(fixture_inventory["slots"])

    class FakeHttp:
        def request(self, *_args, **_kwargs):
            raise AssertionError("blocked path must not reach Gamma HTTP")

        def close(self) -> None:
            return None

    raw = dict(_policy())
    fields = dict(raw.get("field_classifications") or {})
    fields.pop("/client_logo_url", None)
    raw["field_classifications"] = fields
    reset_egress_policy_cache()
    monkeypatch.setattr(
        "services.security.egress_policy._raw_policy",
        lambda: raw,
    )
    client = LiveGammaClient(
        api_key="sk-gamma-test",
        theme_id="theme-1",
        http_client=FakeHttp(),  # type: ignore[arg-type]
    )
    with pytest.raises(GammaPayloadError, match="client_logo_url"):
        client.generate(request)


def test_named_slot_without_classification_is_omitted_from_policy_lookup() -> None:
    classified = slot_classifications_from_policy(("cover.title", "invented.slot"))
    assert classified["cover.title"] == "internal"
    assert "invented.slot" not in classified
    with pytest.raises(EgressBlockedError):
        enforce_external_egress(
            {"slots": {"cover.title": "Invoice match", "invented.slot": "no"}},
            provider="gamma",
            stage="gamma_rendering",
        )


def test_technical_provider_fields_are_internal_not_silently_allowlisted() -> None:
    fields = load_field_classifications()
    for path in (
        "/provider/themeId",
        "/provider/gammaId",
        "/provider/textMode",
        "/provider/format",
        "/provider/exportAs",
    ):
        assert fields[path] == "internal"
    safe = enforce_external_egress(
        {
            "provider": {
                "themeId": "theme-1",
                "textMode": "preserve",
                "format": "presentation",
                "exportAs": "pptx",
            }
        },
        provider="gamma",
        stage="gamma_live",
    )
    assert safe["provider"]["themeId"] == "theme-1"
