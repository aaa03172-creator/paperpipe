from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_paper_synthesis_manifest_conformance_script_reports_ready_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_paper_synthesis_manifest_conformance.py"

    _write(
        workspace / "src" / "schemas" / "paper_synthesis.py",
        "\n".join(
            [
                'artifact_family = "paper_synthesis"',
                'template_kind = "paper"',
                'layer: Literal["compiled_knowledge"] = "compiled_knowledge"',
                'canonical_status: Literal["non_canonical"] = "non_canonical"',
                "source_refs: list[PaperSynthesisSourceRef]",
                "lineage_summary: PaperSynthesisLineageSummary",
                'raise ValueError("PaperSynthesis.source_refs must include structured_state")',
                'raise ValueError("evidence_backed cannot coexist with warnings or uncertainty_notes")',
            ]
        )
        + "\n",
    )
    _write(
        workspace / "src" / "paper_syntheses" / "store.py",
        "\n".join(
            [
                'json_name = "paper_synthesis.json"',
                'md_name = "paper_synthesis.md"',
                "def save_paper_synthesis_bundle(): pass",
                "def load_paper_synthesis(): pass",
                "def load_paper_synthesis_markdown(): pass",
                "def _restore_optional_text(): pass",
                "def _remove_empty_dir(): pass",
            ]
        )
        + "\n",
    )
    _write(
        workspace / "src" / "paper_syntheses" / "renderer.py",
        "\n".join(
            [
                'line = f"artifact_family: {synthesis.artifact_family}"',
                'line = f"template_kind: {synthesis.template_kind}"',
                'line = f"layer: {synthesis.layer}"',
                'line = f"canonical_status: {synthesis.canonical_status}"',
                '"source_refs:"',
                '"## Layer contract"',
                '"## Promotion guardrail"',
            ]
        )
        + "\n",
    )
    _write(
        workspace / "backend" / "routers" / "paper_syntheses.py",
        "\n".join(
            [
                '@router.get(',
                '    "/{synthesis_id}"',
                ')',
                '@router.get(',
                '    "/{synthesis_id}/manifest"',
                ')',
                '@router.get(',
                '    "/{synthesis_id}/markdown"',
                ')',
                '"PaperPipe-Preferred-Manifest-Route"',
                '"PaperPipe-Preferred-Markdown-Route"',
                '"deprecated_bundle_read"',
            ]
        )
        + "\n",
    )
    _write(
        workspace / "tests" / "test_paper_synthesis_service.py",
        "assert result.synthesis.lineage_summary.answer_route == 'canonical_state_then_upstream_evidence'\n",
    )
    _write(
        workspace / "tests" / "test_paper_syntheses_api.py",
        "assert '/manifest' in payload\nassert payload['lineage_summary']['answer_route'] == 'canonical_state_then_upstream_evidence'\n",
    )
    _write(
        workspace / "tests" / "test_no_new_paper_synthesis_bundle_route_usage.py",
        'assert "compatibility bundle route should not spread outside allowlist"\n',
    )
    _write(workspace / "scripts" / "check_paper_synthesis_bundle_route_usage.py", "print('ok')\n")
    _write(workspace / "scripts" / "check_paper_synthesis_bundle_route_removal_readiness.py", "print('ok')\n")

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["conformant"] is True
    assert payload["schema_contract"]["ready"] is True
    assert payload["store_contract"]["ready"] is True
    assert payload["renderer_contract"]["ready"] is True
    assert payload["route_contract"]["ready"] is True
    assert payload["guardrail_contract"]["ready"] is True


def test_paper_synthesis_manifest_conformance_script_flags_missing_contracts(tmp_path):
    workspace = tmp_path / "workspace"
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_paper_synthesis_manifest_conformance.py"

    _write(
        workspace / "src" / "schemas" / "paper_synthesis.py",
        'artifact_family = "paper_synthesis"\n',
    )

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["conformant"] is False
    assert payload["schema_contract"]["ready"] is False
    assert payload["store_contract"]["ready"] is False
    assert payload["renderer_contract"]["ready"] is False
    assert payload["route_contract"]["ready"] is False
    assert payload["guardrail_contract"]["ready"] is False
