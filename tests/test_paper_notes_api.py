import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main as api_main
from backend.routers import paper_notes as paper_notes_router


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
    assert payload["items"][0]["slug"] == "zoteroduboisAlzheimerDiseaseClinicalBiological2024"
    assert payload["items"][0]["structured_state_present"] is True
    assert payload["items"][1]["structured_state_present"] is False
    assert (tmp_path / "storage" / "obsidian" / "paper_notes_index.json").exists()

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
    assert structured_payload["items"][0]["structured_state_present"] is True

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

    resolved = client.get(
        "/paper-notes/resolve-by-paper-id",
        params={"paper_id": "zotero:coricTargetingProdromalAlzheimer2015"},
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
    assert items["repair-note"]["ops_summary"]["reason"] == "Stats report is missing or empty."
    assert items["repair-note"]["ops_summary"]["recommended_action"] == "repair_stats"
    assert items["repair-note"]["ops_summary"]["latest_run_id"] == "run_repair_001"


def test_paper_note_detail_renders_properties_related_and_references(tmp_path, monkeypatch):
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


def test_paper_note_detail_backfills_structured_state_ids_and_signals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

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
    assert len(payload["available_actions"]) >= 1
    assert all(action["enabled"] is False for action in payload["available_actions"])


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
                    "id": "claim_c0ffee000001",
                    "claim": "Structured sidecar should win over stale artifact claimsets for bbox-backed highlighting.",
                    "evidence_ids": ["evidence_deadbeef0001"],
                    "evidence": [
                        {
                            "id": "evidence_deadbeef0001",
                            "claim_id": "claim_c0ffee000001",
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
    assert payload["structured_state"]["paper_slug"] == slug
    assert payload["structured_state"]["claimset"][0]["evidence"][0]["locator"]["bbox_pct"]["left"] == 8


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
