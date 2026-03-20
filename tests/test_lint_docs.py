from scripts.lint_docs import has_status_metadata


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
