from src.services.pr_scope_guard import (
    classify_scope,
    classify_title_scope,
    infer_title_policy,
    is_doc_file,
    normalize_paths,
)


def test_is_doc_file_recognizes_docs_folder_and_root_markdown():
    assert is_doc_file("docs/Pending_PR_Queue.md") is True
    assert is_doc_file("README.md") is True
    assert is_doc_file("src/processor.py") is False


def test_normalize_paths_filters_empty_and_backslashes():
    assert normalize_paths(["", "  ", "docs\\x.md", "src\\a.py"]) == ["docs/x.md", "src/a.py"]


def test_classify_scope_allows_docs_only():
    report = classify_scope(["docs/Pending_PR_Queue.md", "docs/ops.md"])
    assert report.has_mixed_scope is False
    assert report.is_allowed is True
    assert report.code_files == []


def test_classify_scope_allows_code_only():
    report = classify_scope(["src/processor.py", "tests/test_processor.py"])
    assert report.has_mixed_scope is False
    assert report.is_allowed is True
    assert report.doc_files == []


def test_classify_scope_blocks_mixed_scope_for_non_allowed_doc():
    report = classify_scope(["src/processor.py", "docs/archive/Next_Feature_Kickoff_Checklist_2026-02-19.md"])
    assert report.has_mixed_scope is True
    assert report.is_allowed is False
    assert report.blocked_doc_files == ["docs/archive/Next_Feature_Kickoff_Checklist_2026-02-19.md"]


def test_classify_scope_allows_mixed_scope_for_queue_sync_doc():
    report = classify_scope(["src/processor.py", "docs/Pending_PR_Queue.md"])
    assert report.has_mixed_scope is True
    assert report.is_allowed is True
    assert report.allowed_doc_files == ["docs/Pending_PR_Queue.md"]
    assert report.blocked_doc_files == []


def test_infer_title_policy_detects_docs_and_test_prefixes():
    assert infer_title_policy("docs(queue): close batch") == "docs"
    assert infer_title_policy("test(api): add contract checks") == "test"
    assert infer_title_policy("feat(api): add endpoint") == "none"


def test_classify_title_scope_allows_docs_title_for_docs_only_files():
    report = classify_title_scope("docs(queue): sync tracker", ["docs/Pending_PR_Queue.md"])
    assert report.policy == "docs"
    assert report.is_allowed is True
    assert report.violating_files == []


def test_classify_title_scope_blocks_docs_title_when_code_present():
    report = classify_title_scope("docs(queue): sync tracker", ["docs/Pending_PR_Queue.md", "src/cli.py"])
    assert report.policy == "docs"
    assert report.is_allowed is False
    assert report.violating_files == ["src/cli.py"]


def test_classify_title_scope_allows_test_title_for_tests_and_queue_doc():
    report = classify_title_scope(
        "test(api): harden sse contract",
        ["tests/test_jobs_api_smoke.py", "docs/Pending_PR_Queue.md"],
    )
    assert report.policy == "test"
    assert report.is_allowed is True
    assert report.violating_files == []


def test_classify_title_scope_blocks_test_title_when_non_test_file_present():
    report = classify_title_scope(
        "test(api): harden sse contract",
        ["tests/test_jobs_api_smoke.py", "src/services/downloader_ops_metrics.py"],
    )
    assert report.policy == "test"
    assert report.is_allowed is False
    assert report.violating_files == ["src/services/downloader_ops_metrics.py"]
