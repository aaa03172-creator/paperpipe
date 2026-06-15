import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from urllib.parse import quote

import fitz
from fastapi.testclient import TestClient

from backend import main as api_main
from backend.services import job_runner as job_runner_mod
from backend.routers import paper_notes as paper_notes_router
from src import db_utils
from src.agents.ingest_agent import IngestAgent
from src.schemas.paper_notes import PaperNoteImportResponse, PaperNoteIndexItem, PaperNoteOpsSummary
from src.services.paper_operator_state_store import operator_state_path


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_state(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_artifact_run(path, *, claimset: dict | None = None, stats_report: dict | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if claimset is not None:
        _write_state(path / "claimset.resolved.json", claimset)
    if stats_report is not None:
        _write_state(path / "stats_report.json", stats_report)


def _make_import_parser_fixture_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((54, 54), "Import Parser Fixture Paper", fontsize=14)
    page.insert_text((54, 78), "A. Importer, B. Parser", fontsize=9)
    page.insert_textbox(
        fitz.Rect(54, 118, 541, 720),
        (
            "Abstract\n"
            "This fixture verifies that a manually imported PDF is the same file later resolved for parsing.\n"
            "Methods\n"
            "The upload route stores the PDF, writes the paper row, and the job runner resolves pdf_path from DB.\n"
            "Results\n"
            "The parser must preserve this sentinel phrase: IMPORT-PARSER-SENTINEL-2026.\n"
            "Discussion\n"
            "A full import-to-parser regression protects the boundary between storage and extraction.\n"
        ),
        fontsize=9,
        lineheight=1.2,
    )
    doc.set_metadata({"title": "Import Parser Fixture Paper", "author": "A. Importer; B. Parser"})
    doc.save(path)
    doc.close()


def _fixture_structured_state(slug: str) -> dict:
    return {
        "paper_slug": slug,
        "updated_at": "2026-03-10T09:00:00Z",
        "runs": [],
        "signals": {"has_claimset": True},
        "claimset": [
            {
                "id": "claim_c0ffee000001",
                "claim": "Fixture-only structured state should stay hidden from real viewer surfaces.",
                "evidence_ids": ["evidence_deadbeef0001"],
                "evidence": [
                    {
                        "id": "evidence_deadbeef0001",
                        "claim_id": "claim_c0ffee000001",
                        "text": "Fixture evidence.",
                        "page": 0,
                        "source": "bbox",
                        "locator": {
                            "page": 0,
                            "span": [0, 16],
                            "chunk_id": "chunk-e2e-001",
                            "source": "bbox",
                        },
                    }
                ],
                "confidence": 0.9,
                "tags": ["fixture"],
                "outcomes": ["hidden"],
                "source_claim_id": "e2e-claim-1",
            }
        ],
        "entities": ["Fixture"],
        "mesh": ["Fixture"],
        "outcomes": ["hidden"],
    }


def test_import_pdf_route_runs_payload_processing_in_worker_thread(monkeypatch):
    calls = {}

    async def fake_run_sync(func):
        calls["used_worker_thread"] = True
        return func()

    def fake_import_pdf_payload(*, filename: str, payload: bytes):
        calls["filename"] = filename
        calls["payload"] = payload
        return PaperNoteImportResponse(
            paper_id="userpdf-threaded",
            slug="threaded-import",
            title="Threaded Import",
            note_path="Inbox/PaperPipe/threaded-import.md",
            pdf_url="/papers/userpdf-threaded/pdf",
            doi=None,
        )

    monkeypatch.setattr(paper_notes_router.anyio.to_thread, "run_sync", fake_run_sync)
    monkeypatch.setattr(paper_notes_router, "import_pdf_payload", fake_import_pdf_payload)

    response = TestClient(api_main.app).post(
        "/paper-notes/import-pdf",
        files={"file": ("threaded.pdf", b"%PDF-threaded", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["paper_id"] == "userpdf-threaded"
    assert calls == {
        "used_worker_thread": True,
        "filename": "threaded.pdf",
        "payload": b"%PDF-threaded",
    }


def _note_content(
    *,
    note_id: str,
    alias: str,
    tags: list[str],
    date_processed: str,
    confidence: float,
    status: str,
    related_slug: str | None = None,
    doi: str | None = "10.1000/182",
    zotero_link: str | None = None,
    pdf_url: str | None = None,
    reference_lines: list[str] | None = None,
) -> str:
    related_block = ""
    if related_slug:
        related_block = (
            "\n## 🔗 Related Papers\n"
            f"- [[Inbox/PaperPipe/{related_slug}|Related Title]] (shared tags: {tags[0]})\n"
        )
    references = reference_lines if reference_lines is not None else ["* [Open PDF](file:///Users/test/Documents/private.pdf)"]
    frontmatter_lines = [
        "---",
        f"id: {note_id}",
        f"aliases: [\"{alias}\"]",
        "tags:",
        *[f"  - {tag}" for tag in tags],
        f"date_processed: {date_processed}",
        f"confidence: {confidence}",
        f"status: {status}",
    ]
    if doi is not None:
        frontmatter_lines.append(f"doi: {doi}")
    if zotero_link is not None:
        frontmatter_lines.append(f"zotero_link: {zotero_link}")
    if pdf_url is not None:
        frontmatter_lines.append(f"pdf_url: {pdf_url}")
    frontmatter_lines.append("---")

    return (
        "\n".join(frontmatter_lines)
        + "\n\n"
        f"# {alias}\n\n"
        "> **One-Line Summary**\n"
        "> Summary text.\n\n"
        "## Critical Review (ClaimSet)\n"
        "### Claim 1\n"
        "- Claim: Example claim\n"
        + (f"- Context: [[Inbox/PaperPipe/{related_slug}|Related Title]]\n" if related_slug else "")
        + "- Confidence: 0.9\n"
        + related_block
        + "\n## 🔗 References\n"
        + "\n".join(references)
        + "\n"
    )


def test_paper_notes_list_builds_index_and_filters(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "zoteroduboisAlzheimerDiseaseClinicalBiological2024.md",
        _note_content(
            note_id="zotero:duboisAlzheimerDiseaseClinicalBiological2024",
            alias="Alzheimer Disease as a Clinical-Biological Construct—An International Working Group Recommendation",
            tags=["Medicine/Neurology", "Alzheimers_Disease"],
            date_processed="2026-02-24",
            confidence=0.9,
            status="INDEXED",
            related_slug="zoteroduboisAmnesticMCIProdromal2004",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "zoteroduboisAmnesticMCIProdromal2004.md",
        _note_content(
            note_id="zotero:duboisAmnesticMCIProdromal2004",
            alias="Amnestic MCI or prodromal Alzheimer's disease?",
            tags=["Medicine/Neurology", "Alzheimers_Disease"],
            date_processed="2026-02-20",
            confidence=0.8,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / "zoteroduboisAlzheimerDiseaseClinicalBiological2024" / "state.json",
        {
            "paper_slug": "zoteroduboisAlzheimerDiseaseClinicalBiological2024",
            "updated_at": "2026-02-24T09:00:00Z",
            "runs": [],
            "signals": {"has_claimset": True},
            "claimset": [
                {
                    "id": "claim-structured-001",
                    "claim": "Biomarker-first criteria support diagnosis.",
                    "confidence": 0.88,
                    "tags": ["biomarker"],
                    "evidence": [],
                    "evidence_ids": [],
                }
            ],
            "entities": ["Amyloid"],
            "mesh": ["Neurology"],
            "outcomes": ["memory"],
            "reading_assists": [
                {
                    "locale": "ko",
                    "canonical_locale": "en",
                    "machine_translated": True,
                    "partial": True,
                    "blocks": [
                        {
                            "kind": "abstract",
                            "text": "한국어 보조 요약이 준비된 노트다.",
                            "source_heading": "Abstract",
                            "provenance": {
                                "source_field": "abstract",
                                "source_locale": "en",
                            },
                        }
                    ],
                }
            ],
        },
    )
    _write(vault_dir / "2026-02-24.md", "# daily note\n")

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)

    response = client.get("/paper-notes")
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert payload["available_reading_assist_note_count"] == 1
    assert payload["available_reading_assist_locales"] == ["ko"]
    assert payload["items"][0]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"
    assert payload["items"][0]["pp_signals"]["has_claimset"] is True
    assert payload["items"][0]["reading_assist_available"] is True
    assert payload["items"][0]["reading_assist_locales"] == ["ko"]
    assert (tmp_path / "storage" / "obsidian" / "paper_notes_index.json").exists()

    api_prefixed = client.get("/api/paper-notes")
    assert api_prefixed.status_code == 200
    api_payload = api_prefixed.json()
    assert api_payload["total"] == 2
    assert api_payload["available_reading_assist_note_count"] == 1
    assert api_payload["available_reading_assist_locales"] == ["ko"]
    assert api_payload["items"][0]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"

    filtered = client.get("/paper-notes", params={"tag": "Alzheimers_Disease", "q": "prodromal"})
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["slug"] == "zoteroduboisAmnesticMCIProdromal2004"

    structured = client.get("/paper-notes", params={"structured_only": "true"})
    assert structured.status_code == 200
    structured_payload = structured.json()
    assert structured_payload["total"] == 1
    assert structured_payload["items"][0]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"

    any_reading_assist = client.get("/paper-notes", params={"has_reading_assist": "true"})
    assert any_reading_assist.status_code == 200
    any_reading_assist_payload = any_reading_assist.json()
    assert any_reading_assist_payload["total"] == 1
    assert any_reading_assist_payload["items"][0]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"

    korean_assist = client.get("/paper-notes", params={"reading_assist_locale": "ko"})
    assert korean_assist.status_code == 200
    korean_assist_payload = korean_assist.json()
    assert korean_assist_payload["total"] == 1
    assert korean_assist_payload["items"][0]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"

    multi_token = client.get("/paper-notes", params={"q": "Amyloid Neurology"})
    assert multi_token.status_code == 200
    multi_token_payload = multi_token.json()
    assert multi_token_payload["total"] == 1
    assert multi_token_payload["items"][0]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"

    exact_phrase = client.get("/paper-notes", params={"q": "\"Clinical-Biological Construct\""})
    assert exact_phrase.status_code == 200
    exact_phrase_payload = exact_phrase.json()
    assert exact_phrase_payload["total"] == 1
    assert exact_phrase_payload["items"][0]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"


def test_paper_notes_home_context_summarizes_counts_and_slug_links(monkeypatch, tmp_path):
    monkeypatch.setattr(paper_notes_router, "_resolve_vault_path", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        paper_notes_router,
        "_build_index",
        lambda vault_path: SimpleNamespace(
            items=[
                PaperNoteIndexItem(
                    slug="zoteroduboisAlzheimerDiseaseClinicalBiological2024",
                    title="Dubois",
                    note_path="Inbox/PaperPipe/zoteroduboisAlzheimerDiseaseClinicalBiological2024.md",
                    id="zotero:duboisAlzheimerDiseaseClinicalBiological2024",
                    structured_state_present=True,
                    starred=True,
                    has_operator_note=True,
                    triage_labels=["revisit"],
                    updated_at="2026-04-12T09:30:00Z",
                ),
                PaperNoteIndexItem(
                    slug="paper-standalone-2026",
                    title="Standalone",
                    note_path="Inbox/PaperPipe/paper-standalone-2026.md",
                    id="paper-standalone-2026",
                    structured_state_present=False,
                    triage_labels=["needs_verification", "experiment_relevant"],
                    updated_at="2026-04-10T07:00:00Z",
                ),
            ]
        ),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/home-context")

    assert response.status_code == 200
    assert response.json() == {
        "saved_notes": 2,
        "structured_notes": 1,
        "latest_note_updated_at": "2026-04-12T09:30:00Z",
        "note_context_limited": False,
        "note_slug_by_paper_id": {
            "zotero:duboisAlzheimerDiseaseClinicalBiological2024": "zoteroduboisAlzheimerDiseaseClinicalBiological2024",
            "zoteroduboisAlzheimerDiseaseClinicalBiological2024": "zoteroduboisAlzheimerDiseaseClinicalBiological2024",
            "duboisAlzheimerDiseaseClinicalBiological2024": "zoteroduboisAlzheimerDiseaseClinicalBiological2024",
            "paper-standalone-2026": "paper-standalone-2026",
        },
        "marker_summary": {
            "marked_papers": 2,
            "note_backed_papers": 1,
            "starred": 1,
            "triage_counts": {
                "revisit": 1,
                "needs_verification": 1,
                "experiment_relevant": 1,
            },
        },
    }


def test_paper_notes_list_dedupes_legacy_variant_but_preserves_ops_signal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    canonical_slug = "Discovery of a dual-action small molecule that improves neuropathological features of Alzheimer s disease mice"
    legacy_slug = "parkDiscoveryDualactionSmall2022"
    paper_id = "zotero:parkDiscoveryDualactionSmall2022"

    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{canonical_slug}.md",
        "\n".join(
            [
                "---",
                f"id: {paper_id}",
                'aliases: ["Discovery of a dual-action small molecule that improves neuropathological features of Alzheimer’s disease mice"]',
                "tags:",
                "  - Neuroscience/Alzheimer_s_Disease",
                "date_processed: 2026-04-02",
                "confidence: 0.9",
                "status: INDEXED",
                "pp:",
                f"  structured_path: .pp/{canonical_slug}/state.json",
                "---",
                "",
                "# Discovery of a dual-action small molecule that improves neuropathological features of Alzheimer’s disease mice",
                "",
                "## 🔗 References",
                "* [Open PDF](file:///Users/test/Documents/park.pdf)",
                "",
            ]
        ),
    )
    _write_state(
        vault_dir / ".pp" / canonical_slug / "state.json",
        _fixture_structured_state(canonical_slug),
    )

    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{legacy_slug}.md",
        _note_content(
            note_id="parkDiscoveryDualactionSmall2022",
            alias="Discovery of a dual-action small molecule that improves neuropathological features of Alzheimer’s disease mice",
            tags=["Neuroscience/Alzheimer_s_Disease"],
            date_processed="2026-02-19",
            confidence=0.9,
            status="INDEXED",
        ),
    )
    _write_artifact_run(
        artifacts_dir / legacy_slug / "run-legacy",
        claimset={"claims": [{"claim_id": "c1"}]},
        stats_report={"checks": []},
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)

    response = client.get("/paper-notes", params={"q": "dual-action small molecule"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["slug"] == canonical_slug
    assert payload["items"][0]["id"] == paper_id
    assert payload["items"][0]["ops_summary"]["state"] == "action_needed"
    assert payload["items"][0]["ops_summary"]["recommended_action"] == "repair_stats"

    legacy_query = client.get("/paper-notes", params={"q": legacy_slug})
    assert legacy_query.status_code == 200
    legacy_payload = legacy_query.json()
    assert legacy_payload["total"] == 1
    assert legacy_payload["items"][0]["slug"] == canonical_slug


def test_paper_notes_home_context_dedupes_equivalent_variants_and_preserves_markers(monkeypatch, tmp_path):
    canonical_slug = "Discovery of a dual-action small molecule that improves neuropathological features of Alzheimer s disease mice"
    monkeypatch.setattr(paper_notes_router, "_resolve_vault_path", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        paper_notes_router,
        "_build_index",
        lambda vault_path: SimpleNamespace(
            items=[
                PaperNoteIndexItem(
                    slug=canonical_slug,
                    title="Discovery of a dual-action small molecule that improves neuropathological features of Alzheimer’s disease mice",
                    note_path=f"Inbox/PaperPipe/{canonical_slug}.md",
                    id="zotero:parkDiscoveryDualactionSmall2022",
                    structured_state_present=True,
                    updated_at="2026-04-12T09:30:00Z",
                ),
                PaperNoteIndexItem(
                    slug="parkDiscoveryDualactionSmall2022",
                    title="Discovery of a dual-action small molecule that improves neuropathological features of Alzheimer’s disease mice",
                    note_path="Inbox/PaperPipe/parkDiscoveryDualactionSmall2022.md",
                    id="parkDiscoveryDualactionSmall2022",
                    structured_state_present=False,
                    starred=True,
                    has_operator_note=True,
                    triage_labels=["needs_verification"],
                    updated_at="2026-04-10T07:00:00Z",
                ),
            ]
        ),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/home-context")

    assert response.status_code == 200
    assert response.json() == {
        "saved_notes": 1,
        "structured_notes": 1,
        "latest_note_updated_at": "2026-04-12T09:30:00Z",
        "note_context_limited": False,
        "note_slug_by_paper_id": {
            "zotero:parkDiscoveryDualactionSmall2022": canonical_slug,
            "zoteroparkDiscoveryDualactionSmall2022": canonical_slug,
            "parkDiscoveryDualactionSmall2022": canonical_slug,
            canonical_slug: canonical_slug,
        },
        "marker_summary": {
            "marked_papers": 1,
            "note_backed_papers": 1,
            "starred": 1,
            "triage_counts": {
                "revisit": 0,
                "needs_verification": 1,
                "experiment_relevant": 0,
            },
        },
    }


def test_paper_notes_home_context_marks_note_context_limited_when_index_fails(monkeypatch):
    monkeypatch.setattr(paper_notes_router, "_resolve_vault_path", lambda: Path("/missing"))
    monkeypatch.setattr(
        paper_notes_router,
        "_build_index",
        lambda vault_path: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/home-context")

    assert response.status_code == 200
    assert response.json() == {
        "saved_notes": 0,
        "structured_notes": 0,
        "latest_note_updated_at": None,
        "note_context_limited": True,
        "note_slug_by_paper_id": {},
        "marker_summary": {
            "marked_papers": 0,
            "note_backed_papers": 0,
            "starred": 0,
            "triage_counts": {
                "revisit": 0,
                "needs_verification": 0,
                "experiment_relevant": 0,
            },
        },
    }


def test_paper_notes_list_returns_empty_index_when_index_fails(monkeypatch):
    monkeypatch.setattr(paper_notes_router, "_resolve_vault_path", lambda: Path("/missing"))
    monkeypatch.setattr(
        paper_notes_router,
        "_build_index",
        lambda vault_path: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes?page=3&page_size=10&sort_by=date_processed&sort_order=desc")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["page"] == 1
    assert payload["page_size"] == 10
    assert payload["total_pages"] == 1
    assert payload["available_tags"] == []
    assert payload["available_statuses"] == []
    assert payload["available_reading_assist_note_count"] == 0
    assert payload["available_reading_assist_locales"] == []
    assert payload["items"] == []


def test_paper_notes_search_prefers_query_relevance_before_secondary_sort(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "title-match.md",
        _note_content(
            note_id="zotero:title-match",
            alias="Amyloid Neurology Guidance",
            tags=["Tag/Generic"],
            date_processed="2026-01-01",
            confidence=0.4,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "tag-match.md",
        _note_content(
            note_id="zotero:tag-match",
            alias="Generic Biomarker Note",
            tags=["Amyloid", "Neurology"],
            date_processed="2026-03-01",
            confidence=0.9,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get(
        "/paper-notes",
        params={"q": "Amyloid Neurology", "sort_by": "date_processed", "sort_order": "desc"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["slug"] for item in payload["items"]] == ["title-match", "tag-match"]


def test_paper_notes_support_renamed_stateful_note_with_legacy_structured_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    legacy_slug = "zoterocoricTargetingProdromalAlzheimer2015"
    readable_slug = "Targeting Prodromal Alzheimer Disease With Avagacestat A Randomized Clinical Trial"

    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{readable_slug}.md",
        "\n".join(
            [
                "---",
                "id: zotero:coricTargetingProdromalAlzheimer2015",
                f"aliases: [\"{readable_slug}\"]",
                "tags:",
                "  - Medicine/Neurology",
                "date_processed: 2026-03-28",
                "confidence: 0.91",
                "status: INDEXED",
                "pp:",
                f"  structured_path: .pp/{legacy_slug}/state.json",
                "---",
                "",
                f"# {readable_slug}",
                "",
                "## 🔗 References",
                "* [Open PDF](file:///Users/test/Documents/private.pdf)",
                "",
            ]
        ),
    )
    _write_state(
        vault_dir / ".pp" / legacy_slug / "state.json",
        {
            "paper_slug": legacy_slug,
            "updated_at": "2026-03-28T00:00:00Z",
            "runs": [],
            "signals": {"has_claimset": True},
            "claimset": [
                {
                    "id": "claim-001",
                    "claim": "Example claim",
                    "confidence": 0.9,
                    "tags": ["biomarker"],
                    "evidence": [],
                    "evidence_ids": [],
                }
            ],
            "entities": ["Amyloid"],
            "mesh": ["Neurology"],
            "outcomes": ["memory"],
        },
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)

    listing = client.get("/paper-notes")
    assert listing.status_code == 200
    list_payload = listing.json()
    assert list_payload["items"][0]["slug"] == readable_slug
    assert list_payload["items"][0]["structured_state_present"] is True

    for lookup_id in (
        "zotero:coricTargetingProdromalAlzheimer2015",
        "zoterocoricTargetingProdromalAlzheimer2015",
        "coricTargetingProdromalAlzheimer2015",
    ):
        resolved = client.get(
            "/paper-notes/resolve-by-paper-id",
            params={"paper_id": lookup_id},
        )
        assert resolved.status_code == 200
        resolved_payload = resolved.json()
        assert resolved_payload["slug"] == readable_slug
        assert resolved_payload["structured_state"]["paper_slug"] == legacy_slug

    detail = client.get(f"/paper-notes/{readable_slug}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["structured_state"]["paper_slug"] == legacy_slug
    assert ".pp/zoterocoricTargetingProdromalAlzheimer2015/state.json" in detail_payload["context_trace"]["summary"]["source_paths"]


def test_paper_notes_import_pdf_creates_note_and_pdf_route(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )

    sample_pdf_path = Path(__file__).resolve().parents[1] / "frontend" / "public" / "sample.pdf"
    client = TestClient(api_main.app)

    with sample_pdf_path.open("rb") as handle:
        response = client.post(
            "/paper-notes/import-pdf",
            files={"file": ("sample.pdf", handle.read(), "application/pdf")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_id"].startswith("userpdf-")
    assert payload["slug"].startswith("sample")
    assert payload["pdf_url"] == f"/papers/{payload['paper_id']}/pdf"

    note_path = vault_dir / payload["note_path"]
    assert note_path.exists()
    note_body = note_path.read_text(encoding="utf-8")
    assert "Imported from a local PDF on this machine." in note_body
    assert "Open in Workbench" in note_body
    assert f"- {payload['paper_id']}" in note_body

    listing = client.get("/paper-notes")
    assert listing.status_code == 200
    listing_payload = listing.json()
    assert listing_payload["total"] == 1
    assert listing_payload["items"][0]["slug"] == payload["slug"]
    assert listing_payload["items"][0]["id"] == payload["paper_id"]

    pdf_response = client.get(payload["pdf_url"])
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")


def test_paper_notes_import_pdf_creates_paper_state_after_runtime_db_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )
    monkeypatch.setattr(paper_notes_router, "_extract_import_title", lambda path, fallback_name: "Fresh DB Paper")

    response = TestClient(api_main.app).post(
        "/paper-notes/import-pdf",
        files={"file": ("fresh-db.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_id"].startswith("userpdf-")
    assert payload["title"] == "Fresh DB Paper"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT paper_id, title, source, status, pdf_path, issues_state, obsidian_path FROM papers WHERE paper_id = ?",
        (payload["paper_id"],),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["title"] == "Fresh DB Paper"
    assert row["source"] == "user_imported_pdf"
    assert row["status"] == "NEW"
    assert row["issues_state"] == "unavailable"
    assert Path(row["pdf_path"]).exists()
    assert row["obsidian_path"] == payload["note_path"]


def test_paper_notes_import_pdf_persists_local_doi_hint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )
    monkeypatch.setattr(
        paper_notes_router,
        "_extract_import_doi",
        lambda path: "10.1126/science.aeb0045",
    )

    response = TestClient(api_main.app).post(
        "/paper-notes/import-pdf",
        files={"file": ("science.aeb0045.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["doi"] == "10.1126/science.aeb0045"

    note_body = (vault_dir / payload["note_path"]).read_text(encoding="utf-8")
    assert "doi: 10.1126/science.aeb0045" in note_body
    assert "DOI: 10.1126/science.aeb0045" in note_body

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT doi FROM papers WHERE paper_id = ?", (payload["paper_id"],)).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "10.1126/science.aeb0045"


def test_paper_notes_imported_pdf_can_be_enqueued_for_deepread(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )
    monkeypatch.setattr(paper_notes_router, "_extract_import_title", lambda path, fallback_name: "Deep Read Ready")

    client = TestClient(api_main.app)
    import_response = client.post(
        "/paper-notes/import-pdf",
        files={"file": ("deep-read-ready.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )

    assert import_response.status_code == 200
    import_payload = import_response.json()
    paper_id = import_payload["paper_id"]
    expected_pdf_path = pdf_storage_dir / f"{paper_id}.pdf"
    assert expected_pdf_path.exists()
    assert job_runner_mod._resolve_pdf_path_from_db(paper_id) == expected_pdf_path

    enqueue_response = client.post("/jobs/deepread", json={"paper_id": paper_id, "clean_reindex": True})

    assert enqueue_response.status_code == 200
    enqueue_payload = enqueue_response.json()
    assert enqueue_payload["status"] == "queued"
    assert enqueue_payload["run_id"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    job_row = conn.execute(
        "SELECT paper_id, status, clean_reindex FROM jobs WHERE job_id = ?",
        (enqueue_payload["job_id"],),
    ).fetchone()
    action_row = conn.execute(
        """
        SELECT action_type, payload_json
        FROM user_actions
        WHERE paper_id = ?
        ORDER BY ts DESC, rowid DESC
        LIMIT 1
        """,
        (paper_id,),
    ).fetchone()
    conn.close()

    assert job_row is not None
    assert job_row["paper_id"] == paper_id
    assert job_row["status"] == "queued"
    assert job_row["clean_reindex"] == 1
    assert action_row is not None
    assert action_row["action_type"] == "deepread_enqueued"
    assert json.loads(action_row["payload_json"])["run_id"] == enqueue_payload["run_id"]


def test_paper_notes_imported_pdf_resolves_to_parser_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    source_pdf = tmp_path / "import-parser-fixture.pdf"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()
    _make_import_parser_fixture_pdf(source_pdf)

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )

    client = TestClient(api_main.app)
    response = client.post(
        "/paper-notes/import-pdf",
        files={"file": ("import-parser-fixture.pdf", source_pdf.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    paper_id = payload["paper_id"]
    resolved_pdf_path = job_runner_mod._resolve_pdf_path_from_db(paper_id)

    assert resolved_pdf_path == pdf_storage_dir / f"{paper_id}.pdf"
    assert resolved_pdf_path.exists()
    assert resolved_pdf_path.read_bytes() == source_pdf.read_bytes()

    artifact = IngestAgent().process_v2(str(resolved_pdf_path))

    assert artifact is not None
    assert artifact.document_id == f"file:{resolved_pdf_path.name}"
    assert artifact.meta.title == "Import Parser Fixture Paper"
    parsed_text = "\n".join(
        line.text
        for page in artifact.pages
        for block in page.blocks
        for line in block.lines
    )
    assert "IMPORT-PARSER-SENTINEL-2026" in parsed_text
    assert any(
        str(span.source_ref).endswith(f"{resolved_pdf_path}#page=0")
        for page in artifact.pages
        for block in page.blocks
        for line in block.lines
        for span in line.spans
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT paper_id, source, status, pdf_path, obsidian_path FROM papers WHERE paper_id = ?",
        (paper_id,),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["source"] == "user_imported_pdf"
    assert row["status"] == "NEW"
    assert Path(row["pdf_path"]) == resolved_pdf_path
    assert row["obsidian_path"] == payload["note_path"]


def test_paper_notes_import_pdf_merges_duplicate_existing_doi(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO papers (paper_id, doi, title, source, status) VALUES (?, ?, ?, ?, ?)",
        ("doi:10.1126/science.aeb0045", "https://doi.org/10.1126/science.aeb0045", "Existing", "pubmed", "NEW"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )
    monkeypatch.setattr(
        paper_notes_router,
        "_extract_import_doi",
        lambda path: "10.1126/science.aeb0045",
    )

    response = TestClient(api_main.app).post(
        "/paper-notes/import-pdf",
        files={"file": ("science-duplicate.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_id"] == "doi:10.1126/science.aeb0045"
    assert payload["pdf_url"] == f"/papers/{quote(payload['paper_id'], safe='')}/pdf"

    notes = list((vault_dir / "Inbox" / "PaperPipe").glob("*.md"))
    assert len(notes) == 1
    note_body = notes[0].read_text(encoding="utf-8")
    assert "id: doi:10.1126/science.aeb0045" in note_body
    assert "- doi:10.1126/science.aeb0045" in note_body

    stored_pdfs = list(pdf_storage_dir.glob("*.pdf"))
    assert len(stored_pdfs) == 1
    pdf_response = TestClient(api_main.app).get(payload["pdf_url"])
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT paper_id, doi, pdf_path, obsidian_path FROM papers").fetchall()
    conn.close()
    assert rows == [
        (
            "doi:10.1126/science.aeb0045",
            "10.1126/science.aeb0045",
            str(stored_pdfs[0]),
            payload["note_path"],
        )
    ]


def test_paper_notes_reimport_updates_existing_note_doi(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )
    monkeypatch.setattr(paper_notes_router, "_extract_import_title", lambda path, fallback_name: "Science Paper")
    doi_values = iter([None, "10.1126/science.aeb0045"])
    monkeypatch.setattr(paper_notes_router, "_extract_import_doi", lambda path: next(doi_values))

    client = TestClient(api_main.app)
    first = client.post(
        "/paper-notes/import-pdf",
        files={"file": ("science.aeb0045.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )
    assert first.status_code == 200
    note_path = vault_dir / first.json()["note_path"]
    assert "doi:" not in note_path.read_text(encoding="utf-8")

    second = client.post(
        "/paper-notes/import-pdf",
        files={"file": ("science.aeb0045.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )

    assert second.status_code == 200
    assert second.json()["note_path"] == first.json()["note_path"]
    note_body = note_path.read_text(encoding="utf-8")
    assert "doi: 10.1126/science.aeb0045" in note_body
    assert note_body.count("DOI: 10.1126/science.aeb0045") == 1


def test_paper_notes_reimport_does_not_mutate_existing_note_when_db_persist_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )
    monkeypatch.setattr(paper_notes_router, "_extract_import_title", lambda path, fallback_name: "Science Paper")
    doi_values = iter([None, "10.1126/science.aeb0045"])
    monkeypatch.setattr(paper_notes_router, "_extract_import_doi", lambda path: next(doi_values))

    client = TestClient(api_main.app)
    first = client.post(
        "/paper-notes/import-pdf",
        files={"file": ("science.aeb0045.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )
    assert first.status_code == 200
    note_path = vault_dir / first.json()["note_path"]
    original_note = note_path.read_text(encoding="utf-8")

    def fail_persist_note_path(*args, **kwargs):
        raise RuntimeError("forced note path persist failure")

    monkeypatch.setattr(paper_notes_router, "_persist_imported_note_path", fail_persist_note_path)
    second = client.post(
        "/paper-notes/import-pdf",
        files={"file": ("science.aeb0045.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )

    assert second.status_code == 500
    assert note_path.read_text(encoding="utf-8") == original_note


def test_paper_notes_import_pdf_cleans_up_new_db_row_after_post_save_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )
    monkeypatch.setattr(paper_notes_router, "_extract_import_title", lambda path, fallback_name: "Rollback Paper")

    def fail_persist_note_path(*args, **kwargs):
        raise RuntimeError("forced post-save failure")

    monkeypatch.setattr(paper_notes_router, "_persist_imported_note_path", fail_persist_note_path)

    response = TestClient(api_main.app).post(
        "/paper-notes/import-pdf",
        files={"file": ("rollback.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to persist imported paper state."
    assert list((vault_dir / "Inbox" / "PaperPipe").glob("*.md")) == []
    assert list(pdf_storage_dir.glob("*.pdf")) == []

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT paper_id FROM papers").fetchall()
    conn.close()
    assert rows == []


def test_extract_import_doi_from_text_normalizes_science_url():
    text = "Available at https://www.science.org/doi/10.1126/science.aeb0045."

    assert paper_notes_router._extract_import_doi_from_text(text) == "10.1126/science.aeb0045"


def test_select_import_doi_candidate_prefers_repeated_article_doi():
    candidates = [
        ("10.1101/2025.02.19.639050", "reference list"),
        ("10.1126/science.aeb0045", "Downloaded from science.org/doi/10.1126/science.aeb0045"),
        ("10.1126/science.aeb0045", "Article DOI 10.1126/science.aeb0045"),
    ]

    assert paper_notes_router._select_import_doi_candidate(candidates) == "10.1126/science.aeb0045"


def test_paper_notes_import_pdf_sanitizes_filename_derived_title(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )

    raw_secret = "sk-proj-import-title-secret-abcdef"
    client = TestClient(api_main.app)
    response = client.post(
        "/paper-notes/import-pdf",
        files={"file": (f"secret-{raw_secret}.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert raw_secret not in json.dumps(payload)
    assert payload["title"] == "secret <redacted>"
    assert raw_secret not in payload["slug"]

    note_body = (vault_dir / payload["note_path"]).read_text(encoding="utf-8")
    assert raw_secret not in note_body
    assert "secret <redacted>" in note_body

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT title FROM papers WHERE paper_id = ?", (payload["paper_id"],)).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "secret <redacted>"


def test_paper_notes_import_pdf_cleans_up_when_db_state_is_not_persisted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )
    monkeypatch.setattr(paper_notes_router, "save_paper_state", lambda *args, **kwargs: None)

    sample_pdf_path = Path(__file__).resolve().parents[1] / "frontend" / "public" / "sample.pdf"
    client = TestClient(api_main.app)

    with sample_pdf_path.open("rb") as handle:
        response = client.post(
            "/paper-notes/import-pdf",
            files={"file": ("sample.pdf", handle.read(), "application/pdf")},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to persist imported paper state."
    assert list((vault_dir / "Inbox" / "PaperPipe").glob("*.md")) == []
    assert list(pdf_storage_dir.glob("*.pdf")) == []

    listing = client.get("/paper-notes")
    assert listing.status_code == 200
    assert listing.json()["total"] == 0


def test_paper_notes_import_pdf_rejects_note_path_collision_without_overwriting(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    pdf_storage_dir = tmp_path / "pdfs"
    db_path = tmp_path / "state.db"
    vault_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    db_utils.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            processed_date TEXT,
            processed_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            pdf_path TEXT,
            issues_state TEXT,
            obsidian_path TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir, pdf_storage_dir=pdf_storage_dir)),
    )

    sample_pdf_path = Path(__file__).resolve().parents[1] / "frontend" / "public" / "sample.pdf"
    sample_bytes = sample_pdf_path.read_bytes()
    digest = hashlib.sha1(sample_bytes).hexdigest()
    title = paper_notes_router._extract_import_title(sample_pdf_path, fallback_name=sample_pdf_path.stem)
    slug = f"{paper_notes_router._slugify_import_title(title)}-{digest[:8]}"
    colliding_note = vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md"
    original_body = (
        "---\n"
        "id: collision-existing-note\n"
        'aliases: ["Existing Note"]\n'
        "---\n\n"
        "# Existing Note\n"
    )
    _write(colliding_note, original_body)

    client = TestClient(api_main.app)
    response = client.post(
        "/paper-notes/import-pdf",
        files={"file": ("sample.pdf", sample_bytes, "application/pdf")},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "An existing note already occupies this import path."
    assert colliding_note.read_text(encoding="utf-8") == original_body
    assert list(pdf_storage_dir.glob("*.pdf")) == []


def test_paper_notes_import_pdf_rejects_oversized_uploads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_MAX_IMPORT_PDF_BYTES", "8")

    client = TestClient(api_main.app)
    response = client.post(
        "/paper-notes/import-pdf",
        files={"file": ("too-large.pdf", b"%PDF-1.4\n1234567890", "application/pdf")},
    )

    assert response.status_code == 413
    assert "configured limit" in response.json()["detail"]


def test_paper_notes_list_uses_runtime_storage_for_index_cache_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paperpipe_home = tmp_path / "app-home"
    monkeypatch.setenv("PAPERPIPE_HOME", str(paperpipe_home))

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "runtime-path-note.md",
        _note_content(
            note_id="zotero:runtime-path-note",
            alias="Runtime Path Note",
            tags=["Ops/Fix"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes")
    assert response.status_code == 200

    expected_index_path = (paperpipe_home / "storage" / "obsidian" / "paper_notes_index.json").resolve()
    payload = response.json()
    assert payload["index_path"] == str(expected_index_path)
    assert expected_index_path.exists()


def test_paper_notes_list_syncs_existing_db_row_from_note_frontmatter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path / "app-home"))
    db_path = tmp_path / "state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            updated_at TEXT,
            obsidian_path TEXT,
            reading_status TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO papers (
            paper_id, doi, title, source, status, updated_at, obsidian_path, reading_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "zotero:frontmatter-sync-note",
            None,
            "Frontmatter Sync Note",
            "test",
            "PENDING_REVIEW",
            None,
            None,
            None,
        ),
    )
    conn.commit()
    conn.close()

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "frontmatter-sync-note.md",
        _note_content(
            note_id="zotero:frontmatter-sync-note",
            alias="Frontmatter Sync Note",
            tags=["Ops/Sync"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
            doi="https://doi.org/10.5555/Frontmatter.Sync",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes")
    assert response.status_code == 200

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT doi, status, obsidian_path, updated_at FROM papers WHERE paper_id = ?",
        ("zotero:frontmatter-sync-note",),
    ).fetchone()
    conn.close()

    assert row["doi"] == "10.5555/frontmatter.sync"
    assert row["status"] == "INDEXED"
    assert row["obsidian_path"] == "Inbox/PaperPipe/frontmatter-sync-note.md"
    assert row["updated_at"]


def test_paper_notes_list_keeps_reading_status_out_of_pipeline_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_HOME", str(tmp_path / "app-home"))
    db_path = tmp_path / "state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            source TEXT,
            status TEXT,
            updated_at TEXT,
            obsidian_path TEXT,
            reading_status TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO papers (paper_id, title, source, status)
        VALUES (?, ?, ?, ?)
        """,
        ("zotero:reading-status-note", "Reading Status Note", "test", "APPROVED"),
    )
    conn.commit()
    conn.close()

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "reading-status-note.md",
        _note_content(
            note_id="zotero:reading-status-note",
            alias="Reading Status Note",
            tags=["Ops/Sync"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="Inbox",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes")
    assert response.status_code == 200

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status, reading_status FROM papers WHERE paper_id = ?",
        ("zotero:reading-status-note",),
    ).fetchone()
    conn.close()

    assert row["status"] == "APPROVED"
    assert row["reading_status"] == "Inbox"


def test_paper_notes_list_reuses_fresh_index_cache_without_rebuilding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "cache-reuse-note.md",
        _note_content(
            note_id="zotero:cache-reuse-note",
            alias="Cache Reuse Note",
            tags=["Ops/Cache"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    first = client.get("/paper-notes")
    assert first.status_code == 200
    assert first.json()["items"][0]["slug"] == "cache-reuse-note"

    monkeypatch.setattr(
        paper_notes_router,
        "_build_index_item",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cache miss unexpectedly rebuilt index items")),
    )

    second = client.get("/paper-notes")
    assert second.status_code == 200
    assert second.json()["items"][0]["slug"] == "cache-reuse-note"


def test_paper_note_resolve_by_paper_id_reuses_cached_runtime_metadata_without_rereading_markdown(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    vault_dir = tmp_path / "vault"
    note_id = "zotero:cache-lookup-note"
    slug = "cache-lookup-note"
    pdf_url = f"/papers/{quote(note_id, safe='')}/pdf"
    note_path = vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md"
    _write(
        note_path,
        _note_content(
            note_id=note_id,
            alias="Cache Lookup Note",
            tags=["Ops/Cache"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
            doi="10.1000/cache-lookup-note",
            pdf_url=pdf_url,
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    first = client.get("/paper-notes")
    assert first.status_code == 200
    assert first.json()["items"][0]["slug"] == slug

    cached_index = paper_notes_router._build_index(vault_dir)
    assert cached_index.items[0].has_runtime_source_metadata() is True

    def _unexpected_markdown_read(path: Path) -> str:
        raise AssertionError(f"unexpected markdown reread for resolve-by-paper-id: {path}")

    monkeypatch.setattr(paper_notes_router, "_safe_read_text", _unexpected_markdown_read)

    response = client.get("/paper-notes/resolve-by-paper-id", params={"paper_id": note_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["paper_id"] == note_id
    assert payload["slug"] == slug
    assert payload["pdf_url"] == pdf_url
    assert payload["doi_url"] == "https://doi.org/10.1000/cache-lookup-note"
    assert payload["note"]["title"] == "Cache Lookup Note"


def test_paper_notes_cache_invalidates_when_note_file_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    vault_dir = tmp_path / "vault"
    note_path = vault_dir / "Inbox" / "PaperPipe" / "cache-note-change.md"
    _write(
        note_path,
        _note_content(
            note_id="zotero:cache-note-change",
            alias="Original Cache Title",
            tags=["Ops/Cache"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    first = client.get("/paper-notes")
    assert first.status_code == 200
    assert first.json()["items"][0]["title"] == "Original Cache Title"

    _write(
        note_path,
        _note_content(
            note_id="zotero:cache-note-change",
            alias="Updated Cache Title",
            tags=["Ops/Cache"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
        ),
    )

    second = client.get("/paper-notes")
    assert second.status_code == 200
    assert second.json()["items"][0]["title"] == "Updated Cache Title"


def test_paper_notes_cache_invalidates_when_operator_state_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "cache-operator-note.md",
        _note_content(
            note_id="zotero:cache-operator-note",
            alias="Cache Operator Note",
            tags=["Ops/Cache"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    before = client.get("/paper-notes/home-context")
    assert before.status_code == 200
    assert before.json()["marker_summary"]["marked_papers"] == 0

    update = client.put(
        "/paper-notes/cache-operator-note/operator-state",
        json={
            "paper_note_text": "Marked after cache build.",
            "starred": True,
            "triage_labels": ["needs_verification"],
        },
    )
    assert update.status_code == 200

    after = client.get("/paper-notes/home-context")
    assert after.status_code == 200
    assert after.json()["marker_summary"] == {
        "marked_papers": 1,
        "note_backed_papers": 1,
        "starred": 1,
        "triage_counts": {
            "revisit": 0,
            "needs_verification": 1,
            "experiment_relevant": 0,
        },
    }


def test_paper_notes_detail_accepts_legacy_slug_for_renamed_stateful_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    legacy_slug = "zoterocoricTargetingProdromalAlzheimer2015"
    readable_slug = "Targeting Prodromal Alzheimer Disease With Avagacestat A Randomized Clinical Trial"

    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{readable_slug}.md",
        "\n".join(
            [
                "---",
                "id: zotero:coricTargetingProdromalAlzheimer2015",
                f"aliases: [\"{readable_slug}\"]",
                "tags:",
                "  - Medicine/Neurology",
                "date_processed: 2026-03-28",
                "confidence: 0.91",
                "status: INDEXED",
                "pp:",
                f"  structured_path: .pp/{legacy_slug}/state.json",
                "---",
                "",
                f"# {readable_slug}",
                "",
                "## 🔗 References",
                "* [Open PDF](file:///Users/test/Documents/private.pdf)",
                "",
            ]
        ),
    )
    _write_state(
        vault_dir / ".pp" / legacy_slug / "state.json",
        {
            "paper_slug": legacy_slug,
            "updated_at": "2026-03-28T00:00:00Z",
            "runs": [],
            "signals": {"has_claimset": True},
            "claimset": [],
            "entities": [],
            "mesh": [],
            "outcomes": [],
        },
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get(f"/paper-notes/{legacy_slug}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["note"]["slug"] == readable_slug
    assert payload["structured_state"]["paper_slug"] == legacy_slug


def test_paper_notes_list_includes_operational_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    _write(
        vault_dir / "Inbox" / "PaperPipe" / "healthy-note.md",
        _note_content(
            note_id="healthy-note",
            alias="Healthy Note",
            tags=["Medicine/Neurology"],
            date_processed="2026-03-09",
            confidence=0.92,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "repair-note.md",
        _note_content(
            note_id="repair-note",
            alias="Repair Note",
            tags=["Medicine/Neurology"],
            date_processed="2026-03-08",
            confidence=0.81,
            status="INDEXED",
        ),
    )

    _write_artifact_run(
        artifacts_dir / "healthy-note" / "run_healthy_001",
        claimset={"doc_id": "healthy-note", "claims": [{"claim_id": "CLM-1", "statement": "Healthy claim"}]},
        stats_report={
            "doc_id": "healthy-note",
            "run_id": "run_healthy_001",
            "checks": [{"check_id": "CHK-1"}, {"check_id": "CHK-2"}],
        },
    )
    _write_artifact_run(
        artifacts_dir / "repair-note" / "run_repair_001",
        claimset={"doc_id": "repair-note", "claims": [{"claim_id": "CLM-1", "statement": "Repair claim"}]},
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes")
    assert response.status_code == 200
    payload = response.json()

    items = {item["slug"]: item for item in payload["items"]}
    assert items["healthy-note"]["ops_summary"]["state"] == "healthy"
    assert items["healthy-note"]["ops_summary"]["recommended_action"] == "none"
    assert items["healthy-note"]["ops_summary"]["latest_run_id"] == "run_healthy_001"
    assert items["healthy-note"]["ops_summary"]["stats_check_count"] == 2
    assert items["repair-note"]["ops_summary"]["state"] == "action_needed"
    assert items["repair-note"]["ops_summary"]["reason"] == "Saved note checks are missing or empty."
    assert items["repair-note"]["ops_summary"]["recommended_action"] == "repair_stats"
    assert items["repair-note"]["ops_summary"]["latest_run_id"] == "run_repair_001"


def test_deduped_paper_note_items_recompute_ops_summary_from_latest_variant_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    canonical = PaperNoteIndexItem(
        slug="canonical-note",
        title="Same paper",
        note_path="Inbox/PaperPipe/canonical-note.md",
        id="zotero:same-paper",
        structured_state_present=True,
        ops_summary=PaperNoteOpsSummary(
            state="healthy",
            label="Healthy",
            reason="Saved claims and note checks are available. 2 checks are ready.",
            recommended_action="none",
            latest_run_id="run_healthy_001",
            has_claimset=True,
            has_stats_report=True,
            stats_check_count=2,
        ),
    )
    legacy = PaperNoteIndexItem(
        slug="legacy-note",
        title="Same paper",
        note_path="Inbox/PaperPipe/legacy-note.md",
        id="same-paper",
        ops_summary=PaperNoteOpsSummary(
            state="action_needed",
            label="Action needed",
            reason="Saved note checks are missing or empty.",
            recommended_action="repair_stats",
            latest_run_id="run_repair_001",
            has_claimset=True,
            has_stats_report=False,
            stats_check_count=0,
        ),
    )

    _write_artifact_run(
        artifacts_dir / "legacy-note" / "run_repair_001",
        claimset={"claims": [{"claim_id": "c1"}]},
    )
    _write_artifact_run(
        artifacts_dir / "zotero:same-paper" / "run_healthy_001",
        claimset={"claims": [{"claim_id": "c1"}]},
        stats_report={"checks": [{"id": "check-1"}, {"id": "check-2"}]},
    )

    merged = paper_notes_router._dedupe_equivalent_note_items_with_ops(
        [canonical, legacy],
        artifacts_path=artifacts_dir,
        artifact_cache={},
    )

    assert len(merged) == 1
    assert merged[0].slug == "canonical-note"
    assert merged[0].id == "zotero:same-paper"
    assert merged[0].ops_summary is not None
    assert merged[0].ops_summary.state == "healthy"
    assert merged[0].ops_summary.recommended_action == "none"
    assert merged[0].ops_summary.latest_run_id == "run_healthy_001"


def test_default_deduped_paper_note_items_recompute_ops_summary_from_artifacts_root(tmp_path, monkeypatch):
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setattr(paper_notes_router, "artifacts_root", lambda: artifacts_dir)

    canonical = PaperNoteIndexItem(
        slug="canonical-note",
        title="Same paper",
        note_path="Inbox/PaperPipe/canonical-note.md",
        id="zotero:same-paper",
        structured_state_present=True,
        ops_summary=PaperNoteOpsSummary(
            state="healthy",
            label="Healthy",
            reason="Saved claims and note checks are available. 2 checks are ready.",
            recommended_action="none",
            latest_run_id="run_healthy_stale",
            has_claimset=True,
            has_stats_report=True,
            stats_check_count=2,
        ),
    )
    legacy = PaperNoteIndexItem(
        slug="legacy-note",
        title="Same paper",
        note_path="Inbox/PaperPipe/legacy-note.md",
        id="same-paper",
        ops_summary=PaperNoteOpsSummary(
            state="action_needed",
            label="Action needed",
            reason="Saved note checks are missing or empty.",
            recommended_action="repair_stats",
            latest_run_id="run_repair_001",
            has_claimset=True,
            has_stats_report=False,
            stats_check_count=0,
        ),
    )

    _write_artifact_run(
        artifacts_dir / "legacy-note" / "run_repair_001",
        claimset={"claims": [{"claim_id": "c1"}]},
    )

    merged = paper_notes_router._dedupe_equivalent_note_items([canonical, legacy])

    assert len(merged) == 1
    assert merged[0].slug == "canonical-note"
    assert merged[0].id == "zotero:same-paper"
    assert merged[0].ops_summary is not None
    assert merged[0].ops_summary.state == "action_needed"
    assert merged[0].ops_summary.recommended_action == "repair_stats"
    assert merged[0].ops_summary.latest_run_id == "run_repair_001"


def test_dedupe_equivalent_note_items_prefers_real_variant_over_fixture_duplicate():
    fixture = PaperNoteIndexItem(
        slug="e2e-note-fixture-duplicate",
        title="E2E Note Fixture Duplicate",
        note_path="Inbox/PaperPipe/E2E Note Fixture Duplicate.md",
        id="same-note-duplicate",
    )
    real = PaperNoteIndexItem(
        slug="same-note-real-duplicate",
        title="Same Note Real Duplicate",
        note_path="Inbox/PaperPipe/Same Note Real Duplicate.md",
        id="same-note-duplicate",
    )

    merged = paper_notes_router._dedupe_equivalent_note_items_with_ops(
        [fixture, real],
        artifacts_path=None,
        artifact_cache={},
    )

    assert len(merged) == 1
    assert merged[0].slug == "same-note-real-duplicate"
    assert merged[0].title == "Same Note Real Duplicate"


def test_paper_note_operator_state_persists_and_drives_list_filters(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "operator-state-note"
    paper_id = "zotero:operator-state-note"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id=paper_id,
            alias="Operator State Fixture",
            tags=["Medicine/Neurology", "Review"],
            date_processed="2026-04-10",
            confidence=0.82,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)

    initial = client.get(f"/paper-notes/{slug}/operator-state")
    assert initial.status_code == 200
    initial_payload = initial.json()
    assert initial_payload["note_slug"] == slug
    assert initial_payload["paper_id"] == paper_id
    assert initial_payload["starred"] is False
    assert initial_payload["paper_note_text"] is None
    assert initial_payload["triage_labels"] == []

    updated = client.put(
        f"/paper-notes/{slug}/operator-state",
        json={
            "paper_note_text": "  Needs a second pass before downstream reuse.  ",
            "starred": True,
            "triage_labels": ["needs_verification", "revisit", "needs_verification"],
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["paper_note_text"] == "Needs a second pass before downstream reuse."
    assert updated_payload["starred"] is True
    assert updated_payload["triage_labels"] == ["revisit", "needs_verification"]
    assert updated_payload["created_at"] is not None
    assert updated_payload["updated_at"] is not None

    fetched = client.get(f"/paper-notes/{slug}/operator-state")
    assert fetched.status_code == 200
    assert fetched.json()["triage_labels"] == ["revisit", "needs_verification"]

    listing = client.get("/paper-notes", params={"starred": "true"})
    assert listing.status_code == 200
    list_payload = listing.json()
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["slug"] == slug
    assert list_payload["items"][0]["starred"] is True
    assert list_payload["items"][0]["has_operator_note"] is True
    assert list_payload["items"][0]["triage_labels"] == ["revisit", "needs_verification"]

    triage_listing = client.get("/paper-notes", params={"triage_label": "needs_verification"})
    assert triage_listing.status_code == 200
    assert triage_listing.json()["items"][0]["slug"] == slug

    resolved = client.get("/paper-notes/resolve-by-paper-id", params={"paper_id": paper_id})
    assert resolved.status_code == 200
    resolved_payload = resolved.json()
    assert resolved_payload["operator_state"]["starred"] is True
    assert resolved_payload["operator_state"]["triage_labels"] == ["revisit", "needs_verification"]

    detail = client.get(f"/paper-notes/{slug}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["note"]["starred"] is True
    assert detail_payload["note"]["has_operator_note"] is True
    assert detail_payload["note"]["triage_labels"] == ["revisit", "needs_verification"]
    assert detail_payload["operator_state"]["paper_note_text"] == "Needs a second pass before downstream reuse."


def test_paper_note_operator_state_sanitizes_secret_like_note_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "operator-state-secret-note"
    paper_id = "zotero:operator-state-secret-note"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id=paper_id,
            alias="Operator State Secret Fixture",
            tags=["Review"],
            date_processed="2026-04-10",
            confidence=0.82,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    raw_text = (
        "Do not keep Authorization: Bearer operator-note-token-123; "
        "key=sk-proj-operator-note-secret-abcdef."
    )
    updated = client.put(
        f"/paper-notes/{slug}/operator-state",
        json={
            "paper_note_text": raw_text,
            "starred": True,
            "triage_labels": ["revisit"],
        },
    )
    assert updated.status_code == 200
    safe_text = "Do not keep Authorization: <redacted>; key=<redacted>."
    assert updated.json()["paper_note_text"] == safe_text

    state_path = operator_state_path(vault_dir, slug, paper_id)
    raw_file = state_path.read_text(encoding="utf-8")
    assert "operator-note-token-123" not in raw_file
    assert "sk-proj-operator-note-secret-abcdef" not in raw_file

    fetched = client.get(f"/paper-notes/{slug}/operator-state")
    assert fetched.status_code == 200
    assert fetched.json()["paper_note_text"] == safe_text

    detail = client.get(f"/paper-notes/{slug}")
    assert detail.status_code == 200
    assert detail.json()["operator_state"]["paper_note_text"] == safe_text


def test_paper_note_operator_state_sanitizes_legacy_raw_note_text(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "operator-state-legacy-secret-note"
    paper_id = "zotero:operator-state-legacy-secret-note"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id=paper_id,
            alias="Operator State Legacy Secret Fixture",
            tags=["Review"],
            date_processed="2026-04-10",
            confidence=0.82,
            status="INDEXED",
        ),
    )
    state_path = operator_state_path(vault_dir, slug, paper_id)
    _write_state(
        state_path,
        {
            "note_slug": slug,
            "paper_id": paper_id,
            "layer": "raw_memory",
            "canonical_status": "non_canonical",
            "paper_note_text": "Legacy Authorization: Bearer legacy-operator-note-token-123",
            "starred": True,
            "triage_labels": ["revisit"],
            "created_at": "2026-04-10T00:00:00Z",
            "updated_at": "2026-04-10T00:00:00Z",
        },
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    fetched = client.get(f"/paper-notes/{slug}/operator-state")
    assert fetched.status_code == 200
    assert fetched.json()["paper_note_text"] == "Legacy Authorization: <redacted>"


def test_paper_note_operator_state_survives_slug_to_paper_id_transition(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "operator-state-transition-note"
    paper_id = "zotero:operator-state-transition-note"
    note_path = vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md"
    _write(
        note_path,
        (
            "---\n"
            'aliases: ["Operator State Transition Fixture"]\n'
            "tags:\n"
            "  - Review\n"
            "date_processed: 2026-04-10\n"
            "confidence: 0.82\n"
            "status: INDEXED\n"
            "---\n\n"
            "# Operator State Transition Fixture\n"
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    updated = client.put(
        f"/paper-notes/{slug}/operator-state",
        json={
            "paper_note_text": "Preserve this note across id assignment.",
            "starred": True,
            "triage_labels": ["revisit"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["paper_id"] == slug

    _write(
        note_path,
        (
            "---\n"
            f"id: {paper_id}\n"
            'aliases: ["Operator State Transition Fixture"]\n'
            "tags:\n"
            "  - Review\n"
            "date_processed: 2026-04-10\n"
            "confidence: 0.82\n"
            "status: INDEXED\n"
            "---\n\n"
            "# Operator State Transition Fixture\n"
        ),
    )

    fetched = client.get(f"/paper-notes/{slug}/operator-state")
    assert fetched.status_code == 200
    fetched_payload = fetched.json()
    assert fetched_payload["paper_id"] == paper_id
    assert fetched_payload["paper_note_text"] == "Preserve this note across id assignment."
    assert fetched_payload["starred"] is True
    assert fetched_payload["triage_labels"] == ["revisit"]

    resolved = client.get("/paper-notes/resolve-by-paper-id", params={"paper_id": paper_id})
    assert resolved.status_code == 200
    assert resolved.json()["operator_state"]["paper_note_text"] == "Preserve this note across id assignment."


def test_paper_note_detail_renders_properties_related_and_references(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_MASK_LOCAL_PATHS", "false")
    monkeypatch.delenv("PAPERPIPE_MASK_LOCAL_PATHS", raising=False)

    vault_dir = tmp_path / "vault"
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "zoteroduboisAlzheimerDiseaseClinicalBiological2024.md",
        _note_content(
            note_id="zotero:duboisAlzheimerDiseaseClinicalBiological2024",
            alias="Alzheimer Disease as a Clinical-Biological Construct—An International Working Group Recommendation",
            tags=["Medicine/Neurology", "Alzheimers_Disease"],
            date_processed="2026-02-24",
            confidence=0.9,
            status="INDEXED",
            related_slug="zoteroduboisAmnesticMCIProdromal2004",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "zoteroduboisAmnesticMCIProdromal2004.md",
        _note_content(
            note_id="zotero:duboisAmnesticMCIProdromal2004",
            alias="Amnestic MCI or prodromal Alzheimer's disease?",
            tags=["Medicine/Neurology", "Alzheimers_Disease"],
            date_processed="2026-02-20",
            confidence=0.8,
            status="INDEXED",
        ),
    )
    _write_artifact_run(
        artifacts_dir / "zotero:duboisAlzheimerDiseaseClinicalBiological2024" / "run_001",
        claimset={"doc_id": "zotero:duboisAlzheimerDiseaseClinicalBiological2024", "claims": [{"claim_id": "CLM-1"}]},
        stats_report={"doc_id": "zotero:duboisAlzheimerDiseaseClinicalBiological2024", "run_id": "run_001", "checks": [{"check_id": "CHK-1"}]},
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/zoteroduboisAlzheimerDiseaseClinicalBiological2024")
    assert response.status_code == 200

    payload = response.json()
    assert payload["note"]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"
    assert payload["note"]["ops_summary"]["state"] == "healthy"
    assert payload["frontmatter"]["status"] == "INDEXED"
    assert "One-Line Summary" in payload["body_markdown"]
    assert "## 🔗 Related Papers" not in payload["body_markdown"]
    assert "/papers/zoteroduboisAmnesticMCIProdromal2004" in payload["body_markdown"]

    assert len(payload["related"]) == 1
    assert payload["related"][0]["slug"] == "zoteroduboisAmnesticMCIProdromal2004"
    assert "Medicine/Neurology" in payload["related"][0]["shared_tags"]

    assert len(payload["references"]) >= 1
    assert payload["references"][0]["source"] == "pdf"
    assert payload["references"][0]["label"] == "Open PDF"
    assert payload["context_trace"]["available"] is True
    assert payload["context_trace"]["summary"]["entry_count"] == 5
    assert payload["context_trace"]["summary"]["related_count"] == 1
    assert payload["context_trace"]["summary"]["reference_count"] >= 1
    assert payload["context_trace"]["summary"]["related_slugs"] == [
        "zoteroduboisAmnesticMCIProdromal2004"
    ]
    assert payload["context_trace"]["summary"]["reference_sources"] == ["pdf", "doi"]
    assert [entry["action"] for entry in payload["context_trace"]["trace"]] == [
        "note_loaded",
        "body_sections_filtered",
        "references_resolved",
        "related_computed",
        "structured_state_loaded",
    ]
    assert payload["context_trace"]["trace"][-1]["outcome"] == "missing"
    assert payload["context_trace"]["trace"][-1]["source_path"] == (
        ".pp/zoteroduboisAlzheimerDiseaseClinicalBiological2024/state.json"
    )
    assert payload["section_navigator"] == []


def test_paper_note_detail_backfills_structured_state_ids_and_signals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_MASK_LOCAL_PATHS", "false")
    monkeypatch.delenv("PAPERPIPE_MASK_LOCAL_PATHS", raising=False)

    vault_dir = tmp_path / "vault"
    slug = "stateful-note"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id="zotero:stateful",
            alias="Stateful Note",
            tags=["Tag/Stateful", "Outcome/Memory"],
            date_processed="2026-03-09",
            confidence=0.91,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / slug / "state.json",
        {
            "paper_slug": slug,
            "updated_at": "2026-03-09T00:00:00Z",
            "runs": [
                {
                    "id": "skill-20260309T000000Z-critical_appraisal",
                    "action": "critical_appraisal",
                    "ts": "2026-03-09T00:00:00Z",
                    "status": "succeeded",
                    "summary": "ClaimSet extracted",
                    "artifacts": {},
                    "data": {},
                }
            ],
            "claimset": [
                {
                    "id": "CLM-001",
                    "claim": "Structured state claims can keep stable deep links.",
                    "evidence": [
                        {
                            "text": "Stable IDs help future chat references point to exact evidence.",
                            "page": 2,
                            "section": "Results",
                            "source": "text_match",
                        }
                    ],
                    "confidence": 0.88,
                    "tags": ["methods"],
                    "outcomes": ["methods"],
                }
            ],
            "entities": ["Memory"],
            "mesh": ["Knowledge Graphs"],
            "outcomes": ["methods"],
        },
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get(f"/paper-notes/{slug}")
    assert response.status_code == 200
    payload = response.json()

    state = payload["structured_state"]
    assert state["schema_version"] == "2026-03-09.chat-hooks.v1"
    assert state["signals"]["has_claimset"] is True
    assert state["signals"]["claim_count"] == 1
    assert state["signals"]["evidence_count"] == 1
    assert state["signals"]["run_count"] == 1
    assert state["signals"]["section_count"] == 1
    assert state["signals"]["quality_gate_section_navigation_signal"] == "pass"
    assert state["signals"]["last_run_id"] == "skill-20260309T000000Z-critical_appraisal"
    assert payload["context_trace"]["summary"]["reference_sources"] == ["pdf", "doi"]
    assert payload["context_trace"]["trace"][-1]["action"] == "structured_state_loaded"
    assert payload["context_trace"]["trace"][-1]["outcome"] == "loaded"
    assert payload["context_trace"]["trace"][-1]["source_path"] == ".pp/stateful-note/state.json"
    assert payload["context_trace"]["trace"][-1]["metadata"]["run_count"] == 1
    assert payload["context_trace"]["trace"][-1]["metadata"]["has_claimset"] is True

    claim = state["claimset"][0]
    assert claim["id"] == "CLM-001"
    assert claim["evidence_ids"][0].startswith("evidence_")
    evidence = claim["evidence"][0]
    assert evidence["claim_id"] == "CLM-001"
    assert evidence["locator"]["page"] == 2
    assert evidence["locator"]["section"] == "Results"
    assert state["runs"][0]["data"]["section_count"] == 1
    assert state["runs"][0]["data"]["section_navigation_signal_status"] == "pass"
    assert state["runs"][0]["data"]["section_navigation_signal_detail"] == "claimset_section_count=1, summary_present=true"
    assert state["runs"][0]["data"]["section_summary"] == [
        {
            "key": "results",
            "label": "Results",
            "claim_count": 1,
            "evidence_count": 1,
            "representative_claim_id": "CLM-001",
            "representative_evidence_id": evidence["id"],
            "page_start": 2,
            "page_end": 2,
        }
    ]
    assert payload["section_navigator"] == [
        {
            "key": "results",
            "label": "Results",
            "outline_id": None,
            "outline_order": None,
            "claim_count": 1,
            "evidence_count": 1,
            "representative_claim_id": "CLM-001",
            "representative_evidence_id": evidence["id"],
            "page_start": 2,
            "page_end": 2,
            "matched_to_outline": False,
        }
    ]
    assert len(payload["available_actions"]) >= 1
    assert all(action["enabled"] is False for action in payload["available_actions"])


def test_paper_note_detail_section_navigator_prefers_note_heading_match(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "section-match-note"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        "\n".join(
            [
                "---",
                "id: zotero:section-match-note",
                'aliases: ["Section Match Note"]',
                "tags:",
                "  - Tag/One",
                "date_processed: 2026-03-09",
                "confidence: 0.91",
                "status: INDEXED",
                "---",
                "",
                "# Section Match Note",
                "",
                "## Results",
                "Result section body.",
                "",
                "## Discussion",
                "Discussion section body.",
                "",
                "## 🔗 References",
                "* [Open PDF](file:///Users/test/Documents/private.pdf)",
                "",
            ]
        ),
    )
    _write_state(
        vault_dir / ".pp" / slug / "state.json",
        {
            "paper_slug": slug,
            "updated_at": "2026-03-09T00:00:00Z",
            "runs": [],
            "claimset": [
                {
                    "id": "CLM-RESULTS",
                    "claim": "Result headings should reconnect saved evidence to note sections.",
                    "evidence": [
                        {
                            "id": "EV-RESULTS",
                            "text": "The saved evidence belongs under the Results heading.",
                            "page": 1,
                            "section": "Results",
                            "source": "text_match",
                        }
                    ],
                    "confidence": 0.88,
                    "tags": ["results"],
                    "outcomes": ["results"],
                }
            ],
            "entities": [],
            "mesh": [],
            "outcomes": [],
        },
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get(f"/paper-notes/{slug}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["section_navigator"] == [
        {
            "key": "results",
            "label": "Results",
            "outline_id": "results",
            "outline_order": 0,
            "claim_count": 1,
            "evidence_count": 1,
            "representative_claim_id": "CLM-RESULTS",
            "representative_evidence_id": "EV-RESULTS",
            "page_start": 1,
            "page_end": 1,
            "matched_to_outline": True,
        }
    ]


def test_paper_note_detail_exposes_korean_reading_assist_from_structured_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LATTICE_MASK_LOCAL_PATHS", raising=False)
    monkeypatch.delenv("PAPERPIPE_MASK_LOCAL_PATHS", raising=False)

    vault_dir = tmp_path / "vault"
    slug = "reading-assist-note"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        "\n".join(
            [
                "---",
                "id: zotero:reading-assist-note",
                'aliases: ["Reading Assist Note"]',
                "tags:",
                "  - Medicine/Neurology",
                "date_processed: 2026-03-11",
                "confidence: 0.92",
                "status: INDEXED",
                "---",
                "",
                "# Reading Assist Note",
                "",
                "> **One-Line Summary**",
                "> Canonical one-line summary for the detail viewer.",
                "",
                "## Abstract",
                "Canonical abstract text remains the source of truth for this note.",
                "",
                "## Critical Analysis",
                "- Canonical critical analysis stays in English.",
                "- Evidence judgment should still happen against the original source.",
                "",
                "## 🔗 References",
                "* [Open PDF](file:///Users/test/Documents/private.pdf)",
                "",
            ]
        ),
    )
    _write_state(
        vault_dir / ".pp" / slug / "state.json",
        {
            "paper_slug": slug,
            "updated_at": "2026-03-11T09:00:00Z",
            "runs": [],
            "claimset": [],
            "entities": [],
            "mesh": [],
            "outcomes": [],
            "reading_assists": [
                {
                    "locale": "ko",
                    "canonical_locale": "en",
                    "machine_translated": True,
                    "partial": True,
                    "blocks": [
                        {
                            "kind": "one_line_summary",
                            "text": "디테일 뷰를 위한 핵심 한 줄 요약이다.",
                            "source_heading": "One-Line Summary",
                            "provenance": {
                                "source_field": "one_line_summary",
                                "source_locale": "en",
                                "translator": "unit-test",
                                "model": "mock-translator",
                                "version": "v1",
                            },
                        },
                        {
                            "kind": "abstract",
                            "text": "이 노트는 원문 영어를 정본으로 유지한 채 한국어 보조만 제공한다.",
                            "source_heading": "Abstract",
                            "provenance": {
                                "source_field": "abstract",
                                "source_locale": "en",
                            },
                        },
                        {
                            "kind": "critical_analysis",
                            "text": "비판적 해석은 읽기 보조로만 제공되고, 근거 판단은 원문에서 해야 한다.",
                            "source_heading": "Critical Analysis",
                            "provenance": {
                                "source_field": "critical_analysis",
                                "source_locale": "en",
                            },
                        },
                    ],
                },
                {
                    "locale": "ja",
                    "canonical_locale": "en",
                    "machine_translated": True,
                    "partial": True,
                    "blocks": [
                        {
                            "kind": "one_line_summary",
                            "text": "詳細ビュー向けの重要な一文要約です。",
                            "source_heading": "One-Line Summary",
                            "provenance": {
                                "source_field": "one_line_summary",
                                "source_locale": "en",
                                "translator": "unit-test-ja",
                                "model": "mock-translator-ja",
                                "version": "v2",
                            },
                        },
                        {
                            "kind": "abstract",
                            "text": "このノートは英語原文を正本として維持し、日本語の読書補助だけを提供します。",
                            "source_heading": "Abstract",
                            "provenance": {
                                "source_field": "abstract",
                                "source_locale": "en",
                            },
                        },
                        {
                            "kind": "critical_analysis",
                            "text": "批判的解釈は読書補助に限られ、根拠判断は原文で行うべきです。",
                            "source_heading": "Critical Analysis",
                            "provenance": {
                                "source_field": "critical_analysis",
                                "source_locale": "en",
                            },
                        },
                    ],
                }
            ],
        },
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get(f"/paper-notes/{slug}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["reading_assist"]["locale"] == "ko"
    assert payload["reading_assist"]["canonical_locale"] == "en"
    assert payload["reading_assist"]["machine_translated"] is True
    assert payload["reading_assist"]["partial"] is True
    assert [block["kind"] for block in payload["reading_assist"]["blocks"]] == [
        "one_line_summary",
        "abstract",
        "critical_analysis",
    ]
    assert payload["reading_assist"]["blocks"][0]["canonical_text"] == "Canonical one-line summary for the detail viewer."
    assert payload["reading_assist"]["blocks"][0]["translated_text"] == "디테일 뷰를 위한 핵심 한 줄 요약이다."
    assert payload["reading_assist"]["blocks"][1]["canonical_text"] == (
        "Canonical abstract text remains the source of truth for this note."
    )
    assert "Canonical critical analysis stays in English." in payload["reading_assist"]["blocks"][2]["canonical_text"]
    assert payload["structured_state"]["reading_assists"][0]["locale"] == "ko"
    assert payload["structured_state"]["signals"]["has_reading_assists"] is True
    assert payload["structured_state"]["signals"]["reading_assist_count"] == 2
    assert payload["structured_state"]["signals"]["reading_assist_locales"] == ["ko", "ja"]
    assert payload["note"]["reading_assist_available"] is True
    assert payload["note"]["reading_assist_locales"] == ["ko", "ja"]

    japanese = client.get(f"/paper-notes/{slug}", params={"reading_assist_locale": "ja"})
    assert japanese.status_code == 200
    japanese_payload = japanese.json()
    assert japanese_payload["reading_assist"]["locale"] == "ja"
    assert japanese_payload["reading_assist"]["blocks"][0]["translated_text"] == "詳細ビュー向けの重要な一文要約です。"

    listing = client.get("/paper-notes")
    assert listing.status_code == 200
    listing_payload = listing.json()
    matching = next(item for item in listing_payload["items"] if item["slug"] == slug)
    assert matching["pp_signals"]["has_reading_assists"] is True
    assert matching["pp_signals"]["reading_assist_locales"] == ["ko", "ja"]


def test_paper_note_resolve_by_paper_id_prefers_frontmatter_id_and_returns_structured_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "zoteroduboisAlzheimerDiseaseClinicalBiological2024"
    paper_id = "zotero:duboisAlzheimerDiseaseClinicalBiological2024"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id=paper_id,
            alias="Dubois Structured Note",
            tags=["Medicine/Neurology"],
            date_processed="2026-03-10",
            confidence=0.93,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / slug / "state.json",
        {
            "paper_slug": slug,
            "updated_at": "2026-03-10T09:00:00Z",
            "runs": [],
            "signals": {"has_claimset": True},
            "claimset": [
                {
                    "id": "claim-structured-001",
                    "claim": "Structured sidecar should win over stale artifact claimsets for bbox-backed highlighting.",
                    "evidence_ids": ["evidence-structured-001"],
                    "evidence": [
                        {
                            "id": "evidence-structured-001",
                            "claim_id": "claim-structured-001",
                            "text": "BBox-backed evidence from canonical state.",
                            "page": 0,
                            "source": "bbox",
                            "locator": {
                                "page": 0,
                                "span": [0, 41],
                                "bbox_pct": {"left": 8, "top": 10, "width": 40, "height": 20},
                                "source": "bbox",
                            },
                        }
                    ],
                    "confidence": 0.9,
                    "tags": ["bbox"],
                    "outcomes": ["diagnostic criteria"],
                }
            ],
            "entities": ["Amyloid"],
            "mesh": ["Neurology"],
            "outcomes": ["diagnostic criteria"],
        },
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/resolve-by-paper-id", params={"paper_id": paper_id})
    assert response.status_code == 200
    payload = response.json()

    assert payload["paper_id"] == paper_id
    assert payload["slug"] == slug
    assert payload["note_path"] == f"Inbox/PaperPipe/{slug}.md"
    assert payload["note"]["slug"] == slug
    assert payload["note"]["title"] == "Dubois Structured Note"
    assert payload["doi_url"] == "https://doi.org/10.1000/182"
    assert payload["structured_state"]["paper_slug"] == slug
    assert payload["structured_state"]["claimset"][0]["evidence"][0]["locator"]["bbox_pct"]["left"] == 8


def test_paper_note_resolve_by_paper_id_exposes_pdf_url_for_lookup_synthesis(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "lookupPdfUrlNote2026"
    paper_id = "lookupPdfUrlNote2026"
    pdf_url = f"/papers/{quote(paper_id, safe='')}/pdf"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id=paper_id,
            alias="Lookup PDF URL Note",
            tags=["Medicine/Neurology"],
            date_processed="2026-03-10",
            confidence=0.91,
            status="INDEXED",
            doi="10.1000/lookup-pdf-url-note",
            pdf_url=pdf_url,
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/resolve-by-paper-id", params={"paper_id": paper_id})
    assert response.status_code == 200
    payload = response.json()

    assert payload["paper_id"] == paper_id
    assert payload["slug"] == slug
    assert payload["pdf_url"] == pdf_url
    assert payload["doi_url"] == "https://doi.org/10.1000/lookup-pdf-url-note"
    assert payload["note"]["slug"] == slug
    assert payload["note"]["title"] == "Lookup PDF URL Note"
    assert payload["note"]["status"] == "INDEXED"


def test_paper_note_resolve_by_paper_id_accepts_stripped_id_for_prefixed_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "zoterostrippedlookupnote2026"
    paper_id = "zotero:strippedlookupnote2026"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id=paper_id,
            alias="Stripped Lookup Note",
            tags=["Medicine/Neurology"],
            date_processed="2026-03-10",
            confidence=0.91,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / slug / "state.json",
        {
            "paper_slug": slug,
            "updated_at": "2026-03-10T09:00:00Z",
            "runs": [],
            "signals": {"has_claimset": True},
            "claimset": [],
            "entities": ["Amyloid"],
            "mesh": ["Neurology"],
            "outcomes": ["diagnostic criteria"],
        },
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/resolve-by-paper-id", params={"paper_id": "strippedlookupnote2026"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["paper_id"] == paper_id
    assert payload["slug"] == slug
    assert payload["structured_state"]["paper_slug"] == slug


def test_paper_notes_list_hides_fixture_like_structured_state_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "fixture-hidden-note"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id="zotero:fixture-hidden-note",
            alias="Fixture Hidden Note",
            tags=["Ops/Fix"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
        ),
    )
    _write_state(vault_dir / ".pp" / slug / "state.json", _fixture_structured_state(slug))

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes")
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 1
    assert payload["items"][0]["slug"] == slug
    assert payload["items"][0]["structured_state_present"] is False
    assert payload["items"][0]["claim_tags"] == []

    structured_only = client.get("/paper-notes", params={"structured_only": "true"})
    assert structured_only.status_code == 200
    assert structured_only.json()["total"] == 0


def test_paper_note_resolve_by_paper_id_hides_fixture_like_structured_state_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "fixture-hidden-note"
    paper_id = "zotero:fixture-hidden-note"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id=paper_id,
            alias="Fixture Hidden Note",
            tags=["Ops/Fix"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
        ),
    )
    _write_state(vault_dir / ".pp" / slug / "state.json", _fixture_structured_state(slug))

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/resolve-by-paper-id", params={"paper_id": paper_id})
    assert response.status_code == 200
    payload = response.json()

    assert payload["paper_id"] == paper_id
    assert payload["slug"] == slug
    assert payload["structured_state"] is None


def test_paper_note_resolve_by_paper_id_returns_bounded_error_when_config_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paper_id = "zotero:missing-config-note"

    def _raise_missing_config():
        raise FileNotFoundError("Config file not found at /tmp/missing-config.yaml")

    monkeypatch.setattr(paper_notes_router, "load_config", _raise_missing_config)

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/resolve-by-paper-id", params={"paper_id": paper_id})

    assert response.status_code == 503
    assert "Config file not found" in response.json()["detail"]


def test_paper_note_detail_hides_fixture_like_structured_state_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    slug = "fixture-hidden-note"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id="zotero:fixture-hidden-note",
            alias="Fixture Hidden Note",
            tags=["Ops/Fix"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
        ),
    )
    _write_state(vault_dir / ".pp" / slug / "state.json", _fixture_structured_state(slug))

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get(f"/paper-notes/{slug}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["note"]["slug"] == slug
    assert payload["note"]["structured_state_present"] is False
    assert payload["structured_state"] is None
    assert payload["reading_assist"] is None
    assert payload["context_trace"]["trace"][-1]["action"] == "structured_state_loaded"
    assert payload["context_trace"]["trace"][-1]["outcome"] == "missing"


def test_paper_note_detail_allows_fixture_like_structured_state_in_e2e_runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "frontend" / ".e2e-backend-runtime" / "obsidian"
    slug = "fixture-e2e-note"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / f"{slug}.md",
        _note_content(
            note_id="zotero:fixture-e2e-note",
            alias="Fixture E2E Note",
            tags=["Ops/Fix"],
            date_processed="2026-03-10",
            confidence=0.7,
            status="INDEXED",
        ),
    )
    _write_state(vault_dir / ".pp" / slug / "state.json", _fixture_structured_state(slug))

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get(f"/paper-notes/{slug}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["note"]["slug"] == slug
    assert payload["note"]["structured_state_present"] is True
    assert payload["structured_state"]["paper_slug"] == slug
    assert payload["context_trace"]["trace"][-1]["outcome"] == "loaded"


def test_paper_notes_list_supports_status_filter_and_sorting(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-alpha.md",
        _note_content(
            note_id="zotero:alpha",
            alias="Alpha Note",
            tags=["Tag/Shared"],
            date_processed="2026-01-01",
            confidence=0.95,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-beta.md",
        _note_content(
            note_id="zotero:beta",
            alias="Beta Note",
            tags=["Tag/Other"],
            date_processed="2026-03-01",
            confidence=0.55,
            status="REVIEW",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-gamma.md",
        _note_content(
            note_id="zotero:gamma",
            alias="Gamma Note",
            tags=["Tag/Shared"],
            date_processed="2026-02-01",
            confidence=0.8,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )
    client = TestClient(api_main.app)

    confidence_sorted = client.get(
        "/paper-notes",
        params={"status": "INDEXED", "sort_by": "confidence", "sort_order": "asc"},
    )
    assert confidence_sorted.status_code == 200
    confidence_payload = confidence_sorted.json()
    assert confidence_payload["total"] == 2
    assert [item["slug"] for item in confidence_payload["items"]] == ["note-gamma", "note-alpha"]

    date_sorted = client.get("/paper-notes", params={"sort_by": "date_processed", "sort_order": "asc"})
    assert date_sorted.status_code == 200
    date_payload = date_sorted.json()
    assert [item["slug"] for item in date_payload["items"][:3]] == ["note-alpha", "note-gamma", "note-beta"]


def test_paper_notes_default_sort_prioritizes_saved_state_with_richer_claims(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "fixture-live.md",
        _note_content(
            note_id="zotero:fixture-live",
            alias="Live Validate Citations Fixture",
            tags=["Ops/Fix"],
            date_processed="2026-03-09",
            confidence=0.6,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / "fixture-live" / "state.json",
        {
            "paper_slug": "fixture-live",
            "updated_at": "2026-03-09T00:00:00Z",
            "runs": [],
            "signals": {},
            "claimset": [],
            "entities": [],
            "mesh": [],
            "outcomes": [],
        },
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "fixture-structured.md",
        _note_content(
            note_id="zotero:fixture-structured",
            alias="Structured Skills ClaimSet Fixture",
            tags=["Ops/Fix"],
            date_processed="2026-03-09",
            confidence=0.7,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / "fixture-structured" / "state.json",
        {
            "paper_slug": "fixture-structured",
            "updated_at": "2026-03-09T00:00:00Z",
            "runs": [],
            "signals": {},
            "claimset": [],
            "entities": [],
            "mesh": [],
            "outcomes": [],
        },
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "real-dubois.md",
        _note_content(
            note_id="zotero:real-dubois",
            alias="Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation",
            tags=["Medicine/Neurology"],
            date_processed="2026-02-24",
            confidence=0.8,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / "real-dubois" / "state.json",
        {
            "paper_slug": "real-dubois",
            "updated_at": "2026-03-09T07:53:10Z",
            "runs": [],
            "signals": {"claim_count": 2},
            "claimset": [
                {"id": "claim-001", "claim": "Claim one", "evidence": [], "evidence_ids": []},
                {"id": "claim-002", "claim": "Claim two", "evidence": [], "evidence_ids": []},
            ],
            "entities": ["Amyloid"],
            "mesh": ["Neurology"],
            "outcomes": ["memory"],
        },
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "real-coric.md",
        _note_content(
            note_id="zotero:real-coric",
            alias="Targeting Prodromal Alzheimer Disease With Avagacestat: A Randomized Clinical Trial",
            tags=["Medicine/Neurology"],
            date_processed="2026-02-24",
            confidence=0.8,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / "real-coric" / "state.json",
        {
            "paper_slug": "real-coric",
            "updated_at": "2026-03-24T14:40:55Z",
            "runs": [],
            "signals": {"claim_count": 4},
            "claimset": [
                {"id": "claim-001", "claim": "Claim one", "evidence": [], "evidence_ids": []},
                {"id": "claim-002", "claim": "Claim two", "evidence": [], "evidence_ids": []},
                {"id": "claim-003", "claim": "Claim three", "evidence": [], "evidence_ids": []},
                {"id": "claim-004", "claim": "Claim four", "evidence": [], "evidence_ids": []},
            ],
            "entities": ["Amyloid"],
            "mesh": ["Neurology"],
            "outcomes": ["progression"],
        },
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )
    client = TestClient(api_main.app)

    response = client.get("/paper-notes", params={"page_size": 10})
    assert response.status_code == 200
    payload = response.json()

    assert [item["slug"] for item in payload["items"][:4]] == [
        "real-coric",
        "real-dubois",
        "fixture-structured",
        "fixture-live",
    ]


def test_paper_notes_list_supports_multi_tag_filter_and_pagination(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-one.md",
        _note_content(
            note_id="zotero:one",
            alias="Note One",
            tags=["A"],
            date_processed="2026-01-01",
            confidence=0.1,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-two.md",
        _note_content(
            note_id="zotero:two",
            alias="Note Two",
            tags=["B"],
            date_processed="2026-01-02",
            confidence=0.2,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "note-three.md",
        _note_content(
            note_id="zotero:three",
            alias="Note Three",
            tags=["A", "B"],
            date_processed="2026-01-03",
            confidence=0.3,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )
    client = TestClient(api_main.app)

    response = client.get(
        "/paper-notes",
        params={
            "tags": "A,B",
            "sort_by": "date_processed",
            "sort_order": "desc",
            "page": 2,
            "page_size": 1,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 3
    assert payload["page"] == 2
    assert payload["page_size"] == 1
    assert payload["total_pages"] == 3
    assert len(payload["items"]) == 1
    assert payload["items"][0]["slug"] == "note-two"
    assert sorted(payload["available_tags"]) == ["A", "B"]
    assert payload["available_statuses"] == ["INDEXED"]


def test_paper_note_detail_related_limit_and_scoring(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "target-note.md",
        _note_content(
            note_id="zotero:target",
            alias="Target Note",
            tags=["A", "B", "C"],
            date_processed="2026-02-28",
            confidence=0.7,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "triple-match.md",
        _note_content(
            note_id="zotero:triple",
            alias="Triple Match",
            tags=["A", "B", "C"],
            date_processed="2026-02-01",
            confidence=0.5,
            status="INDEXED",
        ),
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "double-match.md",
        _note_content(
            note_id="zotero:double",
            alias="Double Match",
            tags=["A", "B"],
            date_processed="2026-03-01",
            confidence=0.99,
            status="INDEXED",
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )
    client = TestClient(api_main.app)

    response = client.get("/paper-notes/target-note", params={"related_limit": 1})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["related"]) == 1
    assert payload["related"][0]["slug"] == "triple-match"
    assert payload["related"][0]["shared_tags"] == ["A", "B", "C"]


def test_paper_note_detail_related_scoring_uses_structured_signals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "target-structured.md",
        _note_content(
            note_id="zotero:target-structured",
            alias="Target Structured",
            tags=["Tag/Primary"],
            date_processed="2026-03-09",
            confidence=0.7,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / "target-structured" / "state.json",
        {
            "paper_slug": "target-structured",
            "updated_at": "2026-03-09T00:00:00Z",
            "runs": [],
            "claimset": [
                {
                    "id": "claim-target",
                    "claim": "Target structured claim",
                    "evidence": [{"text": "supporting evidence"}],
                    "tags": ["biomarker"],
                }
            ],
            "entities": ["Amyloid"],
            "mesh": ["Neurology"],
            "outcomes": ["memory"],
        },
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "structured-strong.md",
        _note_content(
            note_id="zotero:structured-strong",
            alias="Structured Strong",
            tags=["Tag/Secondary"],
            date_processed="2026-03-08",
            confidence=0.8,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / "structured-strong" / "state.json",
        {
            "paper_slug": "structured-strong",
            "updated_at": "2026-03-09T00:00:00Z",
            "runs": [],
            "claimset": [
                {
                    "id": "claim-strong",
                    "claim": "Strong overlap",
                    "evidence": [{"text": "overlap evidence"}],
                    "tags": ["biomarker"],
                }
            ],
            "entities": ["Amyloid"],
            "mesh": ["Neurology"],
            "outcomes": ["memory"],
        },
    )
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "structured-weak.md",
        _note_content(
            note_id="zotero:structured-weak",
            alias="Structured Weak",
            tags=["Tag/Secondary"],
            date_processed="2026-03-07",
            confidence=0.95,
            status="INDEXED",
        ),
    )
    _write_state(
        vault_dir / ".pp" / "structured-weak" / "state.json",
        {
            "paper_slug": "structured-weak",
            "updated_at": "2026-03-09T00:00:00Z",
            "runs": [],
            "claimset": [],
            "entities": ["Amyloid"],
            "mesh": [],
            "outcomes": [],
        },
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )
    client = TestClient(api_main.app)

    response = client.get("/paper-notes/target-structured", params={"related_limit": 2})
    assert response.status_code == 200
    payload = response.json()

    assert [item["slug"] for item in payload["related"]] == ["structured-strong", "structured-weak"]
    assert payload["related"][0]["shared_signals"] == ["Amyloid", "biomarker", "memory", "Neurology"]
    assert payload["related"][1]["shared_signals"] == ["Amyloid"]


def test_paper_note_detail_excludes_pdf_references_when_path_masking_enabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LATTICE_MASK_LOCAL_PATHS", "1")
    monkeypatch.delenv("PAPERPIPE_MASK_LOCAL_PATHS", raising=False)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "masked-note.md",
        _note_content(
            note_id="zotero:masked",
            alias="Masked Note",
            tags=["Tag/One"],
            date_processed="2026-02-24",
            confidence=0.9,
            status="INDEXED",
            doi="10.1016/S1474-4422(24)00001-2",
            zotero_link="zotero://select/items/1_ABCDE",
            pdf_url="file:///Users/test/Documents/private.pdf",
            reference_lines=[
                "* [Open PDF](file:///Users/test/Documents/private.pdf)",
                "* [Publisher Link](https://example.org/paper)",
            ],
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/masked-note")
    assert response.status_code == 200
    payload = response.json()

    sources = [item["source"] for item in payload["references"]]
    assert "pdf" not in sources
    assert "doi" in sources
    assert "zotero" in sources
    assert "external" in sources
    labels = [item["label"] for item in payload["references"]]
    assert "Open PDF" not in labels


def test_paper_note_detail_excludes_unsafe_reference_url_schemes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LATTICE_MASK_LOCAL_PATHS", raising=False)
    monkeypatch.delenv("PAPERPIPE_MASK_LOCAL_PATHS", raising=False)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "unsafe-link-note.md",
        _note_content(
            note_id="zotero:unsafe",
            alias="Unsafe Link Note",
            tags=["Tag/One"],
            date_processed="2026-02-24",
            confidence=0.9,
            status="INDEXED",
            doi=None,
            zotero_link=None,
            pdf_url="javascript:alert(1)",
            reference_lines=[
                "* [Bad Script](javascript:alert(1))",
                "* [Bad Data](data:text/html,hello)",
                "* [Good Publisher](https://example.org/safe)",
                "* [Good Local PDF](/papers/unsafe-link-note/pdf)",
                "* [Good Zotero](zotero://select/items/1_SAFE)",
            ],
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/unsafe-link-note")
    assert response.status_code == 200
    payload = response.json()

    labels = {item["label"] for item in payload["references"]}
    urls = {item["url"] for item in payload["references"]}
    assert "Bad Script" not in labels
    assert "Bad Data" not in labels
    assert "Good Publisher" in labels
    assert "Good Local PDF" in labels
    assert "Good Zotero" in labels
    assert all(not url.lower().startswith(("javascript:", "data:")) for url in urls)


def test_paper_note_detail_uses_doi_and_zotero_when_pdf_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LATTICE_MASK_LOCAL_PATHS", raising=False)
    monkeypatch.delenv("PAPERPIPE_MASK_LOCAL_PATHS", raising=False)

    vault_dir = tmp_path / "vault"
    _write(
        vault_dir / "Inbox" / "PaperPipe" / "fallback-note.md",
        _note_content(
            note_id="zotero:fallback",
            alias="Fallback Note",
            tags=["Tag/One"],
            date_processed="2026-02-24",
            confidence=0.9,
            status="INDEXED",
            doi="10.1038/fallback",
            zotero_link="zotero://select/items/1_FALLBACK",
            pdf_url=None,
            reference_lines=["* [Publisher Link](https://example.org/fallback)"],
        ),
    )

    monkeypatch.setattr(
        paper_notes_router,
        "load_config",
        lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
    )

    client = TestClient(api_main.app)
    response = client.get("/paper-notes/fallback-note")
    assert response.status_code == 200
    payload = response.json()

    sources = [item["source"] for item in payload["references"]]
    assert "pdf" not in sources
    assert "doi" in sources
    assert "zotero" in sources
