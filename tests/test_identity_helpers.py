import re
import uuid
from datetime import datetime, timezone
import hashlib

from src.services.identity import (
    artifact_paper_segment,
    bridge_doc_id_to_paper_id,
    make_paper_key,
    make_runtime_paper_id,
    new_job_id,
    new_run_id,
    normalize_doi,
    paper_id_candidate_ids,
    paper_id_search_variants,
    paper_id_self_and_suffix_candidate_ids,
    paper_note_lookup_candidate_ids,
)


def test_normalize_doi_strips_prefixes_and_lowercases():
    assert normalize_doi(" https://doi.org/10.1000/AbC.123 ") == "10.1000/abc.123"
    assert normalize_doi("doi:10.2000/XYZ") == "10.2000/xyz"


def test_make_runtime_paper_id_prefers_zotero_then_doi_then_pmid():
    assert make_runtime_paper_id(zotero_key="ABCD1234", doi="10.1000/test", pmid="123") == "zotero:ABCD1234"
    assert make_runtime_paper_id(doi="https://doi.org/10.1000/Test") == "doi:10.1000/test"
    assert make_runtime_paper_id(pmid="12345") == "pmid:12345"


def test_make_runtime_paper_id_uses_content_hash_for_existing_file(tmp_path):
    first = tmp_path / "first.pdf"
    second = tmp_path / "renamed.pdf"
    payload = b"%PDF-1.4\nsame bytes\n"
    first.write_bytes(payload)
    second.write_bytes(payload)

    expected = f"userpdf-{hashlib.sha1(payload).hexdigest()[:16]}"

    assert make_runtime_paper_id(file_path=first) == expected
    assert make_runtime_paper_id(file_path=second) == expected


def test_make_runtime_paper_id_falls_back_to_path_hash_for_missing_file(tmp_path):
    missing = tmp_path / "missing.pdf"

    paper_id = make_runtime_paper_id(file_path=missing)

    assert paper_id.startswith("file:")
    assert "/" not in paper_id


def test_bridge_doc_id_to_paper_id_preserves_prefixed_ids():
    assert bridge_doc_id_to_paper_id("doi:10.1000/Test") == "doi:10.1000/test"
    assert bridge_doc_id_to_paper_id("pmid:12345") == "pmid:12345"
    assert bridge_doc_id_to_paper_id("zotero:ABCD1234") == "zotero:ABCD1234"


def test_bridge_doc_id_to_paper_id_hashes_file_ids():
    bridged = bridge_doc_id_to_paper_id("file:sample/path/paper.pdf")
    assert bridged.startswith("file:")
    assert "/" not in bridged
    assert bridged == bridge_doc_id_to_paper_id("file:sample/path/paper.pdf")


def test_paper_id_candidate_ids_expands_zotero_variants_without_duplicates():
    assert paper_id_candidate_ids("zotero:ABC123") == ["zotero:ABC123", "ABC123"]
    assert paper_id_candidate_ids("ABC123") == ["ABC123", "zotero:ABC123"]
    assert paper_id_candidate_ids("doi:10.1000/test") == ["doi:10.1000/test"]
    assert paper_id_candidate_ids(" zotero:ABC123 ") == ["zotero:ABC123", "ABC123"]
    assert paper_id_candidate_ids("") == []


def test_paper_id_self_and_suffix_candidate_ids_preserves_ops_summary_lookup_contract():
    assert paper_id_self_and_suffix_candidate_ids("zotero:ABC123") == ["zotero:ABC123", "ABC123"]
    assert paper_id_self_and_suffix_candidate_ids("ABC123") == ["ABC123"]
    assert paper_id_self_and_suffix_candidate_ids("doi:10.1000/test") == ["doi:10.1000/test", "10.1000/test"]
    assert paper_id_self_and_suffix_candidate_ids(" zotero:ABC123 ") == ["zotero:ABC123", "ABC123"]
    assert paper_id_self_and_suffix_candidate_ids("") == []


def test_paper_id_search_variants_include_cleaned_note_lookup_forms():
    assert paper_id_search_variants("zotero:ABC123") == ["zotero:ABC123", "zoteroABC123", "ABC123"]
    assert paper_id_search_variants("doi:10.1000/test") == [
        "doi:10.1000/test",
        "doi10.1000/test",
        "10.1000/test",
    ]
    assert paper_id_search_variants("ABC123") == ["ABC123"]
    assert paper_id_search_variants("") == []


def test_paper_note_lookup_candidate_ids_adds_zotero_forms_for_plain_ids():
    assert paper_note_lookup_candidate_ids("ABC123") == ["ABC123", "zotero:ABC123", "zoteroABC123"]
    assert paper_note_lookup_candidate_ids("zotero:ABC123") == ["zotero:ABC123", "zoteroABC123", "ABC123"]
    assert paper_note_lookup_candidate_ids("doi:10.1000/test") == [
        "doi:10.1000/test",
        "doi10.1000/test",
        "10.1000/test",
    ]


def test_new_job_id_returns_uuid_string():
    assert isinstance(uuid.UUID(new_job_id()), uuid.UUID)


def test_new_run_id_includes_timestamp_and_unique_suffix():
    run_id = new_run_id(datetime(2026, 3, 13, 12, 34, 56, tzinfo=timezone.utc))
    second_run_id = new_run_id(datetime(2026, 3, 13, 12, 34, 56, tzinfo=timezone.utc))
    assert run_id.startswith("run_20260313_123456_")
    assert re.fullmatch(r"run_\d{8}_\d{6}_[0-9a-f]{8}", run_id)
    assert second_run_id != run_id


def test_make_paper_key_is_stable_and_safe():
    key = make_paper_key("doi:10.1000/test")
    assert key.startswith("paper_")
    assert "/" not in key
    assert ":" not in key
    assert key == make_paper_key("doi:10.1000/test")


def test_artifact_paper_segment_preserves_safe_ids_and_hashes_unsafe_ids():
    assert artifact_paper_segment("paper_safe_001") == "paper_safe_001"
    unsafe = artifact_paper_segment("doi:10.1000/test")
    assert unsafe.startswith("paper_")
    assert unsafe != "doi:10.1000/test"
