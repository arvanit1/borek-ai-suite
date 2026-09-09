from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path
from uuid import UUID

from services.borek_rag.corpus import corpus_from_mapping
from services.borek_rag.models import RetrievalQuery
from services.borek_rag.retriever import retrieve

from app.services.demo_data import (
    MemoryDemoRecordStore,
    demo_logo_png,
    install_demo_data,
    load_demo_manifest,
)

ROOT = Path(__file__).resolve().parents[3]
USER_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
USER_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def _snapshot(store: MemoryDemoRecordStore) -> str:
    return json.dumps(store.tables, sort_keys=True, separators=(",", ":"))


def test_manifest_uses_frozen_demo_identity_and_valid_retrieval_examples() -> None:
    manifest = load_demo_manifest()
    corpus = corpus_from_mapping(manifest["corpus"])
    examples = manifest["retrieval_examples"]

    hit = retrieve(RetrievalQuery(text=examples["hit"], allow_demo=True), corpus=corpus)
    miss = retrieve(RetrievalQuery(text=examples["miss"], allow_demo=True), corpus=corpus)
    ambiguous = retrieve(
        RetrievalQuery(text=examples["ambiguous"], allow_demo=True),
        corpus=corpus,
    )
    blocked = retrieve(RetrievalQuery(text=examples["hit"]), corpus=corpus)

    assert manifest["demo_marker"] == "demo"
    assert corpus.corpus_id == "borek-demo"
    assert hit.status == "answered"
    assert hit.sources[0].provenance_marker == "demo"
    assert hit.payload is not None and hit.payload["demo"] is True
    assert hit.payload["commercially_approved"] is False
    assert "DEMO ONLY" in (hit.statement or "")
    assert miss.reason == "no_supported_fact"
    assert ambiguous.reason == "ambiguous_facts"
    assert blocked.reason == "no_supported_fact"


def test_seed_is_idempotent_complete_and_owner_scoped(tmp_path: Path) -> None:
    store = MemoryDemoRecordStore()
    first = install_demo_data(user_id=USER_A, store=store, artifact_root=tmp_path)
    before = _snapshot(store)
    first_hashes = copy.deepcopy(first.artifact_hashes)
    versions_before = [
        store.tables["presentation_versions"][str(item)] for item in first.presentation_version_ids
    ]
    mtimes_before = {
        path: Path(row[path]).stat().st_mtime_ns
        for row in versions_before
        for path in ("pptx_storage_path", "pdf_storage_path")
    }
    second = install_demo_data(user_id=USER_A, store=store, artifact_root=tmp_path)

    assert first == second
    assert before == _snapshot(store)
    assert first.record_counts == {
        "opportunities": 2,
        "opportunity_client_logos": 1,
        "framework_versions": 3,
        "presentation_plans": 3,
        "presentations": 3,
        "presentation_versions": 3,
        "slides": 3,
        "filed_artifacts": 6,
        "knowledge_corpus_versions": 1,
        "knowledge_documents": 3,
        "knowledge_facts": 3,
    }
    assert sum(first.record_counts.values()) == 31
    assert len(store.logos) == 1
    assert demo_logo_png().startswith(b"\x89PNG\r\n\x1a\n")
    assert all(
        row["demo_marker"] == "demo"
        for rows in store.tables.values()
        for row in rows.values()
    )

    opportunities = list(store.tables["opportunities"].values())
    rich = next(row for row in opportunities if row["id"] == str(first.rich_opportunity_id))
    bare = next(row for row in opportunities if row["id"] == str(first.bare_opportunity_id))
    assert set(rich["additional_client_information"]) == {
        "location_requirements",
        "constraints",
        "contacts",
        "priorities",
        "notes",
    }
    assert bare["additional_client_information"] is None

    versions = [store.tables["presentation_versions"][str(item)] for item in first.presentation_version_ids]
    assert [row["journey_stage"] for row in versions] == [
        "first_contact",
        "deepening",
        "concretisation",
    ]
    assert versions[0]["prior_stage_presentation_version_id"] is None
    assert versions[1]["prior_stage_presentation_version_id"] == versions[0]["id"]
    assert versions[2]["prior_stage_presentation_version_id"] == versions[1]["id"]
    for row in versions:
        pptx = Path(row["pptx_storage_path"])
        pdf = Path(row["pdf_storage_path"])
        preview = pptx.parent / "slide-001.png"
        assert pptx.read_bytes().startswith(b"PK")
        assert pdf.read_bytes().startswith(b"%PDF")
        assert preview.read_bytes().startswith(b"\x89PNG")
        with zipfile.ZipFile(pptx) as archive:
            slide_xml = archive.read("ppt/slides/slide1.xml")
        stage_label = row["journey_stage"].replace("_", " ").capitalize()
        assert f"DEMO DATA - {stage_label}".encode() in slide_xml
    assert mtimes_before == {
        path: Path(row[path]).stat().st_mtime_ns
        for row in versions
        for path in ("pptx_storage_path", "pdf_storage_path")
    }
    assert first_hashes == {
        name: hashlib.sha256(
            Path(versions[index // 2][f"{name.rsplit('.', 1)[1]}_storage_path"]).read_bytes()
        ).hexdigest()
        for index, name in enumerate(first_hashes)
    }

    install_demo_data(user_id=USER_B, store=store, artifact_root=tmp_path)
    user_a_opportunities = [
        row for row in store.tables["opportunities"].values() if row["created_by"] == str(USER_A)
    ]
    user_b_opportunities = [
        row for row in store.tables["opportunities"].values() if row["created_by"] == str(USER_B)
    ]
    assert len(user_a_opportunities) == len(user_b_opportunities) == 2
    assert {row["id"] for row in user_a_opportunities}.isdisjoint(
        {row["id"] for row in user_b_opportunities}
    )
    corpus_rows = store.tables["knowledge_corpus_versions"].values()
    assert {row["owner_user_id"] for row in corpus_rows} == {str(USER_A), str(USER_B)}


def test_production_profile_refuses_before_writes(monkeypatch, tmp_path: Path, capsys) -> None:
    script = ROOT / "scripts" / "seed_demo_data.py"
    spec = importlib.util.spec_from_file_location("seed_demo_data", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("RUNTIME_PROFILE", "production")
    monkeypatch.setenv("DEMO_DATA_ENABLED", "true")
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path))

    assert module.main() == 2
    assert "Refusing" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_root_install_command_is_stable() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["seed:demo"] == "py -3 scripts/seed_demo_data.py"
