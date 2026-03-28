from pathlib import Path
from types import SimpleNamespace

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
        },
    ]

    report_path = generate_daily_report(results, config)

    assert report_path is not None
    content = Path(report_path).read_text(encoding="utf-8")

    assert "Escalation Fast-Lane Approvals**: 1" in content
    assert "Escalation Routes**: FAST_LANE_APPROVE=1, QUEUE_HUMAN_REVIEW=1" in content
    assert "Top Escalation Reason Codes**: FASTLANE_GUIDANCE (1), MODEL_REVIEW_REQUIRED (1)" in content
    assert "| 🚀 | clinical | FAST_LANE_APPROVE (FASTLANE_GUIDANCE) | [[Oncology Guideline Paper]] |" in content
    assert "| 🟡 | clinical | QUEUE_HUMAN_REVIEW (MODEL_REVIEW_REQUIRED) | [[Broad Biomaterials Review]] |" in content
