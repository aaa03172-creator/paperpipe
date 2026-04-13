from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main as api_main
from backend.routers import method_comparisons as method_comparisons_router


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_note(vault_path: Path, slug: str, *, note_id: str, title: str) -> None:
    _write(
        vault_path / "Inbox" / "PaperPipe" / f"{slug}.md",
        f"---\nid: {note_id}\naliases:\n  - {title}\n---\n\n# {title}\n",
    )
    _write(
        vault_path / ".pp" / slug / "state.json",
        json.dumps(
            {
                "schema_version": "2026-03-09.chat-hooks.v1",
                "paper_slug": slug,
                "updated_at": "2026-03-18T00:00:00Z",
                "runs": [],
                "signals": {"has_claimset": False},
                "claimset": [],
                "entities": [],
                "mesh": [],
                "outcomes": [],
            },
            indent=2,
        ),
    )


def _write_claimset(artifacts_root: Path, paper_id: str, run_id: str, payload: dict) -> None:
    run_dir = artifacts_root / paper_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.resolved.json").write_text(json.dumps(payload), encoding="utf-8")


def test_method_comparisons_api_generate_roundtrip_and_csv_export(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="doi:10.1000/a", title="Alpha Trial")
    _write_claimset(
        artifacts_root,
        "doi:10.1000/a",
        "run_a1",
        {
            "doc_id": "doi:10.1000/a",
            "claims": [
                {
                    "claim_id": "CLM-A",
                    "statement": "Intervention: Ketone ester. Comparator: Placebo. Primary outcome: ADAS-Cog score.",
                    "sample_size": 48,
                    "evidence_spans": [
                        {
                            "quote": "Intervention: Ketone ester. Comparator: Placebo. Primary outcome: ADAS-Cog score. Sample size: 48.",
                            "page": 1,
                        }
                    ],
                }
            ],
        },
    )

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_METHOD_COMPARISONS_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(method_comparisons_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/method-comparisons/generate",
        json={
            "comparison_id": "methodcmp_api_demo",
            "paper_ids": ["doi:10.1000/a"],
            "field_ids": ["intervention", "comparator", "primary_readout", "sample_size"],
        },
    )
    assert created.status_code == 200
    payload = created.json()

    assert payload["comparison"]["comparison_id"] == "methodcmp_api_demo"
    assert payload["comparison"]["rows"][0]["paper_slug"] == "paper-alpha"
    assert payload["comparison"]["rows"][0]["title"] == "Alpha Trial"
    assert [column["field_id"] for column in payload["comparison"]["columns"]] == [
        "intervention",
        "comparator",
        "primary_readout",
        "sample_size",
    ]
    assert payload["comparison"]["source_summary"]["source_priority"] == [
        "claimset.resolved.json",
        "document_artifact",
        "paper_note_state",
    ]
    assert "Ketone ester" in payload["csv_text"]
    assert "## Comparison" in payload["markdown"]
    assert (output_root / "methodcmp_api_demo" / "comparison.json").exists()
    assert (output_root / "methodcmp_api_demo" / "comparison.csv").exists()
    assert (output_root / "methodcmp_api_demo" / "comparison.md").exists()

    fetched = client.get("/method-comparisons/methodcmp_api_demo")
    assert fetched.status_code == 200
    assert fetched.json()["comparison"]["comparison_id"] == "methodcmp_api_demo"

    exported = client.get("/method-comparisons/methodcmp_api_demo/export.csv")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert exported.headers["content-disposition"] == 'attachment; filename="methodcmp_api_demo.csv"'
    assert "paper_id,paper_slug,citekey,title" in exported.text


def test_method_comparisons_api_keeps_route_stable_trailing_hyphen_export_filename(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="doi:10.1000/a", title="Alpha Trial")
    _write_claimset(
        artifacts_root,
        "doi:10.1000/a",
        "run_a1",
        {
            "doc_id": "doi:10.1000/a",
            "claims": [
                {
                    "claim_id": "CLM-A",
                    "statement": "Intervention: Ketone ester.",
                    "evidence_spans": [{"quote": "Intervention: Ketone ester.", "page": 1}],
                }
            ],
        },
    )

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_METHOD_COMPARISONS_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(method_comparisons_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/method-comparisons/generate",
        json={
            "comparison_id": "methodcmp_edge-",
            "paper_ids": ["doi:10.1000/a"],
            "field_ids": ["intervention"],
        },
    )
    assert created.status_code == 200

    exported = client.get("/method-comparisons/methodcmp_edge-/export.csv")
    assert exported.status_code == 200
    assert exported.headers["content-disposition"] == 'attachment; filename="methodcmp_edge-.csv"'


def test_method_comparisons_api_lists_recent_first(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="paper-alpha", title="Alpha Trial")
    _write_note(vault_dir, "paper-beta", note_id="paper-beta", title="Beta Trial")
    _write_claimset(
        artifacts_root,
        "paper-alpha",
        "run_a1",
        {"doc_id": "paper-alpha", "claims": [{"statement": "Intervention: A.", "evidence_spans": [{"quote": "Intervention: A.", "page": 1}]}]},
    )
    _write_claimset(
        artifacts_root,
        "paper-beta",
        "run_b1",
        {"doc_id": "paper-beta", "claims": [{"statement": "Intervention: B.", "evidence_spans": [{"quote": "Intervention: B.", "page": 2}]}]},
    )

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_METHOD_COMPARISONS_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(method_comparisons_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    older = client.post(
        "/method-comparisons/generate",
        json={
            "comparison_id": "methodcmp_api_older",
            "title": "Older comparison",
            "paper_ids": ["paper-alpha"],
            "field_ids": ["intervention"],
        },
    )
    newer = client.post(
        "/method-comparisons/generate",
        json={
            "comparison_id": "methodcmp_api_newer",
            "title": "Newer comparison",
            "paper_ids": ["paper-beta"],
            "field_ids": ["intervention"],
        },
    )
    assert older.status_code == 200
    assert newer.status_code == 200

    listed = client.get("/method-comparisons")
    assert listed.status_code == 200
    payload = listed.json()

    assert payload["total"] == 2
    assert [item["comparison_id"] for item in payload["items"]] == [
        "methodcmp_api_newer",
        "methodcmp_api_older",
    ]
    assert payload["items"][0]["title"] == "Newer comparison"
    assert payload["items"][0]["paper_count"] == 1
    assert payload["items"][0]["field_count"] == 1


def test_method_comparisons_csv_export_uses_requested_route_id_for_legacy_bundle(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="paper-alpha", title="Alpha Trial")
    _write_claimset(
        artifacts_root,
        "paper-alpha",
        "run_a1",
        {"doc_id": "paper-alpha", "claims": [{"statement": "Intervention: A.", "evidence_spans": [{"quote": "Intervention: A.", "page": 1}]}]},
    )

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_METHOD_COMPARISONS_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir))
    monkeypatch.setattr(method_comparisons_router, "load_config", lambda: config)

    client = TestClient(api_main.app)
    created = client.post(
        "/method-comparisons/generate",
        json={
            "comparison_id": "methodcmp_legacy_alias",
            "paper_ids": ["paper-alpha"],
            "field_ids": ["intervention"],
        },
    )
    assert created.status_code == 200

    comparison_json_path = output_root / "methodcmp_legacy_alias" / "comparison.json"
    payload = json.loads(comparison_json_path.read_text(encoding="utf-8"))
    payload["comparison_id"] = "methodcmp_canonical_bundle"
    comparison_json_path.write_text(json.dumps(payload), encoding="utf-8")

    exported = client.get("/method-comparisons/methodcmp_legacy_alias/export.csv")

    assert exported.status_code == 200
    assert exported.headers["content-disposition"] == 'attachment; filename="methodcmp_legacy_alias.csv"'


def test_method_comparisons_api_returns_404_when_comparison_missing(tmp_path, monkeypatch):
    output_root = tmp_path / "method_comparisons"
    monkeypatch.setenv("PAPERPIPE_METHOD_COMPARISONS_DIR", str(output_root))
    monkeypatch.delenv("LATTICE_API_KEY", raising=False)
    monkeypatch.delenv("PAPERPIPE_API_KEY", raising=False)

    client = TestClient(api_main.app)
    response = client.get("/method-comparisons/methodcmp_missing")

    assert response.status_code == 404
