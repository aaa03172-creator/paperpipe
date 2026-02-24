from src.services.pr_scope_guard import classify_scope, is_doc_file, normalize_paths


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
    report = classify_scope(["src/processor.py", "docs/Next_Feature_Kickoff_Checklist_2026-02-19.md"])
    assert report.has_mixed_scope is True
    assert report.is_allowed is False
    assert report.blocked_doc_files == ["docs/Next_Feature_Kickoff_Checklist_2026-02-19.md"]


def test_classify_scope_allows_mixed_scope_for_queue_sync_doc():
    report = classify_scope(["src/processor.py", "docs/Pending_PR_Queue.md"])
    assert report.has_mixed_scope is True
    assert report.is_allowed is True
    assert report.allowed_doc_files == ["docs/Pending_PR_Queue.md"]
    assert report.blocked_doc_files == []
