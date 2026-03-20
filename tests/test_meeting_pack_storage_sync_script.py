from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

from src.meeting_packs.service import generate_meeting_pack
from src.meeting_packs.store import meeting_pack_markdown_path
from src.schemas.meeting_pack import MeetingPackGenerateRequest
from src.schemas.skills import SkillClaimCard, SkillClaimEvidence, SkillRunRecord, StructuredPaperState
from src.skills.storage import write_structured_state


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_state(vault_path: Path, slug: str) -> None:
    state_path = vault_path / ".pp" / slug / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = StructuredPaperState(
        paper_slug=slug,
        updated_at="2026-03-17T00:00:00Z",
        runs=[
            SkillRunRecord(
                id="skill-20260317T000000Z-critical_appraisal",
                action="critical_appraisal",
                ts="2026-03-17T00:00:00Z",
                status="succeeded",
                summary="Generated claim/evidence state.",
            )
        ],
        claimset=[
            SkillClaimCard(
                id="claim_abc123",
                run_id="skill-20260317T000000Z-critical_appraisal",
                claim="Intervention changed the inflammatory pathway.",
                evidence=[
                    SkillClaimEvidence(
                        id="evidence_def456",
                        claim_id="claim_abc123",
                        run_id="skill-20260317T000000Z-critical_appraisal",
                        text="Evidence text",
                        locator={
                            "page": 2,
                            "section": "Results",
                            "source": "state.json",
                        },
                    )
                ],
            )
        ],
    )
    write_structured_state(state_path, state)


def _run_storage_sync(*, root: Path, vault_path: Path, require_regenerable: bool = True) -> subprocess.CompletedProcess[str]:
    command = [
        "python3",
        "scripts/check_meeting_pack_storage_sync.py",
        "--root",
        str(root),
        "--vault-path",
        str(vault_path),
    ]
    if require_regenerable:
        command.append("--require-regenerable")
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_meeting_pack_storage_sync_script_passes_for_in_sync_pack(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[{"type": "paper_slug", "ref": slug}],
            max_slides=5,
        ),
        vault_path=vault_path,
        root=root,
    )

    result = _run_storage_sync(root=root, vault_path=vault_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["drifted_pack_ids"] == []
    assert payload["unavailable_regenerate_pack_ids"] == []


def test_meeting_pack_storage_sync_script_fails_for_drifted_pack(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[{"type": "paper_slug", "ref": slug}],
            max_slides=5,
        ),
        vault_path=vault_path,
        root=root,
    )
    meeting_pack_markdown_path(response.pack.id, root).write_text("# Corrupted\n", encoding="utf-8")

    result = _run_storage_sync(root=root, vault_path=vault_path)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["drifted_pack_ids"] == [response.pack.id]


def test_meeting_pack_storage_sync_script_fails_when_regenerate_is_unavailable(tmp_path):
    vault_path = tmp_path / "vault"
    root = tmp_path / "meeting_packs"
    slug = "wenzelShortchainFattyAcids2020"
    _write_state(vault_path, slug)

    response = generate_meeting_pack(
        request=MeetingPackGenerateRequest(
            mode="journal_club",
            source_items=[{"type": "paper_slug", "ref": slug}],
            max_slides=5,
        ),
        vault_path=vault_path,
        root=root,
    )
    shutil.rmtree(vault_path)

    result = _run_storage_sync(root=root, vault_path=vault_path)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["drifted_pack_ids"] == []
    assert payload["unavailable_regenerate_pack_ids"] == [response.pack.id]
