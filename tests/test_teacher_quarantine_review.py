import json
from pathlib import Path

from scripts.review_teacher_quarantine import list_quarantine_records, resolve_quarantine_record


def _write_quarantine_record(path: Path, paper_id: str, reason_codes: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "paper_id": paper_id,
                "reason_codes": reason_codes or ["EVIDENCE_LOCATION_MISSING"],
                "teacher_output": {"doc_id": paper_id, "claims": []},
                "manifest": {"paper_id": paper_id},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def test_list_quarantine_records_hides_reviewed_by_default(tmp_path: Path) -> None:
    goldset_root = tmp_path / "goldset"
    _write_quarantine_record(goldset_root / "quarantine" / "paper-open.json", "paper-open")
    _write_quarantine_record(goldset_root / "quarantine" / "paper-reviewed.json", "paper-reviewed")

    resolve_quarantine_record(
        goldset_root=goldset_root,
        paper_id="paper-reviewed",
        resolution="KEEP_QUARANTINE",
        reviewer="qa",
        notes="missing evidence still unresolved",
    )

    open_rows = list_quarantine_records(goldset_root=goldset_root, include_resolved=False)
    assert [row["paper_id"] for row in open_rows] == ["paper-open"]

    all_rows = list_quarantine_records(goldset_root=goldset_root, include_resolved=True)
    all_by_id = {row["paper_id"]: row for row in all_rows}
    assert set(all_by_id) == {"paper-open", "paper-reviewed"}
    assert all_by_id["paper-reviewed"]["reviewed"] is True
    assert all_by_id["paper-reviewed"]["review_resolution"] == "KEEP_QUARANTINE"
    assert all_by_id["paper-reviewed"]["accepted_after_review"] is False


def test_resolve_quarantine_record_promotes_to_accepted_and_logs_manual_decision(tmp_path: Path) -> None:
    goldset_root = tmp_path / "goldset"
    _write_quarantine_record(goldset_root / "quarantine" / "paper-promote.json", "paper-promote")

    result = resolve_quarantine_record(
        goldset_root=goldset_root,
        paper_id="paper-promote",
        resolution="APPROVED_WITH_EDIT",
        reviewer="reviewer-a",
        notes="fixed location spans manually",
    )

    accepted_path = goldset_root / "accepted" / "paper-promote.json"
    assert result["accepted_after_review"] is True
    assert result["manual_corrected"] is True
    assert accepted_path.exists()

    accepted_payload = json.loads(accepted_path.read_text(encoding="utf-8"))
    assert accepted_payload["accepted"] is True
    assert accepted_payload["review"]["resolution"] == "APPROVED_WITH_EDIT"
    assert accepted_payload["review"]["reviewer"] == "reviewer-a"

    decisions = _load_jsonl(goldset_root / "manual_decisions" / "human_decisions.jsonl")
    assert len(decisions) == 1
    assert decisions[0]["paper_id"] == "paper-promote"
    assert decisions[0]["resolution"] == "APPROVED_WITH_EDIT"
    assert decisions[0]["manual_corrected"] is True


def test_resolve_quarantine_record_keep_quarantine_removes_stale_accepted_copy(tmp_path: Path) -> None:
    goldset_root = tmp_path / "goldset"
    _write_quarantine_record(goldset_root / "quarantine" / "paper-revert.json", "paper-revert")

    resolve_quarantine_record(
        goldset_root=goldset_root,
        paper_id="paper-revert",
        resolution="APPROVE_NO_EDIT",
        reviewer="reviewer-a",
    )
    accepted_path = goldset_root / "accepted" / "paper-revert.json"
    assert accepted_path.exists()

    result = resolve_quarantine_record(
        goldset_root=goldset_root,
        paper_id="paper-revert",
        resolution="KEEP_QUARANTINE",
        reviewer="reviewer-b",
        notes="rejected after second look",
    )

    assert result["accepted_after_review"] is False
    assert result["manual_corrected"] is False
    assert not accepted_path.exists()

    decisions = _load_jsonl(goldset_root / "manual_decisions" / "human_decisions.jsonl")
    assert [row["resolution"] for row in decisions] == ["APPROVE_NO_EDIT", "KEEP_QUARANTINE"]
