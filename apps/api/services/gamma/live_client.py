"""Live Gamma HTTP adapter (AT-60). Never logs export URLs."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import replace
from typing import Any

import httpx

from services.gamma.contract import (
    GammaArtifact,
    GammaAuthError,
    GammaContentSlot,
    GammaError,
    GammaGenerateRequest,
    GammaGenerateResult,
    GammaPayloadError,
    GammaProviderError,
    GammaRateLimitError,
    GammaTemplateError,
    GammaTimeoutError,
    gamma_egress_reference,
)
from services.gamma.fixture_client import validate_generate_request
from services.gamma.input_text import (
    CARD_SPLIT_INPUT_TEXT_BREAKS,
    align_slots_with_planned_slides,
    build_scratch_input_text,
)
from services.gamma.provider_egress import gamma_live_egress_inventory
from services.gamma.signed_logo import owned_https_prefixes
from services.gamma.template import load_gamma_template

_CONTENT_TYPES = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
}
_POLL_INTERVAL_SECONDS = 2.0


class LiveGammaClient:
    """Calls public-api.gamma.app. Fail-closed without a key."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://public-api.gamma.app",
        theme_id: str,
        template_id: str = "",
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._theme_id = theme_id.strip()
        self._template_id = template_id.strip()
        self._http = http_client

    def generate(self, request: GammaGenerateRequest) -> GammaGenerateResult:
        validate_generate_request(request)
        if not self._api_key:
            raise GammaAuthError("Gamma credentials are missing or rejected.")
        if not self._theme_id:
            raise GammaTemplateError("GAMMA_THEME_ID is required for live generation.")

        request = self._filter_external_slots(request)
        outbound_payload = self._generation_payload(request)
        deadline = time.monotonic() + request.timeout_seconds
        created = self._request(
            "POST",
            self._generation_path(request),
            json_body=outbound_payload,
            deadline=deadline,
        )
        generation_id = str(created.get("generationId") or created.get("generation_id") or "")
        if not generation_id:
            raise GammaProviderError("Gamma did not return a generationId.")

        completed = self._poll_generation(generation_id, deadline=deadline)
        gamma_id = str(completed.get("gammaId") or completed.get("gamma_id") or "")
        artifacts = []
        for index, output_format in enumerate(request.output_formats):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GammaTimeoutError()
            if index == 0:
                export_url = str(completed.get("exportUrl") or completed.get("export_url") or "")
                if not export_url:
                    export_url = self._export_gamma(gamma_id, output_format, deadline=deadline)
            else:
                export_url = self._export_gamma(gamma_id, output_format, deadline=deadline)
            content = self._download_export(export_url, deadline=deadline)
            artifacts.append(
                _owned_artifact(request, output_format=output_format, generation_id=generation_id, content=content)
            )

        return GammaGenerateResult(
            generation_id=generation_id,
            template_id=request.template_id,
            template_version=request.template_version,
            branding_locked=True,
            client_logo_applied=client_logo_sent_in_outbound_payload(outbound_payload),
            artifacts=tuple(artifacts),
        )

    def _filter_external_slots(self, request: GammaGenerateRequest) -> GammaGenerateRequest:
        from services.security.egress_policy import EgressBlockedError, enforce_external_egress

        try:
            safe = enforce_external_egress(
                gamma_live_egress_inventory(
                    request,
                    theme_id=self._theme_id,
                    template_id=self._template_id,
                ),
                provider="gamma",
                stage="gamma_live",
            )
        except EgressBlockedError as exc:
            raise GammaPayloadError(str(exc)) from exc
        slots = safe.get("slots") if isinstance(safe, dict) else {}
        if not isinstance(slots, dict):
            raise GammaPayloadError("Gamma payload contains blocked or unclassified fields.")
        logo_allowed = isinstance(safe, dict) and "client_logo_url" in safe
        return replace(
            request,
            slots=tuple(
                GammaContentSlot(name=name, value=value) for name, value in slots.items()
            ),
            client_logo_ref=request.client_logo_ref if logo_allowed else None,
            client_logo_placement=request.client_logo_placement if logo_allowed else None,
        )

    def _generation_path(self, request: GammaGenerateRequest) -> str:
        if self._template_id and not uses_scratch_generation(request):
            return "/v1.0/generations/from-template"
        return "/v1.0/generations"

    def _generation_payload(self, request: GammaGenerateRequest) -> dict[str, Any]:
        template = load_gamma_template()
        ordered_slots = align_slots_with_planned_slides(
            request.slots,
            request.planned_slide_specs,
            template=template,
        )
        title = next((slot.value for slot in ordered_slots if slot.name == "cover.title"), None)
        if self._template_id and not uses_scratch_generation(request):
            input_text = "\n\n".join(f"{slot.name}: {slot.value}" for slot in ordered_slots)
            # POST /v1.0/generations/from-template requires prompt + gammaId.
            # cardOptions/headerFooter are not documented on this endpoint.
            payload: dict[str, Any] = {
                "prompt": input_text,
                "gammaId": self._template_id,
                "themeId": self._theme_id,
                "exportAs": request.output_formats[0],
            }
            if title:
                payload["title"] = title
            return payload

        header_footer: dict[str, Any] = {
            "bottomLeft": {"type": "image", "source": "themeLogo"},
        }
        client_logo_url = _fetchable_client_logo_url(request)
        if client_logo_url is not None:
            placement = request.client_logo_placement or load_gamma_template().client_logo
            header_footer["bottomRight"] = _custom_header_footer_image(
                src=client_logo_url,
                max_height_pct=placement.max_height_pct,
            )
        input_text, num_cards = build_scratch_input_text(
            ordered_slots,
            template=template,
            planned_slide_specs=request.planned_slide_specs,
        )
        payload = {
            "inputText": input_text,
            "textMode": "preserve",
            "format": "presentation",
            "themeId": self._theme_id,
            "exportAs": request.output_formats[0],
            "cardSplit": CARD_SPLIT_INPUT_TEXT_BREAKS,
            "numCards": num_cards,
            "cardOptions": {"headerFooter": header_footer},
        }
        if title:
            payload["title"] = title
        return payload

    def _poll_generation(self, generation_id: str, *, deadline: float) -> dict[str, Any]:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GammaTimeoutError()
            payload = self._request(
                "GET",
                f"/v1.0/generations/{generation_id}",
                deadline=deadline,
            )
            status = str(payload.get("status") or "").lower()
            if status == "completed":
                return payload
            if status == "failed":
                raise GammaProviderError("Gamma generation failed.")
            time.sleep(min(_POLL_INTERVAL_SECONDS, max(remaining, 0.1)))

    def _export_gamma(self, gamma_id: str, output_format: str, *, deadline: float) -> str:
        if not gamma_id:
            raise GammaProviderError("Gamma generation completed without a gammaId.")
        created = self._request(
            "POST",
            f"/v1.0/gammas/{gamma_id}/export",
            json_body={"exportAs": output_format},
            deadline=deadline,
        )
        export_id = str(created.get("exportId") or created.get("id") or "")
        if not export_id:
            raise GammaProviderError("Gamma export did not return an exportId.")
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GammaTimeoutError()
            payload = self._request(
                "GET",
                f"/v1.0/exports/{export_id}",
                deadline=deadline,
            )
            status = str(payload.get("status") or "").lower()
            if status == "completed":
                export_url = str(payload.get("exportUrl") or payload.get("export_url") or "")
                if not export_url:
                    raise GammaProviderError("Gamma export completed without an export URL.")
                return export_url
            if status == "failed":
                raise GammaProviderError("Gamma export failed.")
            time.sleep(min(_POLL_INTERVAL_SECONDS, max(remaining, 0.1)))

    def _download_export(self, export_url: str, *, deadline: float) -> bytes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise GammaTimeoutError()
        client = self._http or httpx.Client(timeout=remaining)
        try:
            response = client.get(export_url, timeout=remaining)
        except httpx.TimeoutException as exc:
            raise GammaTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise GammaProviderError("Gamma export download failed.") from exc
        finally:
            if self._http is None:
                client.close()
        if response.status_code >= 400:
            raise GammaProviderError("Gamma export download failed.")
        if not response.content:
            raise GammaProviderError("Gamma export was empty.")
        return response.content

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        deadline: float,
    ) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise GammaTimeoutError()
        headers = {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}{path}"
        client = self._http or httpx.Client(timeout=remaining)
        try:
            response = client.request(method, url, headers=headers, json=json_body, timeout=remaining)
        except httpx.TimeoutException as exc:
            raise GammaTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise GammaProviderError("Gamma provider failed.") from exc
        finally:
            if self._http is None:
                client.close()
        raise_for_gamma_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise GammaProviderError("Gamma returned a non-object payload.")
        return payload


def uses_scratch_generation(request: GammaGenerateRequest) -> bool:
    """Use /generations when a fetchable client logo must ride in cardOptions."""
    return _fetchable_client_logo_url(request) is not None


def client_logo_sent_in_outbound_payload(payload: dict[str, Any]) -> bool:
    """True only when the outbound Gamma HTTP JSON requests a custom footer image."""
    card_options = payload.get("cardOptions")
    if not isinstance(card_options, dict):
        return False
    header_footer = card_options.get("headerFooter")
    if not isinstance(header_footer, dict):
        return False
    bottom_right = header_footer.get("bottomRight")
    if not isinstance(bottom_right, dict):
        return False
    return (
        bottom_right.get("type") == "image"
        and bottom_right.get("source") == "custom"
        and isinstance(bottom_right.get("src"), str)
        and bool(bottom_right["src"].strip())
    )


def _fetchable_client_logo_url(request: GammaGenerateRequest) -> str | None:
    """Use this module's owned_https_prefixes so existing tests can patch it."""
    return gamma_egress_reference(
        request.client_logo_ref,
        owned_https_prefixes=owned_https_prefixes(),
    )


def raise_for_gamma_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    if response.status_code in {401, 403}:
        raise GammaAuthError("Gamma credentials are missing or rejected.")
    if response.status_code == 429:
        raise GammaRateLimitError("Gamma rate-limited the request.")
    if response.status_code == 404:
        raise GammaTemplateError("The locked Gamma theme or template was not found.")
    if response.status_code in {400, 409, 422}:
        detail = _sanitize_gamma_provider_message(response)
        raise GammaPayloadError(
            detail or "Gamma rejected the generation payload."
        )
    raise GammaProviderError("Gamma provider failed.")


def _custom_header_footer_image(*, src: str, max_height_pct: float) -> dict[str, Any]:
    """Map JJ-27 placement semantics onto Gamma's header/footer image schema."""
    return {
        "type": "image",
        "source": "custom",
        "src": src,
        "size": _gamma_image_size_for_max_height_pct(max_height_pct),
    }


def _gamma_image_size_for_max_height_pct(max_height_pct: float) -> str:
    if max_height_pct <= 6.0:
        return "sm"
    if max_height_pct <= 10.0:
        return "md"
    if max_height_pct <= 14.0:
        return "lg"
    return "xl"


def _sanitize_gamma_provider_message(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        return None
    return _redact_sensitive_urls(message.strip())


def _redact_sensitive_urls(text: str) -> str:
    return re.sub(r"https?://\S+", "[redacted-url]", text)


def _owned_artifact(
    request: GammaGenerateRequest,
    *,
    output_format: str,
    generation_id: str,
    content: bytes,
) -> GammaArtifact:
    storage_key = (
        f"gamma/{request.opportunity_id}/{request.presentation_version_id}/"
        f"{generation_id}.{output_format}"
    )
    return GammaArtifact(
        format=output_format,  # type: ignore[arg-type]
        artifact_id=f"{generation_id}:{output_format}",
        content_type=_CONTENT_TYPES[output_format],
        byte_size=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        storage_key=storage_key,
        owner_opportunity_id=request.opportunity_id,
        owner_presentation_version_id=request.presentation_version_id,
        content=content,
    )


def classify_gamma_exception(exc: BaseException) -> GammaError:
    if isinstance(exc, GammaError):
        return exc
    return GammaProviderError(str(exc) or "Gamma provider failed.")
