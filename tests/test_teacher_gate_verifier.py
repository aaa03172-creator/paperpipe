import json
from pathlib import Path

from scripts.verify_teacher_output import verify_and_route
from src.quality.gates import (
    EVIDENCE_LOCATION_MISSING,
    NUMERIC_SANITY_FAIL,
    TEACHER_REVIEW_FRAGMENTARY_CLAIM,
    TEACHER_REVIEW_MISALIGNED_QUOTE,
)


def _write_bundle(bundle_dir: Path, paper_id: str = "paper-001") -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "manifest.json").write_text(
        json.dumps(
            {
                "paper_id": paper_id,
                "schema_version": "teacher_bundle.v1",
                "inputs": {
                    "prior_output_file": "prior_output.json",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (bundle_dir / "prior_output.json").write_text(
        json.dumps({"summary": "Concise summary with evidence"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_teacher_review_eval(bundle_dir: Path, *, anchor_quality_label: str, bundle_outcome: str = "MAJOR_ISSUE") -> None:
    payload = {
        "schema_version": "teacher_review_eval.v1",
        "generated_at": "2026-03-24T00:00:00Z",
        "paper_id": "paper-sidecar",
        "doc_id": "doc-001",
        "bundle_dir": str(bundle_dir),
        "review_source": "codex-precheck",
        "review_jsonl_path": None,
        "bundle_outcome": bundle_outcome,
        "issue_patterns": ["synthetic-test"],
        "metrics": {
            "claim_count": 1,
            "reviewed_claim_count": 1,
            "missing_review_count": 0,
            "extra_review_count": 0,
            "duplicate_review_row_count": 0,
            "direct_quote_support_count": 0,
            "adjacent_support_count": 0,
            "heading_level_support_count": 0,
            "misaligned_quote_count": int(anchor_quality_label == "MISALIGNED_QUOTE"),
            "fragmentary_claim_count": int(anchor_quality_label == "FRAGMENTARY_CLAIM"),
            "supported_claim_count": 1,
            "unsupported_claim_count": 0,
            "ambiguous_claim_count": 0,
            "good_location_count": 0,
            "weak_location_count": 0,
            "misleading_location_count": int(anchor_quality_label == "MISALIGNED_QUOTE"),
            "keep_teacher_claim_count": 1,
            "drop_teacher_claim_count": 0,
            "supported_claim_precision": 1.0,
        },
        "claims": [
            {
                "claim_id": "CLM-001",
                "statement": "Treatment reduced pain by 25% (p<0.05).",
                "reviewed": True,
                "anchor_quality_label": anchor_quality_label,
                "support_label": "SUPPORTED",
                "location_label": "MISLEADING" if anchor_quality_label == "MISALIGNED_QUOTE" else "GOOD",
                "keep_teacher_claim": True,
                "source_page": 2,
                "source_chunk_id": "c-1",
                "bundle_outcome": bundle_outcome,
                "issue_pattern": "synthetic-test",
                "reviewer": "codex-precheck",
                "notes": None,
            }
        ],
    }
    _write_json(bundle_dir / "teacher_review_eval.json", payload)


def _valid_teacher_output() -> dict:
    return {
        "doc_id": "doc-001",
        "claims": [
            {
                "claim_id": "CLM-001",
                "type": "efficacy",
                "statement": "Treatment reduced pain by 25% (p<0.05).",
                "evidence_spans": [
                    {
                        "page": 2,
                        "chunk_id": "c-1",
                        "char_start": 10,
                        "char_end": 55,
                        "raw_text": "Treatment group improved by 25% with p=0.03.",
                        "quote": "improved by 25% with p=0.03",
                        "rationale": "Numeric evidence supports the claim.",
                    }
                ],
                "limitations": ["single center"],
                "confidence": 0.82,
            }
        ],
    }


def _invalid_teacher_output_missing_location() -> dict:
    return {
        "doc_id": "doc-002",
        "claims": [
            {
                "claim_id": "CLM-002",
                "type": "efficacy",
                "statement": "This proves improvement at p<0.05.",
                "evidence_spans": [
                    {
                        "page": None,
                        "chunk_id": "c-2",
                        "char_start": None,
                        "char_end": None,
                        "section": None,
                        "source_span": None,
                        "raw_text": "Results improved.",
                        "quote": "Results improved",
                        "rationale": "Support is weak.",
                    }
                ],
                "limitations": [],
                "confidence": 0.95,
            }
        ],
    }


def test_verify_and_route_accepts_valid_teacher_output(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    teacher_output_path = tmp_path / "teacher_output.json"
    goldset_root = tmp_path / "goldset"

    _write_bundle(bundle_dir, paper_id="paper-ok")
    _write_json(teacher_output_path, _valid_teacher_output())

    out_path, record = verify_and_route(
        bundle_dir=bundle_dir,
        teacher_output_path=teacher_output_path,
        goldset_root=goldset_root,
    )

    assert record["accepted"] is True
    assert record["reason_codes"] == []
    assert out_path.parent.name == "accepted"
    assert out_path.exists()


def test_verify_and_route_quarantines_with_reason_codes(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    teacher_output_path = tmp_path / "teacher_output.json"
    goldset_root = tmp_path / "goldset"

    _write_bundle(bundle_dir, paper_id="paper-fail")
    _write_json(teacher_output_path, _invalid_teacher_output_missing_location())

    out_path, record = verify_and_route(
        bundle_dir=bundle_dir,
        teacher_output_path=teacher_output_path,
        goldset_root=goldset_root,
    )

    assert record["accepted"] is False
    assert out_path.parent.name == "quarantine"
    assert EVIDENCE_LOCATION_MISSING in record["reason_codes"]
    assert NUMERIC_SANITY_FAIL in record["reason_codes"]


def test_verify_and_route_quarantines_fragmentary_or_misaligned_teacher_review_eval(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    teacher_output_path = tmp_path / "teacher_output.json"
    goldset_root = tmp_path / "goldset"

    _write_bundle(bundle_dir, paper_id="paper-sidecar")
    _write_json(teacher_output_path, _valid_teacher_output())
    _write_teacher_review_eval(bundle_dir, anchor_quality_label="MISALIGNED_QUOTE")

    out_path, record = verify_and_route(
        bundle_dir=bundle_dir,
        teacher_output_path=teacher_output_path,
        goldset_root=goldset_root,
    )

    assert record["accepted"] is False
    assert out_path.parent.name == "quarantine"
    assert TEACHER_REVIEW_MISALIGNED_QUOTE in record["reason_codes"]
    assert record["teacher_review_eval_summary"]["blocking_anchor_quality_labels"] == ["MISALIGNED_QUOTE"]


def test_verify_and_route_keeps_warning_only_teacher_review_eval_labels_non_blocking(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    teacher_output_path = tmp_path / "teacher_output.json"
    goldset_root = tmp_path / "goldset"

    _write_bundle(bundle_dir, paper_id="paper-warning-only")
    _write_json(teacher_output_path, _valid_teacher_output())
    _write_teacher_review_eval(bundle_dir, anchor_quality_label="ADJACENT_SUPPORT", bundle_outcome="MINOR_ISSUE")

    out_path, record = verify_and_route(
        bundle_dir=bundle_dir,
        teacher_output_path=teacher_output_path,
        goldset_root=goldset_root,
    )

    assert record["accepted"] is True
    assert out_path.parent.name == "accepted"
    assert TEACHER_REVIEW_FRAGMENTARY_CLAIM not in record["reason_codes"]
    assert TEACHER_REVIEW_MISALIGNED_QUOTE not in record["reason_codes"]
    assert record["teacher_review_eval_summary"]["blocking_anchor_quality_labels"] == []
