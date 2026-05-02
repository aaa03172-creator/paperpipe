from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from tests.meeting_pack_actual_paper_fixture import write_actual_paper_aligned_source


REPO_ROOT = Path(__file__).resolve().parents[1]
def test_check_meeting_pack_real_smoke_supports_actual_paper_aligned_quality_gate_probe(tmp_path):
    vault_path = tmp_path / "vault"
    output_root = tmp_path / "meeting_pack_real_smoke"
    slug = "jamaDuboisAlzheimerDiseaseClinicalBiologicalConstruct2024"
    write_actual_paper_aligned_source(vault_path, slug)

    script_path = REPO_ROOT / "scripts" / "check_meeting_pack_real_smoke.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--vault-path",
            str(vault_path),
            "--slug",
            slug,
            "--root",
            str(output_root),
            "--modes",
            "journal_club",
            "--expect-key-point-substring",
            "clinical-biological construct",
            "--require-quality-pass",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["slug"] == slug
    assert payload["results"][0]["mode"] == "journal_club"
    assert payload["results"][0]["readiness"] == "evidence_backed"
    assert payload["results"][0]["markdown_sync"] == "in_sync"
    assert payload["results"][0]["quality_gate_status"] == "pass"
