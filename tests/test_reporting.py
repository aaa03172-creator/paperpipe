from pathlib import Path
from types import SimpleNamespace
import json

from src.reporting import generate_daily_report
from src.schemas import PaperStatus


def test_generate_daily_report_includes_structured_escalation_summary(tmp_path):
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=tmp_path / "vault"))

    results = [
        {
            "title": "Oncology Guideline Paper",
            "slot": "clinical",
            "processing_status": PaperStatus.APPROVED,
            "hybrid_tags": {"soft_tags": ["#oncology"]},
            "is_escalated": True,
            "escalation_final_route": "FAST_LANE_APPROVE",
            "escalation_reason_codes": ["FASTLANE_GUIDANCE"],
            "ai_mode": "extraction",
            "feedback_json": json.dumps(
                {
                    "selection": {
                        "selected_rank": 1,
                        "candidate_count": 3,
                        "selected_manual_rank_score": 0.66,
                    }
                }
            ),
        },
        {
            "title": "Broad Biomaterials Review",
            "slot": "clinical",
            "processing_status": PaperStatus.PENDING_REVIEW,
            "hybrid_tags": {"soft_tags": ["#biomaterials"]},
            "is_escalated": False,
            "escalation_final_route": "QUEUE_HUMAN_REVIEW",
            "escalation_reason_codes": ["MODEL_REVIEW_REQUIRED"],
            "ai_mode": "deep_read",
            "feedback_json": json.dumps(
                {
                    "selection": {
                        "selected_rank": 2,
                        "candidate_count": 4,
                        "selected_manual_rank_score": 0.41,
                        "skipped_processed_candidates": ["pmid:existing-top"],
                    }
                }
            ),
        },
    ]

    report_path = generate_daily_report(results, config)

    assert report_path is not None
    content = Path(report_path).read_text(encoding="utf-8")

    assert "Escalation Fast-Lane Approvals**: 1" in content
    assert "Escalation Routes**: FAST_LANE_APPROVE=1, QUEUE_HUMAN_REVIEW=1" in content
    assert "Top Escalation Reason Codes**: FASTLANE_GUIDANCE (1), MODEL_REVIEW_REQUIRED (1)" in content
    assert "| 🚀 | clinical | FAST_LANE_APPROVE (FASTLANE_GUIDANCE) | r1/3, s=0.66 | [[Oncology Guideline Paper]] |" in content
    assert "| 🟡 | clinical | QUEUE_HUMAN_REVIEW (MODEL_REVIEW_REQUIRED) | r2/4, s=0.41, skip=1 | [[Broad Biomaterials Review]] |" in content
    assert "## 🚨 Health Signals" in content
    assert "No immediate operator action required." in content


def test_generate_daily_report_surfaces_actionable_health_alerts(tmp_path):
    config = SimpleNamespace(paths=SimpleNamespace(obsidian_vault=tmp_path / "vault"))

    results = [
        {
            "title": "Retracted Paper",
            "slot": "clinical",
            "processing_status": PaperStatus.QUARANTINED,
            "hybrid_tags": {},
            "is_retracted": True,
            "ai_mode": "fallback",
            "feedback_json": "{}",
        },
        {
            "title": "Second Quarantined Paper",
            "slot": "mechanism",
            "processing_status": PaperStatus.QUARANTINED,
            "hybrid_tags": {},
            "ai_mode": "fallback",
            "feedback_json": "{}",
        },
        {
            "title": "Pending Review Paper",
            "slot": "methods",
            "processing_status": PaperStatus.PENDING_REVIEW,
            "hybrid_tags": {},
            "ai_mode": "fallback",
            "feedback_json": "{}",
        },
    ]

    report_path = generate_daily_report(results, config)

    assert report_path is not None
    content = Path(report_path).read_text(encoding="utf-8")

    assert "**System Status**: 🔴 System Alert" in content
    assert "Parsing success rate fell below DoD target" in content
    assert "Retraction signal detected in today's batch" in content
    assert "Quarantined papers exceeded half of today's batch" in content
    assert "Review retracted papers immediately" in content
    assert "Audit today's ingest/classification path" in content
