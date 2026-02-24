import json
from pathlib import Path

from scripts.verify_teacher_output import verify_and_route
from src.quality.gates import EVIDENCE_LOCATION_MISSING, NUMERIC_SANITY_FAIL


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
