"""MS-30 deterministic demo pack installation."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import struct
import zlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid5

import httpx

from services.borek_rag.corpus import corpus_from_mapping
from services.borek_rag.identity import demo_corpus_id, demo_provenance_marker

_ROOT = Path(__file__).resolve().parents[5]
_MANIFEST_PATH = _ROOT / "packages" / "contracts" / "fixtures" / "demo_data" / "ms30_demo_pack.json"
_FRAMEWORK_PATH = _ROOT / "packages" / "contracts" / "fixtures" / "framework_object.minimal.json"
_PLAN_PATH = _ROOT / "packages" / "contracts" / "fixtures" / "presentation_plan.minimal.json"
_COVER_PATH = (
    _ROOT / "packages" / "contracts" / "fixtures" / "slide_spec" / "group_a" / "cover_01.minimal.json"
)
_PPTX_PATH = _ROOT / "tests" / "fixtures" / "renderer" / "minimal.pptx"
_NAMESPACE = UUID("715f8414-45af-4f85-8fb2-ef8c98aba8ab")
_STAMP = "2026-09-09T12:00:00+00:00"


class DemoDataError(RuntimeError):
    pass


class DemoRecordStore(Protocol):
    def upsert(self, table: str, row: dict[str, Any]) -> None: ...

    def put_logo(self, storage_path: str, content: bytes, content_type: str) -> None: ...


@dataclass(frozen=True)
class DemoInstallResult:
    user_id: UUID
    rich_opportunity_id: UUID
    bare_opportunity_id: UUID
    presentation_version_ids: tuple[UUID, ...]
    corpus_version_id: UUID
    record_counts: dict[str, int]
    artifact_hashes: dict[str, str]


def load_demo_manifest() -> dict[str, Any]:
    raw = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise DemoDataError("MS-30 manifest must be a JSON object")
    if raw.get("demo_marker") != demo_provenance_marker():
        raise DemoDataError("MS-30 manifest does not use the frozen demo marker")
    corpus = raw.get("corpus")
    if not isinstance(corpus, dict) or corpus.get("corpus_id") != demo_corpus_id():
        raise DemoDataError("MS-30 manifest does not use the frozen demo corpus id")
    if corpus.get("provenance_marker") != demo_provenance_marker():
        raise DemoDataError("MS-30 corpus does not use the frozen provenance marker")
    corpus_from_mapping(corpus)
    stages = [stage.get("id") for stage in raw.get("stages", []) if isinstance(stage, dict)]
    if stages != ["first_contact", "deepening", "concretisation"]:
        raise DemoDataError("MS-30 stages must be cumulative and ordered")
    return raw


def _id(user_id: UUID, key: str) -> UUID:
    return uuid5(_NAMESPACE, f"{user_id}:ms30:{key}")


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def demo_logo_png() -> bytes:
    width = height = 64
    scanline = b"\x00" + (b"\x12\x2b\x4f\xff" * width)
    pixels = scanline * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(pixels, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _preview_png(stage_label: str) -> bytes:
    width, height = 320, 180
    colors = {
        "First contact": (18, 43, 79, 255),
        "Deepening": (31, 111, 120, 255),
        "Concretisation": (184, 111, 45, 255),
    }
    color = colors[stage_label]
    scanline = b"\x00" + bytes(color) * width
    pixels = scanline * height
    label = f"DEMO DATA - {stage_label}".encode("ascii")
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"tEXt", b"Title\x00" + label)
        + _png_chunk(b"IDAT", zlib.compress(pixels, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _pptx_bytes(stage_label: str) -> bytes:
    replacement = f"DEMO DATA - {stage_label}".encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(_PPTX_PATH, "r") as source, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as target:
        for name in sorted(source.namelist()):
            content = source.read(name).replace(b"AT-9 fixture slide", replacement)
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 9, 12, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            target.writestr(info, content)
    return output.getvalue()


def _pdf_bytes(stage_label: str) -> bytes:
    safe = stage_label.replace("(", "[").replace(")", "]")
    stream = f"BT /F1 18 Tf 72 720 Td (DEMO DATA - {safe}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    body.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    return bytes(body)


def _writable_path(path: Path) -> Path:
    resolved = path.resolve()
    text = str(resolved)
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return Path("\\\\?\\" + text)
    return resolved


def _write_if_changed(path: Path, content: bytes) -> None:
    if path.is_file() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_assets(
    *,
    artifact_root: Path,
    opportunity_id: UUID,
    presentation_ids: dict[str, UUID],
    version_ids: dict[str, UUID],
    stages: list[dict[str, str]],
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    if not _PPTX_PATH.is_file():
        raise DemoDataError(f"Fixture PPTX is missing: {_PPTX_PATH}")
    paths: dict[str, dict[str, str]] = {}
    hashes: dict[str, str] = {}
    for stage in stages:
        stage_id = stage["id"]
        version_id = version_ids[stage_id]
        output = _writable_path(artifact_root / str(version_id))
        output.mkdir(parents=True, exist_ok=True)
        pptx = output / "deck.pptx"
        pdf = output / "deck.pdf"
        preview = output / "slide-001.png"
        pptx_content = _pptx_bytes(stage["label"])
        pdf_content = _pdf_bytes(stage["label"])
        preview_content = _preview_png(stage["label"])
        _write_if_changed(pptx, pptx_content)
        _write_if_changed(pdf, pdf_content)
        _write_if_changed(preview, preview_content)
        enterprise = _writable_path(
            artifact_root
            / "enterprise"
            / "opportunities"
            / str(opportunity_id)
            / "presentations"
            / str(presentation_ids[stage_id])
            / "versions"
            / str(version_id)
        )
        enterprise.mkdir(parents=True, exist_ok=True)
        _write_if_changed(enterprise / "pptx.pptx", pptx_content)
        _write_if_changed(enterprise / "pdf.pdf", pdf_content)
        paths[stage_id] = {
            "pptx": str(pptx.resolve()),
            "pdf": str(pdf.resolve()),
            "preview": str(preview.resolve()),
        }
        hashes[f"{stage_id}.pptx"] = hashlib.sha256(pptx.read_bytes()).hexdigest()
        hashes[f"{stage_id}.pdf"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    return paths, hashes


def _framework_fixture(opportunity_id: UUID, stage_label: str, user_id: UUID) -> dict[str, Any]:
    framework = json.loads(_FRAMEWORK_PATH.read_text(encoding="utf-8"))
    framework.update(
        {
            "opportunity_id": str(opportunity_id),
            "title": f"DEMO DATA - {stage_label}",
            "status": "confirmed",
            "confirmed_by": str(user_id),
            "confirmed_at": _STAMP,
            "updated_at": _STAMP,
        }
    )
    return framework


def _plan_fixture(stage_label: str) -> dict[str, Any]:
    plan = json.loads(_PLAN_PATH.read_text(encoding="utf-8"))
    plan["title"] = f"DEMO DATA - {stage_label}"
    return plan


def _slide_fixture(stage_label: str) -> dict[str, Any]:
    slide = json.loads(_COVER_PATH.read_text(encoding="utf-8"))
    slide["title"] = f"DEMO DATA - {stage_label}"
    slide["subtitle"] = "Fictional fixture output"
    slide["statBadges"] = [{"value": "Demo", "label": "Not customer or commercial data"}]
    return slide


def install_demo_data(
    *,
    user_id: UUID,
    store: DemoRecordStore,
    artifact_root: Path,
    manifest: dict[str, Any] | None = None,
) -> DemoInstallResult:
    data = copy.deepcopy(manifest or load_demo_manifest())
    marker = data["demo_marker"]
    stages: list[dict[str, str]] = data["stages"]
    rich_opportunity_id = _id(user_id, "opportunity:rich")
    bare_opportunity_id = _id(user_id, "opportunity:bare")
    framework_ids = {stage["id"]: _id(user_id, f"framework:{stage['id']}") for stage in stages}
    plan_ids = {stage["id"]: _id(user_id, f"plan:{stage['id']}") for stage in stages}
    presentation_ids = {stage["id"]: _id(user_id, f"presentation:{stage['id']}") for stage in stages}
    version_ids = {stage["id"]: _id(user_id, f"version:{stage['id']}") for stage in stages}
    slide_ids = {stage["id"]: _id(user_id, f"slide:{stage['id']}") for stage in stages}
    corpus_version_id = _id(user_id, "corpus:ms30.1")
    logo = demo_logo_png()
    logo_path = f"{rich_opportunity_id}/demo-logo.png"
    assets, artifact_hashes = _write_assets(
        artifact_root=artifact_root,
        opportunity_id=rich_opportunity_id,
        presentation_ids=presentation_ids,
        version_ids=version_ids,
        stages=stages,
    )

    counts: dict[str, int] = {}

    def upsert(table: str, row: dict[str, Any]) -> None:
        store.upsert(table, row)
        counts[table] = counts.get(table, 0) + 1

    client = data["client"]
    bare = data["bare_client"]
    for opportunity_id, values, client_pack in (
        (rich_opportunity_id, client, data["rich_client_pack"]),
        (bare_opportunity_id, bare, None),
    ):
        upsert(
            "opportunities",
            {
                "id": str(opportunity_id),
                "client_name": values["name"],
                "opportunity_name": values["opportunity"],
                "department": values["department"],
                "language": values["language"],
                "status": "active",
                "pii_redaction_enabled": True,
                "additional_client_information": client_pack,
                "created_by": str(user_id),
                "demo_marker": marker,
                "created_at": _STAMP,
                "updated_at": _STAMP,
            },
        )

    store.put_logo(logo_path, logo, "image/png")
    upsert(
        "opportunity_client_logos",
        {
            "id": str(_id(user_id, "logo:rich")),
            "opportunity_id": str(rich_opportunity_id),
            "created_by": str(user_id),
            "file_name": "demo-logo.png",
            "mime_type": "image/png",
            "size_bytes": len(logo),
            "width_px": 64,
            "height_px": 64,
            "storage_path": logo_path,
            "demo_marker": marker,
            "uploaded_at": _STAMP,
        },
    )

    previous_version_id: UUID | None = None
    corpus_ref = f"{data['corpus']['corpus_id']}@{data['corpus']['corpus_version']}"
    for stage in stages:
        stage_id = stage["id"]
        framework_id = framework_ids[stage_id]
        plan_id = plan_ids[stage_id]
        presentation_id = presentation_ids[stage_id]
        version_id = version_ids[stage_id]
        slide = _slide_fixture(stage["label"])
        upsert(
            "framework_versions",
            {
                "id": str(framework_id),
                "opportunity_id": str(rich_opportunity_id),
                "version_number": stages.index(stage) + 1,
                "status": "confirmed",
                "framework_json": _framework_fixture(rich_opportunity_id, stage["label"], user_id),
                "created_by": str(user_id),
                "demo_marker": marker,
                "created_at": _STAMP,
            },
        )
        upsert(
            "presentation_plans",
            {
                "id": str(plan_id),
                "framework_version_id": str(framework_id),
                "plan_json": _plan_fixture(stage["label"]),
                "demo_marker": marker,
                "created_at": _STAMP,
            },
        )
        upsert(
            "presentations",
            {
                "id": str(presentation_id),
                "presentation_plan_id": str(plan_id),
                "name": f"DEMO DATA - {stage['label']}",
                "status": "ready",
                "demo_marker": marker,
                "created_at": _STAMP,
            },
        )
        upsert(
            "presentation_versions",
            {
                "id": str(version_id),
                "presentation_id": str(presentation_id),
                "version_number": 1,
                "slides_json": [slide],
                "pptx_storage_path": assets[stage_id]["pptx"],
                "pdf_storage_path": assets[stage_id]["pdf"],
                "status": "ready",
                "journey_stage": stage_id,
                "prior_stage_presentation_version_id": str(previous_version_id) if previous_version_id else None,
                "demo_marker": marker,
                "created_at": _STAMP,
            },
        )
        upsert(
            "slides",
            {
                "id": str(slide_ids[stage_id]),
                "presentation_version_id": str(version_id),
                "slide_index": 0,
                "layout_id": slide["layoutId"],
                "slide_spec": slide,
                "source_chapter_ids": slide["sourceChapterIds"],
                "demo_marker": marker,
                "created_at": _STAMP,
            },
        )
        for kind, content_type, suffix in (
            ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"),
            ("pdf", "application/pdf", "pdf"),
        ):
            destination = (
                f"opportunities/{rich_opportunity_id}/presentations/{presentation_id}/"
                f"versions/{version_id}/{kind}.{suffix}"
            )
            key = hashlib.sha256(f"{version_id}:{kind}:fixture".encode("utf-8")).hexdigest()
            upsert(
                "filed_artifacts",
                {
                    "id": str(_id(user_id, f"filed:{stage_id}:{kind}")),
                    "idempotency_key": key,
                    "opportunity_id": str(rich_opportunity_id),
                    "presentation_id": str(presentation_id),
                    "presentation_version_id": str(version_id),
                    "framework_version_id": str(framework_id),
                    "artifact_kind": kind,
                    "content_type": content_type,
                    "provider": "fixture",
                    "destination_path": destination,
                    "repository_ref": f"fixture://enterprise/{destination}",
                    "status": "filed",
                    "approved_by": str(user_id),
                    "approved_at": _STAMP,
                    "corpus_versions": [corpus_ref],
                    "filed_at": _STAMP,
                    "created_at": _STAMP,
                    "updated_at": _STAMP,
                    "demo_marker": marker,
                },
            )
        previous_version_id = version_id

    corpus = data["corpus"]
    upsert(
        "knowledge_corpus_versions",
        {
            "id": str(corpus_version_id),
            "corpus_key": corpus["corpus_id"],
            "version": corpus["corpus_version"],
            "status": "approved",
            "owner": corpus["owner"],
            "owner_user_id": str(user_id),
            "demo_marker": marker,
            "created_at": _STAMP,
            "approved_at": _STAMP,
        },
    )
    for document in corpus["documents"]:
        document_id = _id(user_id, f"document:{document['document_id']}")
        upsert(
            "knowledge_documents",
            {
                "id": str(document_id),
                "corpus_version_id": str(corpus_version_id),
                "document_key": document["document_id"],
                "document_type": document["document_type"],
                "source_uri": f"fixture://ms30/{document['document_id']}",
                "source_version": document["version"],
                "classification": document["classification"],
                "effective_from": document["effective_from"],
                "effective_to": document["effective_to"],
                "demo_marker": marker,
                "created_at": _STAMP,
            },
        )
        for fact in document["facts"]:
            upsert(
                "knowledge_facts",
                {
                    "id": str(_id(user_id, f"fact:{fact['fact_id']}")),
                    "document_id": str(document_id),
                    "fact_key": fact["fact_id"],
                    "kind": fact["kind"],
                    "service_key": fact["service_key"],
                    "query_key": fact["query_key"],
                    "statement": fact["statement"],
                    "payload": fact["payload"],
                    "search_terms": [*fact["required_terms"], *fact.get("optional_terms", [])],
                    "demo_marker": marker,
                    "created_at": _STAMP,
                },
            )

    return DemoInstallResult(
        user_id=user_id,
        rich_opportunity_id=rich_opportunity_id,
        bare_opportunity_id=bare_opportunity_id,
        presentation_version_ids=tuple(version_ids[stage["id"]] for stage in stages),
        corpus_version_id=corpus_version_id,
        record_counts=counts,
        artifact_hashes=artifact_hashes,
    )


class MemoryDemoRecordStore:
    def __init__(self) -> None:
        self.tables: dict[str, dict[str, dict[str, Any]]] = {}
        self.logos: dict[str, bytes] = {}

    def upsert(self, table: str, row: dict[str, Any]) -> None:
        self.tables.setdefault(table, {})[str(row["id"])] = copy.deepcopy(row)

    def put_logo(self, storage_path: str, content: bytes, content_type: str) -> None:
        if content_type != "image/png":
            raise DemoDataError("MS-30 demo logo must be PNG")
        self.logos[storage_path] = bytes(content)


class SupabaseDemoRecordStore:
    """Privileged installer; records remain scoped to the verified calling user."""

    def __init__(self, *, base_url: str, service_role_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_role_key = service_role_key
        self.client = httpx.Client(timeout=30.0)

    def _headers(self, *, content_type: str = "application/json") -> dict[str, str]:
        headers = {"apikey": self.service_role_key, "Content-Type": content_type}
        if not self.service_role_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.service_role_key}"
        return headers

    def upsert(self, table: str, row: dict[str, Any]) -> None:
        response = self.client.post(
            f"{self.base_url}/rest/v1/{table}",
            params={"on_conflict": "id"},
            headers={**self._headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=row,
        )
        if response.status_code not in {200, 201, 204}:
            raise DemoDataError(f"Could not seed {table}: HTTP {response.status_code} {response.text}")

    def put_logo(self, storage_path: str, content: bytes, content_type: str) -> None:
        existing = self.client.get(
            f"{self.base_url}/storage/v1/object/client-logos/{storage_path}",
            headers=self._headers(content_type=content_type),
        )
        if existing.status_code == 200 and existing.content == content:
            return
        if existing.status_code not in {200, 400, 404}:
            raise DemoDataError(
                f"Could not inspect demo logo: HTTP {existing.status_code} {existing.text}"
            )
        response = self.client.post(
            f"{self.base_url}/storage/v1/object/client-logos/{storage_path}",
            headers={**self._headers(content_type=content_type), "x-upsert": "true"},
            content=content,
        )
        if response.status_code not in {200, 201}:
            raise DemoDataError(f"Could not seed demo logo: HTTP {response.status_code} {response.text}")
