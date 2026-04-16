from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import src.cli as cli


def _last_json_block(output: str) -> dict:
    start = output.find("{")
    end = output.rfind("}")
    assert start >= 0 and end >= start
    return json.loads(output[start : end + 1])


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
                "updated_at": "2026-04-08T00:00:00Z",
                "runs": [
                    {
                        "id": "run-current",
                        "action": "deep_read",
                        "ts": "2026-04-08T00:00:00Z",
                        "status": "succeeded",
                        "summary": "Canonical state snapshot",
                    }
                ],
                "signals": {"last_run_id": "run-current"},
                "claimset": [
                    {
                        "id": "claim_0",
                        "run_id": "run-current",
                        "claim": "Finding 0",
                        "evidence": [
                            {
                                "id": "evidence_0",
                                "run_id": "run-current",
                                "text": "Evidence 0",
                                "page": 1,
                                "grounded": True,
                                "resolution": "resolved",
                                "source": "reader",
                            }
                        ],
                    }
                ],
                "entities": [],
                "mesh": [],
                "outcomes": [],
            },
            indent=2,
        ),
    )


def _write_run(artifacts_root: Path, paper_id: str, run_id: str, *, statement: str = "Finding 0") -> None:
    run_dir = artifacts_root / paper_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "succeeded",
                "finished_at": "2026-04-08T01:00:00Z",
                "parser_backend": "docling",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "claimset.resolved.json").write_text(
        json.dumps(
            {
                "doc_id": paper_id,
                "claims": [
                    {
                        "claim_id": "CLM-0",
                        "statement": statement,
                        "evidence_spans": [
                            {
                                "quote": "Evidence 0",
                                "page": 1,
                                "section": "Results",
                                "grounded": True,
                                "resolution": "resolved",
                                "source": "reader",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_paper_synthesis_cli_generate_show_and_list(tmp_path, monkeypatch):
    runner = CliRunner()
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "paper_syntheses"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="doi:10.1000/a", title="Alpha Trial")
    _write_run(artifacts_root, "doi:10.1000/a", "run-current")

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(output_root))
    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)))

    created_result = runner.invoke(cli.app, ["paper-synthesis-generate", "paper-alpha"])
    assert created_result.exit_code == 0
    created = _last_json_block(created_result.output)
    synthesis_id = created["synthesis"]["synthesis_id"]

    assert created["synthesis"]["artifact_family"] == "paper_synthesis"
    assert created["synthesis"]["canonical_status"] == "non_canonical"
    assert created["synthesis"]["readiness"] == "evidence_backed"
    assert created["synthesis"]["lineage_summary"]["present_required_source_kinds"] == [
        "structured_state",
        "claimset_resolved",
        "run_meta",
    ]
    assert (output_root / synthesis_id / "paper_synthesis.json").exists()

    show_result = runner.invoke(cli.app, ["paper-synthesis-show", synthesis_id])
    assert show_result.exit_code == 0
    shown = _last_json_block(show_result.output)
    assert shown["synthesis"]["synthesis_id"] == synthesis_id

    list_result = runner.invoke(cli.app, ["paper-synthesis-list"])
    assert list_result.exit_code == 0
    listed = _last_json_block(list_result.output)
    assert listed["total"] == 1
    assert listed["items"][0]["canonical_status"] == "non_canonical"
    assert listed["items"][0]["source_ref_count"] >= 3
    assert listed["items"][0]["lineage_summary"]["answer_route"] == "canonical_state_then_upstream_evidence"


def test_paper_synthesis_cli_markdown_flag_prints_frontmatter(tmp_path, monkeypatch):
    runner = CliRunner()
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "paper_syntheses"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="paper-alpha", title="Alpha Trial")
    _write_run(artifacts_root, "paper-alpha", "run-current")

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(output_root))
    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)))

    result = runner.invoke(cli.app, ["paper-synthesis-generate", "paper-alpha", "--markdown"])
    assert result.exit_code == 0
    assert result.output.startswith("---\nartifact_family: paper_synthesis\n")


def test_paper_synthesis_cli_manifest_flag_prints_structured_manifest_only(tmp_path, monkeypatch):
    runner = CliRunner()
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "paper_syntheses"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="paper-alpha", title="Alpha Trial")
    _write_run(artifacts_root, "paper-alpha", "run-current")

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(output_root))
    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)))

    generated_result = runner.invoke(cli.app, ["paper-synthesis-generate", "paper-alpha", "--manifest"])
    assert generated_result.exit_code == 0
    generated = _last_json_block(generated_result.output)
    assert generated["artifact_family"] == "paper_synthesis"
    assert generated["canonical_status"] == "non_canonical"
    assert "source_refs" in generated
    assert "markdown" not in generated

    synthesis_id = generated["synthesis_id"]
    shown_result = runner.invoke(cli.app, ["paper-synthesis-show", synthesis_id, "--manifest"])
    assert shown_result.exit_code == 0
    shown = _last_json_block(shown_result.output)
    assert shown["synthesis_id"] == synthesis_id
    assert shown["lineage_summary"]["answer_route"] == "canonical_state_then_upstream_evidence"
    assert "markdown" not in shown


def test_paper_synthesis_cli_rejects_manifest_and_markdown_together(tmp_path, monkeypatch):
    runner = CliRunner()
    vault_dir = tmp_path / "vault"
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "paper_syntheses"
    vault_dir.mkdir(parents=True, exist_ok=True)

    _write_note(vault_dir, "paper-alpha", note_id="paper-alpha", title="Alpha Trial")
    _write_run(artifacts_root, "paper-alpha", "run-current")

    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_root))
    monkeypatch.setenv("PAPERPIPE_PAPER_SYNTHESES_DIR", str(output_root))
    monkeypatch.setattr(cli, "load_config", lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)))

    result = runner.invoke(cli.app, ["paper-synthesis-generate", "paper-alpha", "--manifest", "--markdown"])
    assert result.exit_code != 0
    assert "Choose only one of --manifest or --markdown" in result.output
