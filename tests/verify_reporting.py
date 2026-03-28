import sys
from unittest.mock import MagicMock
from pathlib import Path
from src.reporting import generate_daily_report, PaperStatus

def test_reporting():
    # Mock Config
    mock_config = MagicMock()
    mock_config.paths.obsidian_vault = Path("./test_vault")
    
    # Mock Results
    results = [
        # Paper 1: Success (Auto Approved)
        {
            "title": "Paper 1",
            "slot": "clinical",
            "processing_status": PaperStatus.AUTO_APPROVED,
            "hybrid_tags": {"soft_tags": ["#Tag1"]},
            "ai_mode": "extraction"
        },
        # Paper 2: Pending (Medium Confidence)
        {
            "title": "Paper 2",
            "slot": "mechanism",
            "processing_status": PaperStatus.PENDING_REVIEW,
            "hybrid_tags": {"soft_tags": ["#Tag2"]},
            "ai_mode": "deep_read"
        },
        # Paper 3: Failed (Quarantined, No Tags)
        {
            "title": "Paper 3",
            "slot": "methods",
            "processing_status": PaperStatus.QUARANTINED,
            "hybrid_tags": None, # Parsing Failed
            "ai_mode": "fallback"
        },
        # Paper 4: Retracted
        {
            "title": "Paper 4",
            "slot": "clinical",
            "processing_status": PaperStatus.QUARANTINED,
            "is_retracted": True,
            "hybrid_tags": {"soft_tags": ["#Tag4"]},
            "ai_mode": "one_liner"
        }
    ]
    
    # Run
    report_path = generate_daily_report(results, mock_config)
    
    if not report_path:
        print("Report generation failed.")
        sys.exit(1)
        
    print(f"Report generated at: {report_path}")
    
    # Verify Content
    with open(report_path, "r") as f:
        content = f.read()
        print("\n--- Report Content Snippet ---")
        print(content[:500])
        print("------------------------------\n")
        
        # Assertions
        assert "🎯 Definition of Done (MVP)" in content
        assert "Parsing Success Rate" in content
        
        # Parsing calculation: 
        # Total = 4
        # Success = 1 (Paper 1) + 1 (Paper 2) + 1 (Paper 4 has tags) = 3
        # Paper 3 has None tags.
        # Rate = 3/4 = 75%
        # Target 80% -> Fail
        
        assert "75.0%" in content
        assert "🔴 Fail" in content # Because 75% < 80%
        
        # Check pass/fail logic
        assert "Total Processed**: 4" in content
        assert "System Alert" in content # Retracted paper triggers alert
        assert "Escalation Fast-Lane Approvals" in content
        
    print("✅ Reporting verification passed!")

if __name__ == "__main__":
    test_reporting()
