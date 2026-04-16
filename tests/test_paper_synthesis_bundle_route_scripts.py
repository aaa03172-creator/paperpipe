from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import src.db_utils as db_utils
from src.services.event_log import log_request_audit


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_paper_synthesis_bundle_route_audit_script_flags_non_allowlisted_usage(tmp_path):
    workspace = tmp_path / "workspace"
    _write(
        workspace / "frontend" / "src" / "app" / "lib" / "api.ts",
        'const url = `/paper-syntheses/${encodeURIComponent(normalizedId)}`;\n',
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_paper_synthesis_bundle_route_usage.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["offender_count"] == 1
    assert payload["offenders"] == ["frontend/src/app/lib/api.ts"]


def test_paper_synthesis_bundle_route_audit_script_allows_bounded_compatibility_surfaces(tmp_path):
    workspace = tmp_path / "workspace"
    _write(
        workspace / "backend" / "routers" / "paper_syntheses.py",
        'summary = "Prefer `/paper-syntheses/{synthesis_id}/manifest` over `/paper-syntheses/{synthesis_id}`"\n',
    )
    _write(
        workspace / "docs" / "PAPER_SYNTHESIS.md",
        "- `GET /paper-syntheses/{synthesis_id}` (compatibility bundle fetch)\n",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_paper_synthesis_bundle_route_usage.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["offender_count"] == 0
    assert payload["allowlisted_surface_count"] == 2
    assert payload["allowlisted_surfaces"] == [
        "backend/routers/paper_syntheses.py",
        "docs/PAPER_SYNTHESIS.md",
    ]


def test_paper_synthesis_bundle_route_removal_readiness_reports_first_party_ready_but_route_deletion_not_confirmed(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    missing_db = tmp_path / "missing.db"
    _write(
        workspace / "backend" / "routers" / "paper_syntheses.py",
        'summary = "Compatibility bundle fetch at /paper-syntheses/{synthesis_id}"\n',
    )
    _write(
        workspace / "frontend" / "src" / "app" / "lib" / "api.ts",
        "\n".join(
            [
                "export async function getPaperSynthesisManifest() {",
                "  return `/paper-syntheses/${encodeURIComponent(normalizedId)}/manifest`;",
                "}",
            ]
        )
        + "\n",
    )
    _write(
        workspace / "frontend" / "src" / "app" / "lib" / "types.ts",
        "export interface PaperSynthesisManifest {}\n",
    )
    _write(
        workspace / "src" / "cli.py",
        "\n".join(
            [
                '@app.command(name="paper-synthesis-generate")',
                '"--manifest"',
                '@app.command(name="paper-synthesis-show")',
                '"--manifest"',
                'raise typer.BadParameter("Choose only one of --manifest or --markdown")',
            ]
        )
        + "\n",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_paper_synthesis_bundle_route_removal_readiness.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace), "--db", str(missing_db)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["active_surface_ready"] is True
    assert payload["ready_to_retire_bundle_route_from_first_party"] is True
    assert payload["ready_to_delete_api_bundle_route_now"] is False
    assert payload["frontend_manifest_contract"]["ready"] is True
    assert payload["cli_manifest_contract"]["ready"] is True
    assert payload["runtime_compatibility_hit_summary"]["exit_code"] == 2
    assert payload["runtime_signal_interpretation"] == "unavailable"
    assert "not confirmed" in payload["api_route_deletion_not_confirmed_reason"].lower()


def test_paper_synthesis_bundle_route_removal_readiness_flags_first_party_blockers(tmp_path):
    workspace = tmp_path / "workspace"
    missing_db = tmp_path / "missing.db"
    _write(
        workspace / "frontend" / "src" / "app" / "lib" / "api.ts",
        'const url = `/paper-syntheses/${encodeURIComponent(normalizedId)}`;\n',
    )
    _write(
        workspace / "frontend" / "src" / "app" / "lib" / "types.ts",
        "export interface PaperSynthesisDetail {}\n",
    )
    _write(
        workspace / "src" / "cli.py",
        '@app.command(name="paper-synthesis-generate")\n',
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_paper_synthesis_bundle_route_removal_readiness.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace), "--db", str(missing_db)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["active_surface_ready"] is False
    assert payload["ready_to_retire_bundle_route_from_first_party"] is False
    assert payload["compatibility_usage_audit"]["offender_count"] == 1
    assert payload["frontend_manifest_contract"]["ready"] is False
    assert payload["cli_manifest_contract"]["ready"] is False
    assert payload["runtime_signal_interpretation"] == "unavailable"


def test_paper_synthesis_bundle_route_removal_readiness_includes_runtime_hit_summary(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    db_path = tmp_path / "state.db"
    original_db_path = db_utils.DB_PATH

    _write(
        workspace / "backend" / "routers" / "paper_syntheses.py",
        'summary = "Compatibility bundle fetch at /paper-syntheses/{synthesis_id}"\n',
    )
    _write(
        workspace / "frontend" / "src" / "app" / "lib" / "api.ts",
        "\n".join(
            [
                "export async function getPaperSynthesisManifest() {",
                "  return `/paper-syntheses/${encodeURIComponent(normalizedId)}/manifest`;",
                "}",
            ]
        )
        + "\n",
    )
    _write(
        workspace / "frontend" / "src" / "app" / "lib" / "types.ts",
        "export interface PaperSynthesisManifest {}\n",
    )
    _write(
        workspace / "src" / "cli.py",
        "\n".join(
            [
                '@app.command(name="paper-synthesis-generate")',
                '"--manifest"',
                '@app.command(name="paper-synthesis-show")',
                '"--manifest"',
                'raise typer.BadParameter("Choose only one of --manifest or --markdown")',
            ]
        )
        + "\n",
    )

    monkeypatch.chdir(tmp_path)
    db_utils.DB_PATH = db_path
    try:
        db_utils.init_db()
        log_request_audit(
            source="compatibility_route",
            client_ip="10.0.0.1",
            host="alpha.example.com",
            method="GET",
            path="/paper-syntheses/papersynth_alpha",
            status_code=200,
            outcome="deprecated_bundle_read",
            payload={
                "synthesis_id": "papersynth_alpha",
                "preferred_manifest_route": "/paper-syntheses/papersynth_alpha/manifest",
                "preferred_markdown_route": "/paper-syntheses/papersynth_alpha/markdown",
            },
        )

        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "check_paper_synthesis_bundle_route_removal_readiness.py"

        result = subprocess.run(
            [sys.executable, str(script_path), "--root", str(workspace), "--db", str(db_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        db_utils.DB_PATH = original_db_path

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["active_surface_ready"] is True
    assert payload["ready_to_delete_api_bundle_route_now"] is False
    assert payload["runtime_signal_interpretation"] == "possibly_external_seen"
    assert payload["runtime_compatibility_hit_summary"]["exit_code"] == 0
    assert payload["runtime_compatibility_hit_summary"]["route_usage_observed"] is True
    assert payload["runtime_compatibility_hit_summary"]["recent_possible_external_hosts"] == [
        "alpha.example.com"
    ]


def test_paper_synthesis_bundle_route_hit_summary_reports_recent_observed_usage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_db_path = db_utils.DB_PATH
    db_path = tmp_path / "state.db"
    db_utils.DB_PATH = db_path
    try:
        db_utils.init_db()
        log_request_audit(
            source="compatibility_route",
            client_ip="10.0.0.1",
            host="alpha.example.com",
            method="GET",
            path="/paper-syntheses/papersynth_alpha",
            status_code=200,
            outcome="deprecated_bundle_read",
            payload={
                "synthesis_id": "papersynth_alpha",
                "preferred_manifest_route": "/paper-syntheses/papersynth_alpha/manifest",
                "preferred_markdown_route": "/paper-syntheses/papersynth_alpha/markdown",
            },
        )
        log_request_audit(
            source="compatibility_route",
            client_ip="10.0.0.2",
            host="testserver",
            method="GET",
            path="/paper-syntheses/papersynth_missing",
            status_code=200,
            outcome="deprecated_bundle_read",
            payload={
                "synthesis_id": "papersynth_missing",
                "preferred_manifest_route": "/paper-syntheses/papersynth_missing/manifest",
                "preferred_markdown_route": "/paper-syntheses/papersynth_missing/markdown",
            },
        )
        log_request_audit(
            source="compatibility_route",
            client_ip="10.0.0.4",
            host="labbox.local",
            method="GET",
            path="/paper-syntheses/papersynth_gamma",
            status_code=200,
            outcome="deprecated_bundle_read",
            payload={
                "synthesis_id": "papersynth_gamma",
                "preferred_manifest_route": "/paper-syntheses/papersynth_gamma/manifest",
                "preferred_markdown_route": "/paper-syntheses/papersynth_gamma/markdown",
            },
        )
        log_request_audit(
            source="browser_api",
            client_ip="10.0.0.3",
            host="ignored.local",
            method="POST",
            path="/api/jobs/deepread",
            status_code=200,
            outcome="allowed",
            payload={"scope": "browser_write"},
        )

        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "summarize_paper_synthesis_bundle_route_hits.py"

        env = dict(os.environ)
        env["PAPERPIPE_DB_PATH"] = str(db_path)
        result = subprocess.run(
            [sys.executable, str(script_path), "--limit", "5"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        payload = json.loads(result.stdout)
        assert result.returncode == 0
        assert payload["route_usage_observed"] is True
        assert payload["total_hit_count"] == 3
        assert payload["latest_hit_ts"] is not None
        assert payload["recent_unique_synthesis_ids"] == [
            "papersynth_alpha",
            "papersynth_gamma",
            "papersynth_missing",
        ]
        assert payload["recent_host_counts"] == [
            {"host": "alpha.example.com", "count": 1},
            {"host": "labbox.local", "count": 1},
            {"host": "testserver", "count": 1},
        ]
        assert payload["recent_host_signal_counts"] == {
            "internal_network_like": 1,
            "known_local_or_test": 1,
            "possibly_external": 1,
        }
        assert payload["recent_possible_external_hosts"] == ["alpha.example.com"]
        assert payload["recent_likely_test_noise_count"] == 1
        assert payload["recent_non_noise_hit_count"] == 2
        assert len(payload["recent_hits"]) == 3
        assert {item["synthesis_id"] for item in payload["recent_hits"]} == {
            "papersynth_alpha",
            "papersynth_gamma",
            "papersynth_missing",
        }
        assert {item["host_signal"] for item in payload["recent_hits"]} == {
            "internal_network_like",
            "known_local_or_test",
            "possibly_external",
        }
        missing_hit = next(item for item in payload["recent_hits"] if item["synthesis_id"] == "papersynth_missing")
        assert missing_hit["likely_test_noise"] is True
        assert missing_hit["likely_test_noise_reason"] == "known_missing_placeholder_on_local_test_host"
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_synthesis_bundle_route_hit_summary_reports_missing_runtime_db(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "summarize_paper_synthesis_bundle_route_hits.py"
    missing_db = tmp_path / "missing.db"

    env = dict(os.environ)
    env["PAPERPIPE_DB_PATH"] = str(missing_db)
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["db_exists"] is False
    assert payload["request_audits_table_present"] is False
    assert payload["route_usage_observed"] is False
    assert payload["total_hit_count"] == 0
    assert payload["recent_hits"] == []
    assert payload["recent_host_signal_counts"] == {}
    assert payload["recent_possible_external_hosts"] == []
    assert payload["recent_likely_test_noise_count"] == 0
    assert payload["recent_non_noise_hit_count"] == 0


def test_paper_synthesis_bundle_route_removal_readiness_can_classify_known_test_noise_only(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    db_path = tmp_path / "state.db"
    original_db_path = db_utils.DB_PATH

    _write(
        workspace / "backend" / "routers" / "paper_syntheses.py",
        'summary = "Compatibility bundle fetch at /paper-syntheses/{synthesis_id}"\n',
    )
    _write(
        workspace / "frontend" / "src" / "app" / "lib" / "api.ts",
        "\n".join(
            [
                "export async function getPaperSynthesisManifest() {",
                "  return `/paper-syntheses/${encodeURIComponent(normalizedId)}/manifest`;",
                "}",
            ]
        )
        + "\n",
    )
    _write(
        workspace / "frontend" / "src" / "app" / "lib" / "types.ts",
        "export interface PaperSynthesisManifest {}\n",
    )
    _write(
        workspace / "src" / "cli.py",
        "\n".join(
            [
                '@app.command(name="paper-synthesis-generate")',
                '"--manifest"',
                '@app.command(name="paper-synthesis-show")',
                '"--manifest"',
                'raise typer.BadParameter("Choose only one of --manifest or --markdown")',
            ]
        )
        + "\n",
    )

    monkeypatch.chdir(tmp_path)
    db_utils.DB_PATH = db_path
    try:
        db_utils.init_db()
        log_request_audit(
            source="compatibility_route",
            client_ip="10.0.0.2",
            host="testserver",
            method="GET",
            path="/paper-syntheses/papersynth_missing",
            status_code=200,
            outcome="deprecated_bundle_read",
            payload={
                "synthesis_id": "papersynth_missing",
                "preferred_manifest_route": "/paper-syntheses/papersynth_missing/manifest",
                "preferred_markdown_route": "/paper-syntheses/papersynth_missing/markdown",
            },
        )

        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "check_paper_synthesis_bundle_route_removal_readiness.py"

        result = subprocess.run(
            [sys.executable, str(script_path), "--root", str(workspace), "--db", str(db_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        db_utils.DB_PATH = original_db_path

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["active_surface_ready"] is True
    assert payload["runtime_signal_interpretation"] == "likely_historical_test_noise_only"
    assert payload["runtime_compatibility_hit_summary"]["recent_likely_test_noise_count"] == 1
    assert payload["runtime_compatibility_hit_summary"]["recent_non_noise_hit_count"] == 0
