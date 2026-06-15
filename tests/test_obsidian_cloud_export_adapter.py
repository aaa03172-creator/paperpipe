from __future__ import annotations

from src.services.cloud_paper_downstream import build_cloud_paper_downstream_adapter_response
from src.services.cloud_paper_fake import get_mock_cloud_derived_artifacts
from src.services.cloud_paper_obsidian_export import render_cloud_derived_obsidian_section


def test_obsidian_cloud_export_renders_provenance_labeled_noncanonical_section() -> None:
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")
    downstream = build_cloud_paper_downstream_adapter_response(derived)

    markdown = render_cloud_derived_obsidian_section(downstream)

    assert "<!-- paperpipe:cloud-derived:start paper_id=paper_mock_ready run_id=run_paper_mock_ready -->" in markdown
    assert "<!-- paperpipe:cloud-derived:end -->" in markdown
    assert "## Cloud-Derived Context" in markdown
    assert "Canonical status: derived_noncanonical" in markdown
    assert f"Source PDF SHA256: `{derived.source_pdf_sha256}`" in markdown
    assert "- OCR `ocr_001` page 1: Mock OCR text recovered from a rendered cloud PDF page." in markdown
    assert "- Table `table_001` page 2: Mock reconstructed table from cloud PDF layout." in markdown
    assert "- Figure `figure_001` page 3: Mock figure crop from rendered cloud PDF page." in markdown
    assert "- Figure analysis `figure_analysis_001` page 3: Mock figure analysis placeholder derived from a server-side figure crop." in markdown

    for forbidden in ("gs://", "signed_url", "service_account", "/Users/", "bucket"):
        assert forbidden not in markdown


def test_obsidian_cloud_export_limits_long_context_lines() -> None:
    derived = get_mock_cloud_derived_artifacts("paper_mock_ready")
    downstream = build_cloud_paper_downstream_adapter_response(derived)
    long_candidate = downstream.candidates[0].model_copy(update={"text": "x" * 1200})
    downstream = downstream.model_copy(update={"candidates": [long_candidate, *downstream.candidates[1:]]})

    markdown = render_cloud_derived_obsidian_section(downstream, max_text_chars=80)

    assert "xxx" in markdown
    assert "..." in markdown
    assert "x" * 100 not in markdown
