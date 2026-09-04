"""Live Gamma HTTP adapter (AT-60). Never logs export URLs."""

from __future__ import annotations

import hashlib
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
)
from services.gamma.fixture_client import validate_generate_request

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
        deadline = time.monotonic() + request.timeout_seconds
        created = self._request(
            "POST",
            self._generation_path(),
            json_body=self._generation_payload(request),
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
            client_logo_applied=request.client_logo_ref is not None,
            artifacts=tuple(artifacts),
        )

    def _filter_external_slots(self, request: GammaGenerateRequest) -> GammaGenerateRequest:
        from services.security.egress_policy import EgressBlockedError, enforce_external_egress

        try:
            safe = enforce_external_egress(
                {"slots": {slot.name: slot.value for slot in request.slots}},
                provider="gamma",
                stage="gamma_live",
            )
        except EgressBlockedError as exc:
            raise GammaPayloadError(str(exc)) from exc
        slots = safe.get("slots") if isinstance(safe, dict) else {}
        if not isinstance(slots, dict):
            raise GammaPayloadError("Gamma payload contains blocked or unclassified fields.")
        return replace(
            request,
            slots=tuple(
                GammaContentSlot(name=name, value=value) for name, value in slots.items()
            ),
        )

    def _generation_path(self) -> str:
        if self._template_id:
            return "/v1.0/generations/from-template"
        return "/v1.0/generations"

    def _generation_payload(self, request: GammaGenerateRequest) -> dict[str, Any]:
        input_text = "\n\n".join(f"{slot.name}: {slot.value}" for slot in request.slots)
        payload: dict[str, Any] = {
            "inputText": input_text,
            "textMode": "preserve",
            "format": "presentation",
            "themeId": self._theme_id,
            "exportAs": request.output_formats[0],
            "cardOptions": {
                "headerFooter": {
                    "bottomLeft": {"type": "image", "source": "themeLogo"},
                }
            },
        }
        if self._template_id:
            payload["gammaId"] = self._template_id
        title = next((slot.value for slot in request.slots if slot.name == "cover.title"), None)
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
            json_body={"format": output_format},
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
        raise GammaPayloadError("Gamma rejected the generation payload.")
    raise GammaProviderError("Gamma provider failed.")


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
