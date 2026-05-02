import json

from src.skills.storage import load_structured_state, resolve_note_path, resolve_note_slug_by_paper_id


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_resolve_note_path_supports_legacy_structured_slug_mapping(tmp_path):
    vault = tmp_path / "vault"
    legacy_slug = "zoterocoricTargetingProdromalAlzheimer2015"
    readable_stem = "Targeting Prodromal Alzheimer Disease With Avagacestat A Randomized Clinical Trial"
    note_path = vault / "Inbox" / "PaperPipe" / f"{readable_stem}.md"
    _write(
        note_path,
        "\n".join(
            [
                "---",
                "id: zotero:coricTargetingProdromalAlzheimer2015",
                f"aliases: [\"{readable_stem}\"]",
                "pp:",
                f"  structured_path: .pp/{legacy_slug}/state.json",
                "---",
                "",
                f"# {readable_stem}",
                "",
            ]
        ),
    )
    _write(
        vault / ".pp" / legacy_slug / "state.json",
        json.dumps(
            {
                "paper_slug": legacy_slug,
                "updated_at": "2026-03-28T00:00:00Z",
                "runs": [],
                "signals": {"has_claimset": True},
                "claimset": [],
                "entities": [],
                "mesh": [],
                "outcomes": [],
            }
        ),
    )

    assert resolve_note_path(vault, legacy_slug) == note_path

    frontmatter = {"pp": {"structured_path": f".pp/{legacy_slug}/state.json"}}
    state = load_structured_state(vault, readable_stem, frontmatter)
    assert state is not None
    assert state.paper_slug == legacy_slug


def test_resolve_note_path_ignores_backup_matches_for_legacy_slug(tmp_path):
    vault = tmp_path / "vault"
    legacy_slug = "zoterocoricTargetingProdromalAlzheimer2015"
    readable_stem = "Targeting Prodromal Alzheimer Disease With Avagacestat A Randomized Clinical Trial"
    active_note = vault / "Inbox" / "PaperPipe" / f"{readable_stem}.md"
    backup_note = vault / "_backup" / "PaperPipe" / f"{legacy_slug}.md"

    _write(
        active_note,
        "\n".join(
            [
                "---",
                "id: zotero:coricTargetingProdromalAlzheimer2015",
                f"aliases: [\"{readable_stem}\"]",
                "pp:",
                f"  structured_path: .pp/{legacy_slug}/state.json",
                "---",
                "",
                f"# {readable_stem}",
                "",
            ]
        ),
    )
    _write(backup_note, "# old backup note\n")

    assert resolve_note_path(vault, legacy_slug) == active_note


def test_resolve_note_slug_by_paper_id_ignores_hidden_fixture_state_preference(tmp_path):
    vault = tmp_path / "vault"
    fixture_note = vault / "Inbox" / "PaperPipe" / "aaa-fixture.md"
    real_note = vault / "Inbox" / "PaperPipe" / "real-note.md"

    _write(
        fixture_note,
        "\n".join(
            [
                "---",
                "id: doi:10.1000/abc",
                'aliases: ["Fixture Note"]',
                "---",
                "",
                "# Fixture Note",
                "",
            ]
        ),
    )
    _write(
        vault / ".pp" / "aaa-fixture" / "state.json",
        json.dumps(
            {
                "paper_slug": "aaa-fixture",
                "updated_at": "2026-03-28T00:00:00Z",
                "runs": [],
                "signals": {"has_claimset": True},
                "claimset": [
                    {
                        "id": "claim_c0ffee000001",
                        "source_claim_id": "e2e-claim-1",
                        "claim": "Fixture claim.",
                        "evidence_ids": ["evidence_deadbeef0001"],
                        "evidence": [
                            {
                                "id": "evidence_deadbeef0001",
                                "claim_id": "claim_c0ffee000001",
                                "text": "Fixture evidence",
                                "locator": {"chunk_id": "chunk-e2e-001", "source": "bbox"},
                            }
                        ],
                    }
                ],
                "entities": [],
                "mesh": [],
                "outcomes": [],
            }
        ),
    )
    _write(
        real_note,
        "\n".join(
            [
                "---",
                "id: doi:10.1000/abc",
                'aliases: ["Real Note"]',
                "tags:",
                "  - Medicine/Neurology",
                "date_processed: 2026-03-28",
                "confidence: 0.9",
                "status: INDEXED",
                "doi: 10.1000/abc",
                "---",
                "",
                "# Real Note",
                "",
            ]
        ),
    )

    assert resolve_note_slug_by_paper_id(vault, "doi:10.1000/abc") == "real-note"


def test_load_structured_state_backfills_section_summary_into_runtime_data(tmp_path):
    vault = tmp_path / "vault"
    slug = "section-summary-note"
    _write(
        vault / ".pp" / slug / "state.json",
        json.dumps(
            {
                "paper_slug": slug,
                "updated_at": "2026-04-14T00:00:00Z",
                "runs": [
                    {
                        "id": "run-section-summary",
                        "action": "critical_appraisal",
                        "ts": "2026-04-14T00:00:00Z",
                        "status": "succeeded",
                        "summary": "Loaded state",
                        "data": {},
                    }
                ],
                "signals": {"has_claimset": True},
                "claimset": [
                    {
                        "id": "claim-results-1",
                        "claim": "Section summaries should be available before note-detail reconstruction.",
                        "evidence_ids": ["evidence-results-1"],
                        "evidence": [
                            {
                                "id": "evidence-results-1",
                                "claim_id": "claim-results-1",
                                "text": "Result evidence.",
                                "page": 2,
                                "section": "Results",
                                "locator": {
                                    "page": 2,
                                    "section": "Results",
                                    "span": [10, 24],
                                    "source": "state.json",
                                },
                            }
                        ],
                    }
                ],
                "entities": [],
                "mesh": [],
                "outcomes": [],
            }
        ),
    )

    state = load_structured_state(vault, slug)
    assert state is not None
    assert state.signals["section_count"] == 1
    assert state.signals["quality_gate_section_navigation_signal"] == "pass"
    assert state.runs[0].data["section_count"] == 1
    assert state.runs[0].data["section_navigation_signal_status"] == "pass"
    assert state.runs[0].data["section_navigation_signal_detail"] == "claimset_section_count=1, summary_present=true"
    assert state.runs[0].data["section_summary"] == [
        {
            "key": "results",
            "label": "Results",
            "claim_count": 1,
            "evidence_count": 1,
            "representative_claim_id": "claim-results-1",
            "representative_evidence_id": "evidence-results-1",
            "page_start": 2,
            "page_end": 2,
        }
    ]


def test_load_structured_state_preserves_explicit_section_navigation_signal(tmp_path):
    vault = tmp_path / "vault"
    slug = "section-signal-preserve-note"
    _write(
        vault / ".pp" / slug / "state.json",
        json.dumps(
            {
                "paper_slug": slug,
                "updated_at": "2026-04-14T00:00:00Z",
                "runs": [
                    {
                        "id": "run-section-signal",
                        "action": "critical_appraisal",
                        "ts": "2026-04-14T00:00:00Z",
                        "status": "succeeded",
                        "summary": "Loaded state",
                        "data": {
                            "section_navigation_signal_status": "warn",
                            "section_navigation_signal_detail": "quality_gate_detected_partial_section_support",
                        },
                    }
                ],
                "signals": {
                    "has_claimset": True,
                    "quality_gate_section_navigation_signal": "warn",
                },
                "claimset": [
                    {
                        "id": "claim-results-1",
                        "claim": "Explicit quality-gate section signal should not be overwritten by summary backfill.",
                        "evidence_ids": ["evidence-results-1"],
                        "evidence": [
                            {
                                "id": "evidence-results-1",
                                "claim_id": "claim-results-1",
                                "text": "Result evidence.",
                                "page": 2,
                                "section": "Results",
                                "locator": {
                                    "page": 2,
                                    "section": "Results",
                                    "span": [10, 24],
                                    "source": "state.json",
                                },
                            }
                        ],
                    }
                ],
                "entities": [],
                "mesh": [],
                "outcomes": [],
            }
        ),
    )

    state = load_structured_state(vault, slug)
    assert state is not None
    assert state.signals["section_count"] == 1
    assert state.signals["quality_gate_section_navigation_signal"] == "warn"
    assert state.runs[0].data["section_count"] == 1
    assert state.runs[0].data["section_navigation_signal_status"] == "warn"
    assert state.runs[0].data["section_navigation_signal_detail"] == "quality_gate_detected_partial_section_support"
    assert state.runs[0].data["section_summary"] == [
        {
            "key": "results",
            "label": "Results",
            "claim_count": 1,
            "evidence_count": 1,
            "representative_claim_id": "claim-results-1",
            "representative_evidence_id": "evidence-results-1",
            "page_start": 2,
            "page_end": 2,
        }
    ]
