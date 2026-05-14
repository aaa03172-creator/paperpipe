from __future__ import annotations

import json
from pathlib import Path

from src.services.teacher_review_eval_sidecar import build_teacher_review_eval_sidecar, load_teacher_review_rows


def _write_bundle(bundle_dir: Path) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"schema_version": "teacher_bundle.v1", "paper_id": "zotero:test-teacher-paper"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    teacher_output = {
        "doc_id": "doc:test-teacher",
        "claims": [
            {
                "claim_id": "CLM-001",
                "type": "finding",
                "statement": "Supported claim.",
                "evidence_spans": [],
                "limitations": [],
                "confidence": 0.9,
            },
            {
                "claim_id": "CLM-002",
                "type": "finding",
                "statement": "Ambiguous claim.",
                "evidence_spans": [],
                "limitations": [],
                "confidence": 0.7,
            },
        ],
    }
    (bundle_dir / "teacher_output.json").write_text(json.dumps(teacher_output, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle_dir / "teacher_output.meta.json").write_text(
        json.dumps(
            {
                "schema_version": "teacher_review.v1",
                "paper_id": "zotero:test-teacher-paper",
                "doc_id": "doc:test-teacher",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_teacher_review_eval_sidecar_summarizes_review_rows(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    _write_bundle(bundle_dir)
    review_jsonl = tmp_path / "review.jsonl"
    review_jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "paper_id": "zotero:test-teacher-paper",
                        "bundle_dir": str(bundle_dir),
                        "claim_id": "CLM-001",
                        "support_label": "SUPPORTED",
                        "location_label": "GOOD",
                        "keep_teacher_claim": True,
                        "bundle_outcome": "MINOR_ISSUE",
                        "issue_pattern": "adjacent-quote-selection",
                        "reviewer": "codex_precheck",
                        "source_page": 3,
                        "source_chunk_id": "chunk-1",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "paper_id": "zotero:test-teacher-paper",
                        "bundle_dir": str(bundle_dir),
                        "claim_id": "CLM-002",
                        "support_label": "AMBIGUOUS",
                        "location_label": "MISLEADING",
                        "keep_teacher_claim": False,
                        "bundle_outcome": "MINOR_ISSUE",
                        "issue_pattern": "fragmentary-claim",
                        "reviewer": "codex_precheck",
                        "source_page": 4,
                        "source_chunk_id": "chunk-2",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "paper_id": "zotero:test-teacher-paper",
                        "bundle_dir": str(bundle_dir),
                        "claim_id": "CLM-999",
                        "support_label": "SUPPORTED",
                        "location_label": "GOOD",
                        "keep_teacher_claim": True,
                        "bundle_outcome": "MINOR_ISSUE",
                        "reviewer": "codex_precheck",
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    rows = load_teacher_review_rows(review_jsonl)
    sidecar = build_teacher_review_eval_sidecar(
        bundle_dir=bundle_dir,
        review_rows=rows,
        review_jsonl_path=review_jsonl,
    )

    assert sidecar.schema_version == "teacher_review_eval.v1"
    assert sidecar.paper_id == "zotero:test-teacher-paper"
    assert sidecar.doc_id == "doc:test-teacher"
    assert sidecar.review_source == "codex_precheck"
    assert sidecar.bundle_outcome == "MINOR_ISSUE"
    assert sidecar.metrics.claim_count == 2
    assert sidecar.metrics.reviewed_claim_count == 2
    assert sidecar.metrics.extra_review_count == 1
    assert sidecar.metrics.adjacent_support_count == 1
    assert sidecar.metrics.fragmentary_claim_count == 1
    assert sidecar.metrics.supported_claim_count == 1
    assert sidecar.metrics.ambiguous_claim_count == 1
    assert sidecar.metrics.misleading_location_count == 1
    assert sidecar.metrics.keep_teacher_claim_count == 1
    assert sidecar.metrics.drop_teacher_claim_count == 1
    assert sidecar.metrics.supported_claim_precision == 1.0
    assert sidecar.issue_patterns == ["adjacent-quote-selection", "fragmentary-claim"]
    assert sidecar.claims[0].anchor_quality_label == "ADJACENT_SUPPORT"
    assert sidecar.claims[0].source_page == 3
    assert sidecar.claims[1].anchor_quality_label == "FRAGMENTARY_CLAIM"
    assert sidecar.claims[1].support_label == "AMBIGUOUS"


def test_build_teacher_review_eval_sidecar_tracks_missing_and_duplicate_reviews(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    _write_bundle(bundle_dir)
    review_rows = [
        {
            "paper_id": "zotero:test-teacher-paper",
            "bundle_dir": str(bundle_dir),
            "claim_id": "CLM-001",
            "support_label": "SUPPORTED",
            "location_label": "GOOD",
            "keep_teacher_claim": True,
            "bundle_outcome": "AGREE",
            "reviewer": "human",
        },
        {
            "paper_id": "zotero:test-teacher-paper",
            "bundle_dir": str(bundle_dir),
            "claim_id": "CLM-001",
            "support_label": "SUPPORTED",
            "location_label": "GOOD",
            "keep_teacher_claim": True,
            "bundle_outcome": "AGREE",
            "reviewer": "human",
        },
    ]

    sidecar = build_teacher_review_eval_sidecar(bundle_dir=bundle_dir, review_rows=review_rows)

    assert sidecar.review_source == "human"
    assert sidecar.metrics.reviewed_claim_count == 1
    assert sidecar.metrics.missing_review_count == 1
    assert sidecar.metrics.duplicate_review_row_count == 1
    assert sidecar.metrics.direct_quote_support_count == 1
    assert sidecar.claims[0].reviewed is True
    assert sidecar.claims[1].reviewed is False


def test_build_teacher_review_eval_sidecar_classifies_heading_and_misaligned_rows(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"schema_version": "teacher_bundle.v1", "paper_id": "zotero:test-heading-paper"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    teacher_output = {
        "doc_id": "doc:test-heading",
        "claims": [
            {
                "claim_id": "CLM-001",
                "type": "finding",
                "statement": "Heading-level claim.",
                "evidence_spans": [],
                "limitations": [],
                "confidence": 0.6,
            },
            {
                "claim_id": "CLM-002",
                "type": "finding",
                "statement": "Misaligned quote claim.",
                "evidence_spans": [],
                "limitations": [],
                "confidence": 0.8,
            },
        ],
    }
    (bundle_dir / "teacher_output.json").write_text(json.dumps(teacher_output, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle_dir / "teacher_output.meta.json").write_text(
        json.dumps({"schema_version": "teacher_review.v1", "paper_id": "zotero:test-heading-paper", "doc_id": "doc:test-heading"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    review_rows = [
        {
            "paper_id": "zotero:test-heading-paper",
            "bundle_dir": str(bundle_dir),
            "claim_id": "CLM-001",
            "support_label": "AMBIGUOUS",
            "location_label": "WEAK",
            "keep_teacher_claim": False,
            "bundle_outcome": "MINOR_ISSUE",
            "issue_pattern": "heading-level-evidence",
            "reviewer": "codex_precheck",
        },
        {
            "paper_id": "zotero:test-heading-paper",
            "bundle_dir": str(bundle_dir),
            "claim_id": "CLM-002",
            "support_label": "SUPPORTED",
            "location_label": "MISLEADING",
            "keep_teacher_claim": True,
            "bundle_outcome": "MAJOR_ISSUE",
            "issue_pattern": "supported-claim-wrong-anchor",
            "reviewer": "codex_precheck",
        },
    ]

    sidecar = build_teacher_review_eval_sidecar(bundle_dir=bundle_dir, review_rows=review_rows)

    assert sidecar.metrics.heading_level_support_count == 1
    assert sidecar.metrics.misaligned_quote_count == 1
    assert sidecar.claims[0].anchor_quality_label == "HEADING_LEVEL_SUPPORT"
    assert sidecar.claims[1].anchor_quality_label == "MISALIGNED_QUOTE"
