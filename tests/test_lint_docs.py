from scripts.lint_docs import (
    find_unexpected_retired_stub_references,
    has_status_metadata,
)


def test_has_status_metadata_accepts_frontmatter_status() -> None:
    text = """---
title: Example
status: active
owner: repo
---

Body
"""
    assert has_status_metadata(text) is True


def test_has_status_metadata_accepts_top_header_status_line() -> None:
    text = """# Example

Status: Active
Date: 2026-03-09
Owner: Repository maintainers
Canonical: `docs/example.md`
"""
    assert has_status_metadata(text) is True


def test_has_status_metadata_ignores_body_status_mentions() -> None:
    text = """# Example

Body text.

## Details
Status: PENDING_REVIEW
"""
    assert has_status_metadata(text) is False


def test_retired_operating_note_stub_reference_is_blocked_in_active_doc() -> None:
    rel = "docs/reports/Some_Other_Report.md"
    text = (
        "Use `docs/reports/PaperPipe_Minimum_Operating_Principles_2026-03-25.md` "
        "for current operating guidance."
    )

    assert find_unexpected_retired_stub_references(rel, text) == [
        "unexpected retired compatibility stub reference in "
        "docs/reports/Some_Other_Report.md: "
        "docs/reports/PaperPipe_Minimum_Operating_Principles_2026-03-25.md"
    ]


def test_retired_operating_note_stub_reference_is_allowed_in_compatibility_note() -> None:
    rel = "docs/reports/Lightweight_Contracts_Followup_Review_2026-04-03.md"
    text = (
        "Reviewed surfaces include "
        "`docs/reports/PaperPipe_Minimum_Operating_Principles_2026-03-25.md` "
        "because it remains a compatibility stub."
    )

    assert find_unexpected_retired_stub_references(rel, text) == []


def test_retired_master_spec_stub_reference_is_blocked_in_active_doc() -> None:
    rel = "docs/reports/Some_Other_Report.md"
    text = "Use `docs/PaperPipe_v3_Master_Spec.md` as the current top-level spec."

    assert find_unexpected_retired_stub_references(rel, text) == [
        "unexpected retired compatibility stub reference in "
        "docs/reports/Some_Other_Report.md: docs/PaperPipe_v3_Master_Spec.md"
    ]


def test_retired_master_spec_stub_reference_is_allowed_in_docs_index() -> None:
    rel = "docs/README.md"
    text = (
        "Legacy aliases include `docs/Lattice_v3_UIUX_MASTER.md` and "
        "`docs/PaperPipe_v3_Master_Spec.md`."
    )

    assert find_unexpected_retired_stub_references(rel, text) == []
