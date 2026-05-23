import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from fastapi.testclient import TestClient

import src.db_utils as db_utils
import src.services.paper_ops_summary as paper_ops_summary
from backend import main as api_main
from backend.routers import paper_notes as paper_notes_router
from src.services.path_masking import mask_local_path
from src.schemas.paper_notes import PaperNoteIndexItem, PaperNoteOpsSummary


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_artifact_run(path: Path, *, claimset: dict | None = None, stats_report: dict | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if claimset is not None:
        (path / "claimset.resolved.json").write_text(json.dumps(claimset), encoding="utf-8")
    if stats_report is not None:
        (path / "stats_report.json").write_text(json.dumps(stats_report), encoding="utf-8")


def _note_content(
    *,
    note_id: str,
    alias: str,
    doi: str | None = None,
    pdf_url: str | None = None,
) -> str:
    frontmatter_lines = [
        "---",
        f"id: {note_id}",
        f"aliases: [\"{alias}\"]",
        "tags:",
        "  - Medicine/Neurology",
        "date_processed: 2026-02-24",
        "confidence: 0.9",
        "status: INDEXED",
    ]
    if doi is not None:
        frontmatter_lines.append(f"doi: {doi}")
    if pdf_url is not None:
        frontmatter_lines.append(f"pdf_url: {pdf_url}")
    frontmatter_lines.append("---")
    return (
        "\n".join(frontmatter_lines)
        + "\n\n"
        f"# {alias}\n\n"
        "## References\n"
        + (f"- [Open PDF]({pdf_url})\n" if pdf_url else "")
    )


def test_visible_paper_candidate_window_prefers_non_fixtures_and_keeps_stable_order(monkeypatch):
    non_fixture_heap: list[tuple[float, int, dict]] = []
    fixture_heap: list[tuple[float, int, dict]] = []
    candidates = [
        {
            "sort_updated_at": "2026-04-17T03:00:00Z",
            "fixture_record": {"paper_id": "paper-e2e-001", "title": "E2E fixture"},
            "paper_id": "paper-e2e-001",
        },
        {
            "sort_updated_at": "2026-04-17T02:00:00Z",
            "fixture_record": {"paper_id": "real-paper-002", "title": "Real paper two"},
            "paper_id": "real-paper-002",
        },
        {
            "sort_updated_at": "2026-04-17T02:00:00Z",
            "fixture_record": {"paper_id": "real-paper-001", "title": "Real paper one"},
            "paper_id": "real-paper-001",
        },
    ]

    any_non_fixture = False
    any_fixture = False
    for sequence, candidate in enumerate(candidates):
        if api_main.is_test_fixture_paper_record(candidate["fixture_record"]):
            any_fixture = True
            api_main._push_visible_paper_candidate_window(
                fixture_heap,
                candidate,
                sequence=sequence,
                target_count=2,
            )
        else:
            any_non_fixture = True
            api_main._push_visible_paper_candidate_window(
                non_fixture_heap,
                candidate,
                sequence=sequence,
                target_count=2,
            )

    monkeypatch.setattr(
        api_main,
        "is_test_fixture_paper_record",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("finalize should trust the existing fixture/non-fixture heap partition")
        ),
    )

    class _UnexpectedFixtureHeapIteration(list):
        def __iter__(self):
            raise AssertionError("finalize should not merge fixture heap when non-fixtures are visible")

    selected, fixtures_only = api_main._finalize_visible_paper_candidate_window(
        non_fixture_heap=non_fixture_heap,
        fixture_heap=_UnexpectedFixtureHeapIteration(fixture_heap),
        any_non_fixture=any_non_fixture,
        any_fixture=any_fixture,
        include_test_fixtures=False,
        offset=0,
        limit=2,
    )

    assert fixtures_only is False
    assert [candidate["paper_id"] for candidate in selected] == [
        "real-paper-002",
        "real-paper-001",
    ]


def test_visible_paper_candidate_window_keeps_fixture_candidates_when_opted_in(monkeypatch):
    monkeypatch.setenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", "1")
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    non_fixture_heap: list[tuple[float, int, dict]] = []
    fixture_heap: list[tuple[float, int, dict]] = []
    candidates = [
        {
            "sort_updated_at": "2026-04-17T03:00:00Z",
            "fixture_record": {"paper_id": "paper-e2e-001", "title": "E2E fixture"},
            "paper_id": "paper-e2e-001",
        },
        {
            "sort_updated_at": "2026-04-17T02:00:00Z",
            "fixture_record": {"paper_id": "real-paper-002", "title": "Real paper two"},
            "paper_id": "real-paper-002",
        },
        {
            "sort_updated_at": "2026-04-17T02:00:00Z",
            "fixture_record": {"paper_id": "real-paper-001", "title": "Real paper one"},
            "paper_id": "real-paper-001",
        },
    ]

    any_non_fixture = False
    any_fixture = False
    for sequence, candidate in enumerate(candidates):
        if api_main.is_test_fixture_paper_record(candidate["fixture_record"]):
            any_fixture = True
            api_main._push_visible_paper_candidate_window(
                fixture_heap,
                candidate,
                sequence=sequence,
                target_count=2,
            )
        else:
            any_non_fixture = True
            api_main._push_visible_paper_candidate_window(
                non_fixture_heap,
                candidate,
                sequence=sequence,
                target_count=2,
            )

    selected, fixtures_only = api_main._finalize_visible_paper_candidate_window(
        non_fixture_heap=non_fixture_heap,
        fixture_heap=fixture_heap,
        any_non_fixture=any_non_fixture,
        any_fixture=any_fixture,
        include_test_fixtures=True,
        offset=0,
        limit=2,
    )

    assert fixtures_only is False
    assert [candidate["paper_id"] for candidate in selected] == [
        "paper-e2e-001",
        "real-paper-002",
    ]


def test_paper_note_identity_sets_cache_variants_per_item(monkeypatch):
    item = PaperNoteIndexItem(
        slug="cached-note-slug",
        id="zotero:cached-note-id",
        title="Cached note",
        note_path="Inbox/PaperPipe/Cached note.md",
    )
    original_helper = api_main._paper_id_identity_sets
    call_count = 0

    def _counted_identity_sets(paper_id: str):
        nonlocal call_count
        call_count += 1
        return original_helper(paper_id)

    monkeypatch.setattr(api_main, "_paper_id_identity_sets", _counted_identity_sets)

    first = api_main._paper_note_identity_sets(item)
    second = api_main._paper_note_identity_sets(item)

    assert first == second
    assert call_count == 2


def test_paper_note_listing_candidate_metadata_cache_per_item(monkeypatch):
    item = PaperNoteIndexItem(
        slug="paper-e2e-cached-slug",
        id="zotero:paper-e2e-cached-id",
        title="Cached listing candidate",
        note_path="Inbox/PaperPipe/Cached listing candidate.md",
        updated_at="2026-04-17T12:00:00Z",
    )
    original_fixture_checker = api_main.is_test_fixture_paper_record
    call_count = 0

    def _counted_fixture_checker(record):
        nonlocal call_count
        call_count += 1
        return original_fixture_checker(record)

    monkeypatch.setattr(api_main, "is_test_fixture_paper_record", _counted_fixture_checker)

    first = api_main._paper_note_listing_candidate_metadata(item)
    second = api_main._paper_note_listing_candidate_metadata(item)

    assert first == (
        "zotero:paper-e2e-cached-id",
        "Cached listing candidate",
        "2026-04-17T12:00:00Z",
        False,
    )
    assert second == first
    assert call_count == 1


def test_paper_note_fixture_preview_cache_per_item(monkeypatch):
    item = PaperNoteIndexItem(
        slug="paper-e2e-preview-slug",
        id="paper-e2e-preview-id",
        title="E2E Preview Fixture",
        note_path="Inbox/PaperPipe/E2E Preview Fixture.md",
    )
    original_fixture_checker = api_main.is_test_fixture_paper_record
    call_count = 0

    def _counted_fixture_checker(record):
        nonlocal call_count
        call_count += 1
        return original_fixture_checker(record)

    monkeypatch.setattr(api_main, "is_test_fixture_paper_record", _counted_fixture_checker)

    first = api_main._paper_note_fixture_preview_is_fixture(item)
    second = api_main._paper_note_fixture_preview_is_fixture(item)

    assert first is True
    assert second is True
    assert call_count == 1


def test_paper_note_ops_candidate_group_key_cache_per_item(monkeypatch):
    item = PaperNoteIndexItem(
        slug="paper-note-group-cache-slug",
        id="zotero:paper-note-group-cache-id",
        title="Paper note group cache",
        note_path="Inbox/PaperPipe/Paper note group cache.md",
    )
    original_group_key_helper = api_main._normalized_candidate_id_group
    call_count = 0

    def _counted_group_key(candidate_ids):
        nonlocal call_count
        call_count += 1
        return original_group_key_helper(candidate_ids)

    monkeypatch.setattr(api_main, "_normalized_candidate_id_group", _counted_group_key)

    first = api_main._paper_note_ops_candidate_group_key(item)
    second = api_main._paper_note_ops_candidate_group_key(item)

    assert first == second
    assert call_count == 1


def test_paper_note_artifact_candidate_ids_populate_runtime_group_key_cache(monkeypatch):
    item = PaperNoteIndexItem(
        slug="paper-note-artifact-group-cache-slug",
        id="zotero:paper-note-artifact-group-cache-id",
        title="Paper note artifact group cache",
        note_path="Inbox/PaperPipe/Paper note artifact group cache.md",
    )

    artifact_candidate_ids = tuple(api_main._paper_note_artifact_candidate_ids(item))

    monkeypatch.setattr(
        api_main,
        "_paper_note_identity_sets",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("artifact candidate helper should populate the runtime note group key cache")
        ),
    )

    assert api_main._paper_note_ops_candidate_group_key(item) == artifact_candidate_ids


def test_artifact_cache_candidate_helpers_normalize_ids_before_lookup():
    artifact_cache: paper_ops_summary.ArtifactSnapshotCache = {
        "paper_artifact_cache_normalized": paper_ops_summary.ArtifactOperationalSnapshot(
            paper_id="paper_artifact_cache_normalized",
            run_id="run-artifact-cache-normalized",
            updated_at="2026-04-23T00:00:00+00:00",
            mtime=1.0,
            has_claimset=True,
            has_stats_report=True,
            stats_check_count=1,
        )
    }
    candidate_ids = ["", " paper_artifact_cache_normalized ", "paper_artifact_cache_normalized", "  "]

    ops_summary = api_main._ops_summary_from_artifact_cache_for_candidate_ids(
        candidate_ids,
        artifact_cache,
    )

    assert ops_summary is not api_main._UNCACHED_ARTIFACT_GROUP
    assert ops_summary.latest_run_id == "run-artifact-cache-normalized"
    assert api_main._latest_run_id_from_artifact_cache_for_candidate_ids(
        candidate_ids,
        artifact_cache,
    ) == "run-artifact-cache-normalized"
    assert api_main._artifact_cache_covers_candidate_ids(candidate_ids, artifact_cache) is True


def test_normalized_candidate_id_group_uses_shared_normalization_boundary(monkeypatch):
    original_normalized_candidate_id_list = api_main._normalized_candidate_id_list
    calls: list[tuple[str, ...]] = []

    def _record_normalized_candidate_id_list(candidate_ids):
        values = tuple(candidate_ids)
        calls.append(values)
        return original_normalized_candidate_id_list(values)

    monkeypatch.setattr(api_main, "_normalized_candidate_id_list", _record_normalized_candidate_id_list)

    group_key = api_main._normalized_candidate_id_group(
        [" beta ", "", "alpha", "beta", "  "]
    )

    assert group_key == ("alpha", "beta")
    assert calls == [(" beta ", "", "alpha", "beta", "  ")]


def test_selected_note_candidate_id_groups_skip_group_key_for_single_note_window(monkeypatch):
    item = PaperNoteIndexItem(
        slug="single-note-window-slug",
        id="zotero:single-note-window-id",
        title="Single note window",
        note_path="Inbox/PaperPipe/Single note window.md",
    )

    monkeypatch.setattr(
        api_main,
        "_paper_note_ops_candidate_group_key",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("single-note selected windows should not compute preload group keys")
        ),
    )

    assert api_main._selected_note_candidate_id_groups(
        [
            {
                "kind": "note",
                "paper_id": "zotero:single-note-window-id",
                "note_item": item,
            }
        ]
    ) == []


def test_preload_artifact_snapshots_caches_jobs_misses_without_blocking_fs_only_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        fs_only_run_dir = artifacts_dir / "paper_fs_only_artifact" / "run-fs-only"
        fs_only_run_dir.mkdir(parents=True, exist_ok=True)

        artifact_cache: paper_ops_summary.ArtifactSnapshotCache = {}
        api_main._preload_artifact_snapshots_for_candidate_id_groups(
            artifacts_dir,
            [
                ["paper_missing_no_artifact_dir"],
                ["paper_fs_only_artifact"],
            ],
            artifact_cache,
        )

        assert artifact_cache["paper_missing_no_artifact_dir"] is None
        assert "paper_fs_only_artifact" not in artifact_cache
    finally:
        db_utils.DB_PATH = original_db_path


def test_preload_artifact_snapshots_skips_candidate_ids_already_in_request_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    original_get_db_connection = api_main.get_db_connection
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        run_dir = artifacts_dir / "paper_uncached" / "run-uncached"
        _write_artifact_run(
            run_dir,
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": [{"id": "check-1"}]},
        )
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("job-uncached", "run-uncached", "paper_uncached", "completed", str(run_dir)),
        )
        conn.commit()
        conn.close()

        executed_queries: list[tuple[str, tuple[object, ...]]] = []

        class _RecordingConnection:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, params=()):
                executed_queries.append((" ".join(str(sql).split()), tuple(params)))
                return self._inner.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        def _recording_get_db_connection():
            return _RecordingConnection(original_get_db_connection())

        monkeypatch.setattr(api_main, "get_db_connection", _recording_get_db_connection)

        artifact_cache: paper_ops_summary.ArtifactSnapshotCache = {
            "paper_cached_hit": paper_ops_summary.ArtifactOperationalSnapshot(
                paper_id="paper_cached_hit",
                run_id="run-cached-hit",
                updated_at="2026-04-22T00:00:00+00:00",
                mtime=2.0,
                has_claimset=True,
                has_stats_report=True,
                stats_check_count=1,
            ),
            "paper_cached_miss": None,
        }
        api_main._preload_artifact_snapshots_for_candidate_id_groups(
            artifacts_dir,
            [
                ["", "paper_cached_hit", " paper_uncached "],
                ["  ", "paper_cached_miss", "paper_uncached"],
            ],
            artifact_cache,
        )

        jobs_queries = [
            params
            for query, params in executed_queries
            if "FROM jobs" in query and "paper_id IN (" in query
        ]
        assert jobs_queries == [("paper_uncached",)]
        assert "" not in artifact_cache
        assert "  " not in artifact_cache
        assert artifact_cache["paper_uncached"] is not None
        assert artifact_cache["paper_uncached"].run_id == "run-uncached"
    finally:
        db_utils.DB_PATH = original_db_path


def test_build_note_item_lookup_for_paper_ids_resolves_targets_without_partial_re_resolve(monkeypatch):
    matching_item = PaperNoteIndexItem(
        slug="targeted-note-slug",
        id="paper_targeted_lookup",
        title="Targeted lookup",
        note_path="Inbox/PaperPipe/Targeted lookup.md",
    )
    unrelated_item = PaperNoteIndexItem(
        slug="unrelated-note-slug",
        id="zotero:unrelatedTargetedLookup2026",
        title="Unrelated lookup",
        note_path="Inbox/PaperPipe/Unrelated lookup.md",
    )
    original_resolver = api_main._resolve_note_item_for_paper_id_from_lookup

    def _unexpected_partial_resolve(*args, **kwargs):
        raise AssertionError("targeted note lookup helper should not repeatedly re-resolve remaining paper ids")

    monkeypatch.setattr(api_main, "_resolve_note_item_for_paper_id_from_lookup", _unexpected_partial_resolve)

    lookup = api_main._build_note_item_lookup_for_paper_ids(
        [matching_item, unrelated_item],
        ["paper_targeted_lookup"],
    )

    assert original_resolver(lookup, "paper_targeted_lookup") is matching_item


def test_build_note_item_lookup_for_paper_ids_indexes_only_requested_candidates():
    matching_item = PaperNoteIndexItem(
        slug="targeted-note-slug",
        id="paper_targeted_lookup",
        title="Targeted lookup",
        note_path="Inbox/PaperPipe/Targeted lookup.md",
    )
    unrelated_item = PaperNoteIndexItem(
        slug="unrelated-note-slug",
        id="zotero:unrelatedTargetedLookup2026",
        title="Unrelated lookup",
        note_path="Inbox/PaperPipe/Unrelated lookup.md",
    )

    lookup = api_main._build_note_item_lookup_for_paper_ids(
        [matching_item, unrelated_item],
        ["paper_targeted_lookup"],
    )

    requested_exact_candidates = set(paper_notes_router._paper_note_lookup_candidates("paper_targeted_lookup"))
    requested_normalized_candidates = {
        normalized
        for candidate in requested_exact_candidates
        if (normalized := paper_notes_router._normalize_paper_note_id(candidate))
    }
    matching_raw_variants, matching_normalized_variants = api_main._paper_note_identity_sets(matching_item)
    unrelated_raw_variants, unrelated_normalized_variants = api_main._paper_note_identity_sets(unrelated_item)

    assert set(lookup.exact) == (matching_raw_variants & requested_exact_candidates)
    assert set(lookup.normalized) == (matching_normalized_variants & requested_normalized_candidates)
    assert not (set(lookup.exact) & unrelated_raw_variants)
    assert not (set(lookup.normalized) & unrelated_normalized_variants)


def test_build_note_backed_paper_item_skips_resolve_when_note_index_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
    monkeypatch.setattr(api_main, "_load_deduped_note_items_without_ops", lambda vault_path: [])
    monkeypatch.setattr(
        api_main,
        "_resolve_note_backed_paper_item",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("note-backed paper helper should not resolve when the note index is empty")
        ),
    )

    assert api_main._build_note_backed_paper_item("paper-empty-note-index") is None


def test_build_note_backed_pdf_path_skips_resolve_when_note_index_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
    monkeypatch.setattr(api_main, "_load_deduped_note_items_without_ops", lambda vault_path: [])
    monkeypatch.setattr(
        api_main,
        "_resolve_note_backed_pdf_path_for_paper_id",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("note-backed pdf helper should not resolve when the note index is empty")
        ),
    )

    assert api_main._build_note_backed_pdf_path("paper-empty-note-index") is None


def test_note_backed_row_builders_reuse_preloaded_artifact_cache_for_ops_summary(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    note_title = "Note Backed Preloaded Ops Cache"
    note_id = "zotero:noteBackedPreloadedOps2026"
    note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
    _write(
        note_path,
        _note_content(
            note_id=note_id,
            alias=note_title,
            doi="10.1000/note-backed-preloaded-ops",
        ),
    )

    item = PaperNoteIndexItem(
        slug="noteBackedPreloadedOps2026",
        id=note_id,
        title=note_title,
        note_path="Inbox/PaperPipe/Note Backed Preloaded Ops Cache.md",
        status="INDEXED",
        updated_at="2026-04-22T00:00:00Z",
    )
    candidate_ids, _ = api_main._paper_note_identity_sets(item)
    artifact_cache = {
        candidate_id: paper_ops_summary.ArtifactOperationalSnapshot(
            paper_id=candidate_id,
            run_id="run-note-backed-preloaded-ops",
            updated_at="2026-04-22T00:00:00+00:00",
            mtime=1.0,
            has_claimset=True,
            has_stats_report=True,
            stats_check_count=1,
        )
        for candidate_id in candidate_ids
    }

    monkeypatch.setattr(
        api_main,
        "build_ops_summary_for_candidate_ids",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("note-backed row builders should reuse preloaded artifact cache before rebuilding ops summary")
        ),
    )
    monkeypatch.setattr(
        api_main,
        "_latest_run_id_from_artifact_cache_for_candidate_ids",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("note-backed item builder should not rescan artifact latest-run state when ops summary has a run id")
        ),
    )

    built_item = api_main._build_note_backed_paper_item_from_index_item(
        vault_dir,
        item,
        paper_id=note_id,
        artifact_cache=artifact_cache,
        artifacts_path=tmp_path / "artifacts",
    )
    built_rail_item = api_main._build_note_backed_paper_rail_item_from_index_item(
        vault_dir,
        item,
        paper_id=note_id,
        artifact_cache=artifact_cache,
        artifacts_path=tmp_path / "artifacts",
    )

    assert built_item is not None
    assert built_item[0]["ops_summary"].state == "healthy"
    assert built_item[0]["latest_run_id"] == "run-note-backed-preloaded-ops"
    assert built_rail_item is not None
    assert built_rail_item["ops_summary"].state == "healthy"


def test_note_backed_row_builders_reuse_cached_group_key_before_identity_sets(tmp_path, monkeypatch):
    vault_dir = tmp_path / "vault"
    note_title = "Note Backed Cached Group Key"
    note_id = "zotero:noteBackedCachedGroupKey2026"
    note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
    _write(
        note_path,
        _note_content(
            note_id=note_id,
            alias=note_title,
            doi="10.1000/note-backed-cached-group-key",
        ),
    )

    item = PaperNoteIndexItem(
        slug="noteBackedCachedGroupKey2026",
        id=note_id,
        title=note_title,
        note_path="Inbox/PaperPipe/Note Backed Cached Group Key.md",
        status="INDEXED",
        updated_at="2026-04-22T00:00:00Z",
    )
    cached_group_key = tuple(api_main._paper_note_ops_candidate_group_key(item))
    artifact_cache = {
        candidate_id: paper_ops_summary.ArtifactOperationalSnapshot(
            paper_id=candidate_id,
            run_id="run-note-backed-cached-group-key",
            updated_at="2026-04-22T00:00:00+00:00",
            mtime=1.0,
            has_claimset=True,
            has_stats_report=True,
            stats_check_count=1,
        )
        for candidate_id in cached_group_key
    }

    monkeypatch.setattr(
        api_main,
        "_paper_note_identity_sets",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("note-backed row builders should reuse cached group keys before recomputing identity sets")
        ),
    )

    built_item = api_main._build_note_backed_paper_item_from_index_item(
        vault_dir,
        item,
        paper_id=note_id,
        artifact_cache=artifact_cache,
        artifacts_path=tmp_path / "artifacts",
    )
    built_rail_item = api_main._build_note_backed_paper_rail_item_from_index_item(
        vault_dir,
        item,
        paper_id=note_id,
        artifact_cache=artifact_cache,
        artifacts_path=tmp_path / "artifacts",
    )

    assert built_item is not None
    assert built_item[0]["latest_run_id"] == "run-note-backed-cached-group-key"
    assert built_rail_item is not None
    assert built_rail_item["ops_summary"].latest_run_id == "run-note-backed-cached-group-key"


def test_note_backed_paper_item_skips_ops_candidate_ids_when_artifact_cache_already_covers_note_clear_miss(
    tmp_path, monkeypatch
):
    vault_dir = tmp_path / "vault"
    note_title = "Note Backed Clear Miss Group Cache"
    note_id = "zotero:noteBackedClearMissGroupCache2026"
    note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
    _write(
        note_path,
        _note_content(
            note_id=note_id,
            alias=note_title,
            doi="10.1000/note-backed-clear-miss-group-cache",
        ),
    )

    item = PaperNoteIndexItem(
        slug="noteBackedClearMissGroupCache2026",
        id=note_id,
        title=note_title,
        note_path="Inbox/PaperPipe/Note Backed Clear Miss Group Cache.md",
        status="INDEXED",
        updated_at="2026-04-22T00:00:00Z",
    )
    candidate_ids = tuple(api_main._paper_note_artifact_candidate_ids(item))
    artifact_cache = {candidate_id: None for candidate_id in candidate_ids}

    monkeypatch.setattr(
        api_main,
        "_ops_summary_candidate_ids",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("note-backed builder should not rebuild route candidate ids after note artifact clear miss is proven")
        ),
    )

    built_item = api_main._build_note_backed_paper_item_from_index_item(
        vault_dir,
        item,
        paper_id=note_id,
        artifact_cache=artifact_cache,
        artifacts_path=tmp_path / "artifacts",
    )

    assert built_item is not None
    assert built_item[0]["latest_run_id"] is None
    assert built_item[0]["ops_summary"] is None


def test_note_backed_paper_item_skips_clear_miss_coverage_when_artifact_run_is_already_present(
    tmp_path, monkeypatch
):
    vault_dir = tmp_path / "vault"
    note_title = "Note Backed Artifact Hit"
    note_id = "zotero:noteBackedArtifactHit2026"
    note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
    _write(
        note_path,
        _note_content(
            note_id=note_id,
            alias=note_title,
            doi="10.1000/note-backed-artifact-hit",
        ),
    )

    item = PaperNoteIndexItem(
        slug="noteBackedArtifactHit2026",
        id=note_id,
        title=note_title,
        note_path="Inbox/PaperPipe/Note Backed Artifact Hit.md",
        status="INDEXED",
        updated_at="2026-04-22T00:00:00Z",
    )
    candidate_ids = tuple(api_main._paper_note_artifact_candidate_ids(item))
    artifact_cache = {
        candidate_id: paper_ops_summary.ArtifactOperationalSnapshot(
            paper_id=candidate_id,
            run_id="run-note-backed-artifact-hit",
            updated_at="2026-04-22T00:00:00+00:00",
            mtime=1.0,
            has_claimset=False,
            has_stats_report=False,
            stats_check_count=0,
        )
        for candidate_id in candidate_ids
    }

    monkeypatch.setattr(
        api_main,
        "_artifact_cache_covers_candidate_ids",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("note-backed builder should not check clear-miss coverage after an artifact run hit is already present")
        ),
    )

    built_item = api_main._build_note_backed_paper_item_from_index_item(
        vault_dir,
        item,
        paper_id=note_id,
        artifact_cache=artifact_cache,
        artifacts_path=tmp_path / "artifacts",
    )

    assert built_item is not None
    assert built_item[0]["latest_run_id"] == "run-note-backed-artifact-hit"


def test_papers_note_iteration_stops_early_when_db_heap_already_dominates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "dominant-db.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%dominant db pdf\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_dominant_db",
                "Dominant DB paper",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-17 13:00:00",
                "2026-04-17 13:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        for idx in range(3):
            note_title = f"Older note {idx}"
            note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
            _write(
                note_path,
                _note_content(
                    note_id=f"zotero:olderNote{idx}",
                    alias=note_title,
                    doi=f"10.1000/older-note-{idx}",
                ),
            )
            os.utime(note_path, (1_710_000_000 + idx, 1_710_000_000 + idx))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_identity_sets(*args, **kwargs):
            raise AssertionError("note identity sets should not be evaluated when DB heap already dominates the page")

        monkeypatch.setattr(api_main, "_paper_note_identity_sets", _unexpected_identity_sets)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == ["paper_dominant_db"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_note_iteration_skips_note_metadata_when_db_heap_already_dominates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "dominant-db-metadata.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%dominant db metadata pdf\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_dominant_db_metadata",
                "Dominant DB metadata paper",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-17 13:00:00",
                "2026-04-17 13:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        for idx in range(2):
            note_title = f"Older metadata note {idx}"
            note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
            _write(
                note_path,
                _note_content(
                    note_id=f"zotero:olderMetadataNote{idx}",
                    alias=note_title,
                    doi=f"10.1000/older-metadata-note-{idx}",
                ),
            )
            os.utime(note_path, (1_710_000_100 + idx, 1_710_000_100 + idx))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_note_metadata(*args, **kwargs):
            raise AssertionError("note metadata should not be evaluated when DB heap already dominates the page")

        monkeypatch.setattr(api_main, "_paper_note_listing_candidate_metadata", _unexpected_note_metadata)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == ["paper_dominant_db_metadata"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_duplicate_note_match_skips_note_metadata_after_slug_backfill(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "duplicate-note-match.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%duplicate note match pdf\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_duplicate_note_match",
                "Duplicate note match",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-17 13:00:00",
                "2026-04-17 13:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        note_slug = "duplicateNoteSlug2026"
        note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_slug}.md"
        _write(
            note_path,
            _note_content(
                note_id="paper_duplicate_note_match",
                alias="Duplicate note match",
                doi="10.1000/duplicate-note-match",
            ),
        )
        os.utime(note_path, (1_710_000_100, 1_710_000_100))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_note_metadata(*args, **kwargs):
            raise AssertionError("duplicate note matches should backfill note_slug without building note metadata")

        monkeypatch.setattr(api_main, "_paper_note_listing_candidate_metadata", _unexpected_note_metadata)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})
        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        assert listing.json()[0]["paper_id"] == "paper_duplicate_note_match"
        assert listing.json()[0]["note_slug"] == note_slug
        assert rail_listing.status_code == 200
        assert rail_listing.json()[0]["paper_id"] == "paper_duplicate_note_match"
        assert rail_listing.json()[0]["note_slug"] == note_slug
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_note_iteration_skips_fixture_heap_push_when_real_note_is_already_visible(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_push = api_main._push_visible_paper_candidate_window
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_specs = [
            ("zotero:realVisibleNote2026", "Real Visible Note", 1_720_000_201),
            ("paper-e2e-hidden-fixture-note", "E2E Hidden Fixture Note", 1_720_000_200),
        ]
        for note_id, note_title, timestamp in note_specs:
            note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
            _write(
                note_path,
                _note_content(
                    note_id=note_id,
                    alias=note_title,
                    doi=f"10.1000/{note_id.replace(':', '-')}",
                ),
            )
            os.utime(note_path, (timestamp, timestamp))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        pushed_paper_ids: list[str] = []

        def _record_push(heap, candidate, *, sequence, target_count):
            pushed_paper_ids.append(str(candidate.get("paper_id") or ""))
            return original_push(heap, candidate, sequence=sequence, target_count=target_count)

        monkeypatch.setattr(api_main, "_push_visible_paper_candidate_window", _record_push)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == ["zotero:realVisibleNote2026"]
        assert pushed_paper_ids == ["zotero:realVisibleNote2026"]
    finally:
        api_main._push_visible_paper_candidate_window = original_push
        db_utils.DB_PATH = original_db_path


def test_papers_hidden_fixture_note_skips_metadata_when_real_note_is_already_visible(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_metadata_helper = api_main._paper_note_listing_candidate_metadata
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_specs = [
            ("zotero:realVisibleMetadataNote2026", "Real Visible Metadata Note", 1_720_000_301),
            ("paper-e2e-hidden-fixture-metadata-note", "E2E Hidden Fixture Metadata Note", 1_720_000_300),
        ]
        for note_id, note_title, timestamp in note_specs:
            note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
            _write(
                note_path,
                _note_content(
                    note_id=note_id,
                    alias=note_title,
                    doi=f"10.1000/{note_id.replace(':', '-')}",
                ),
            )
            os.utime(note_path, (timestamp, timestamp))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _guarded_metadata(note_item):
            if str(getattr(note_item, "id", "") or "").strip() == "paper-e2e-hidden-fixture-metadata-note":
                raise AssertionError("hidden fixture notes should not build listing metadata after a real note is visible")
            return original_metadata_helper(note_item)

        monkeypatch.setattr(api_main, "_paper_note_listing_candidate_metadata", _guarded_metadata)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == ["zotero:realVisibleMetadataNote2026"]
    finally:
        api_main._paper_note_listing_candidate_metadata = original_metadata_helper
        db_utils.DB_PATH = original_db_path


def test_papers_hidden_fixture_note_without_slug_skips_identity_sets_when_real_note_is_already_visible(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_identity_helper = api_main._paper_note_identity_sets
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        monkeypatch.setattr(
            api_main.paper_notes,
            "_resolve_vault_path",
            lambda: tmp_path / "vault",
        )
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="zotero:realVisibleIdentityNote2026",
                    slug="real-visible-identity-note",
                    title="Real Visible Identity Note",
                    note_path="Inbox/PaperPipe/Real Visible Identity Note.md",
                    status="NEW",
                    updated_at="2026-07-08T09:25:00Z",
                ),
                PaperNoteIndexItem(
                    id="paper-e2e-hidden-fixture-identity-note",
                    slug="",
                    title="E2E Hidden Fixture Identity Note",
                    note_path="Inbox/PaperPipe/E2E Hidden Fixture Identity Note.md",
                    status="INDEXED",
                    updated_at="2026-07-08T09:24:00Z",
                ),
            ],
            raising=False,
        )

        def _guarded_identity_sets(note_item):
            if str(getattr(note_item, "id", "") or "").strip() == "paper-e2e-hidden-fixture-identity-note":
                raise AssertionError(
                    "hidden fixture notes without slug should not build identity sets after a real note is visible"
                )
            return original_identity_helper(note_item)

        monkeypatch.setattr(api_main, "_paper_note_identity_sets", _guarded_identity_sets)

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=0)

        assert [candidate["paper_id"] for candidate in page.selected_candidates] == [
            "zotero:realVisibleIdentityNote2026"
        ]
    finally:
        api_main._paper_note_identity_sets = original_identity_helper
        db_utils.DB_PATH = original_db_path


def test_papers_hidden_fixture_note_with_slug_skips_identity_sets_in_note_only_mixed_window(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_identity_helper = api_main._paper_note_identity_sets
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        monkeypatch.setattr(
            api_main.paper_notes,
            "_resolve_vault_path",
            lambda: tmp_path / "vault",
        )
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="zotero:realVisibleSlugIdentityNote2026",
                    slug="real-visible-slug-identity-note",
                    title="Real Visible Slug Identity Note",
                    note_path="Inbox/PaperPipe/Real Visible Slug Identity Note.md",
                    status="NEW",
                    updated_at="2026-07-09T09:25:00Z",
                ),
                PaperNoteIndexItem(
                    id="paper-e2e-hidden-fixture-slug-identity-note",
                    slug="hidden-fixture-slug-identity-note",
                    title="E2E Hidden Fixture Slug Identity Note",
                    note_path="Inbox/PaperPipe/E2E Hidden Fixture Slug Identity Note.md",
                    status="INDEXED",
                    updated_at="2026-07-09T09:24:00Z",
                ),
            ],
            raising=False,
        )

        def _guarded_identity_sets(note_item):
            if str(getattr(note_item, "id", "") or "").strip() == "paper-e2e-hidden-fixture-slug-identity-note":
                raise AssertionError(
                    "hidden fixture notes in note-only mixed windows should not build identity sets after a real note is visible"
                )
            return original_identity_helper(note_item)

        monkeypatch.setattr(api_main, "_paper_note_identity_sets", _guarded_identity_sets)

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=0)

        assert [candidate["paper_id"] for candidate in page.selected_candidates] == [
            "zotero:realVisibleSlugIdentityNote2026"
        ]
    finally:
        api_main._paper_note_identity_sets = original_identity_helper
        db_utils.DB_PATH = original_db_path


def test_hidden_fixture_note_does_not_block_later_real_note_duplicate_in_mixed_window(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "mixed-window-real-db.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%mixed window real db pdf\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_real_window_anchor",
                "Real window anchor",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-17 13:00:00",
                "2026-04-17 13:00:00",
            ),
        )
        conn.commit()
        conn.close()

        shared_note_id = "shared-note-id-2026"
        vault_dir = tmp_path / "vault"

        fixture_note_path = vault_dir / "Inbox" / "PaperPipe" / "E2E Shared Fixture.md"
        _write(
            fixture_note_path,
            _note_content(
                note_id=shared_note_id,
                alias="E2E Shared Fixture",
                doi="10.1000/shared-note-fixture",
            ),
        )
        os.utime(fixture_note_path, (1_720_000_300, 1_720_000_300))

        real_note_path = vault_dir / "Inbox" / "PaperPipe" / "Shared Real Note.md"
        _write(
            real_note_path,
            _note_content(
                note_id=shared_note_id,
                alias="Shared Real Note",
                doi="10.1000/shared-note-real",
            ),
        )
        os.utime(real_note_path, (1_720_000_200, 1_720_000_200))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id=shared_note_id,
                    slug="e2e-shared-fixture",
                    title="E2E Shared Fixture",
                    note_path="Inbox/PaperPipe/E2E Shared Fixture.md",
                    status="INDEXED",
                    updated_at="2026-07-03T09:25:00Z",
                ),
                PaperNoteIndexItem(
                    id=shared_note_id,
                    slug="shared-real-note",
                    title="Shared Real Note",
                    note_path="Inbox/PaperPipe/Shared Real Note.md",
                    status="INDEXED",
                    updated_at="2026-07-03T09:24:00Z",
                ),
            ],
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 2, "offset": 0})

        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == [
            shared_note_id,
            "paper_real_window_anchor",
        ]
        assert listing.json()[0]["title"] == "Shared Real Note"
    finally:
        db_utils.DB_PATH = original_db_path


def test_fixture_note_does_not_block_later_real_duplicate_note_without_db_anchor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    original_build_index = api_main.paper_notes._build_index
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", lambda **kwargs: [])
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main.paper_notes,
            "_build_index",
            lambda _: SimpleNamespace(
                items=[
                    PaperNoteIndexItem(
                        id="shared-note-only-duplicate-2026",
                        slug="e2e-note-only-fixture-duplicate",
                        title="E2E Note-only Fixture Duplicate",
                        note_path="Inbox/PaperPipe/E2E Note-only Fixture Duplicate.md",
                        updated_at="2026-07-06T09:25:00Z",
                    ),
                    PaperNoteIndexItem(
                        id="shared-note-only-duplicate-2026",
                        slug="note-only-real-duplicate",
                        title="Note-only Real Duplicate",
                        note_path="Inbox/PaperPipe/Note-only Real Duplicate.md",
                        updated_at="2026-07-06T09:24:00Z",
                    ),
                ]
            ),
        )

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=0, raw_limit=5000)

        assert len(page.selected_candidates) == 1
        assert page.selected_candidates[0]["kind"] == "note"
        assert page.selected_candidates[0]["paper_id"] == "shared-note-only-duplicate-2026"
        assert page.selected_candidates[0]["note_item"].slug == "note-only-real-duplicate"
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        api_main.paper_notes._build_index = original_build_index
        db_utils.DB_PATH = original_db_path


def test_hidden_fixture_note_slug_does_not_override_later_real_duplicate_for_db_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "db-note-slug-prefer-real.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%db note slug prefer real\n")
        paper_id = "paper_db_slug_anchor_2026"
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_id,
                "DB slug anchor paper",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-21 00:00:00",
                "2026-04-21 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id=paper_id,
                    slug="e2e-hidden-db-slug",
                    title="E2E Hidden DB Slug Fixture",
                    note_path="Inbox/PaperPipe/E2E Hidden DB Slug Fixture.md",
                    status="INDEXED",
                    updated_at="2026-07-03T09:25:00Z",
                ),
                PaperNoteIndexItem(
                    id=paper_id,
                    slug="real-db-slug",
                    title="Real DB Slug Note",
                    note_path="Inbox/PaperPipe/Real DB Slug Note.md",
                    status="INDEXED",
                    updated_at="2026-07-03T09:24:00Z",
                ),
            ],
            raising=False,
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})
        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        assert listing.json()[0]["paper_id"] == paper_id
        assert listing.json()[0]["note_slug"] == "real-db-slug"

        assert rail_listing.status_code == 200
        assert rail_listing.json()[0]["paper_id"] == paper_id
        assert rail_listing.json()[0]["note_slug"] == "real-db-slug"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_note_slug_backfill_reuses_fixture_preview_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_fixture_checker = api_main.is_test_fixture_paper_record
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "db-note-slug-cache.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%db note slug cache\n")
        paper_id = "paper_db_slug_cache_anchor_2026"
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_id,
                "DB slug cache anchor paper",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-21 00:00:00",
                "2026-04-21 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id=paper_id,
                    slug="e2e-hidden-db-slug-cache",
                    title="E2E Hidden DB Slug Cache Fixture",
                    note_path="Inbox/PaperPipe/E2E Hidden DB Slug Cache Fixture.md",
                    status="INDEXED",
                    updated_at="2026-07-03T09:25:00Z",
                ),
                PaperNoteIndexItem(
                    id=paper_id,
                    slug="real-db-slug-cache",
                    title="Real DB Slug Cache Note",
                    note_path="Inbox/PaperPipe/Real DB Slug Cache Note.md",
                    status="INDEXED",
                    updated_at="2026-07-03T09:24:00Z",
                ),
            ],
            raising=False,
        )

        fixture_checker_calls = 0

        def _counted_fixture_checker(record):
            nonlocal fixture_checker_calls
            fixture_checker_calls += 1
            return original_fixture_checker(record)

        monkeypatch.setattr(api_main, "is_test_fixture_paper_record", _counted_fixture_checker)
        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        assert listing.json()[0]["paper_id"] == paper_id
        assert listing.json()[0]["note_slug"] == "real-db-slug-cache"
        assert fixture_checker_calls == 3
    finally:
        api_main.is_test_fixture_paper_record = original_fixture_checker
        db_utils.DB_PATH = original_db_path


def test_papers_note_only_iteration_stops_early_once_heap_is_filled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_identity_sets = api_main._paper_note_identity_sets
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_specs = [
            ("zotero:newestNoteOnly2026", "Newest Note Only", 1_720_000_002),
            ("zotero:olderNoteOnly2026A", "Older Note Only A", 1_720_000_001),
            ("zotero:olderNoteOnly2026B", "Older Note Only B", 1_720_000_000),
        ]
        for note_id, note_title, timestamp in note_specs:
            note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
            _write(
                note_path,
                _note_content(
                    note_id=note_id,
                    alias=note_title,
                    doi=f"10.1000/{note_id.split(':', 1)[1]}",
                ),
            )
            os.utime(note_path, (timestamp, timestamp))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _guarded_identity_sets(target):
            target_id = str(getattr(target, "id", "") or "")
            if target_id != "zotero:newestNoteOnly2026":
                raise AssertionError("older note identity sets should not be evaluated once note heap is filled")
            return original_identity_sets(target)

        monkeypatch.setattr(api_main, "_paper_note_identity_sets", _guarded_identity_sets)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == ["zotero:newestNoteOnly2026"]
    finally:
        api_main._paper_note_identity_sets = original_identity_sets
        db_utils.DB_PATH = original_db_path


def test_papers_fixture_only_iteration_stops_early_once_heap_is_filled_when_fixtures_are_included(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.setenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", "1")
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_identity_sets = api_main._paper_note_identity_sets
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_specs = [
            ("paper-e2e-fixture-newest", "E2E Fixture Newest", 1_720_000_102),
            ("paper-e2e-fixture-older-a", "E2E Fixture Older A", 1_720_000_101),
            ("paper-e2e-fixture-older-b", "E2E Fixture Older B", 1_720_000_100),
        ]
        for note_id, note_title, timestamp in note_specs:
            note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
            _write(
                note_path,
                _note_content(
                    note_id=note_id,
                    alias=note_title,
                    doi=f"10.1000/{note_id}",
                ),
            )
            os.utime(note_path, (timestamp, timestamp))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _guarded_identity_sets(target):
            target_id = str(getattr(target, "id", "") or "")
            if target_id != "paper-e2e-fixture-newest":
                raise AssertionError("older fixture note identity sets should not be evaluated once fixture heap is filled")
            return original_identity_sets(target)

        monkeypatch.setattr(api_main, "_paper_note_identity_sets", _guarded_identity_sets)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == ["paper-e2e-fixture-newest"]
    finally:
        api_main._paper_note_identity_sets = original_identity_sets
        db_utils.DB_PATH = original_db_path


def test_papers_note_sorting_is_reused_across_scan_expansions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    original_build_index = api_main.paper_notes._build_index
    original_sorter = api_main._note_items_sorted_for_listing
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        vault_dir = tmp_path / "vault"
        note_items = [
            PaperNoteIndexItem(
                slug="paper_real_001",
                id="paper_real_001",
                title="Duplicate of first real DB row",
                note_path="Inbox/PaperPipe/Duplicate of first real DB row.md",
                updated_at="2026-04-10T00:00:00Z",
            )
        ]

        def _fake_loader(*, raw_limit=5000, raw_offset=0, lightweight=False, table_columns=None):
            if raw_offset == 0:
                rows = [
                    {
                        "paper_id": "paper_real_001",
                        "title": "Real paper 001",
                        "updated_at": "2026-04-17T13:00:00Z",
                        "pdf_path": None,
                    },
                ]
                rows.extend(
                    {
                        "paper_id": f"paper-e2e-{idx:03d}",
                        "title": f"E2E Fixture {idx:03d}",
                        "updated_at": "2026-04-01T00:00:00Z",
                        "pdf_path": None,
                    }
                    for idx in range(200)
                )
                return rows
            if raw_offset == 201:
                rows = [
                    {
                        "paper_id": "paper_real_002",
                        "title": "Real paper 002",
                        "updated_at": "2026-04-16T13:00:00Z",
                        "pdf_path": None,
                    }
                ]
                return rows
            return []

        sort_call_count = 0

        def _counted_sorter(items):
            nonlocal sort_call_count
            sort_call_count += 1
            return original_sorter(items)

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", _fake_loader)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: vault_dir)
        monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda _: SimpleNamespace(items=note_items))
        monkeypatch.setattr(api_main, "_note_items_sorted_for_listing", _counted_sorter)

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=1, raw_limit=5000)

        assert page.selected_candidates[0]["kind"] == "db"
        assert page.selected_candidates[0]["row"]["paper_id"] == "paper_real_002"
        assert sort_call_count == 1
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        api_main.paper_notes._build_index = original_build_index
        api_main._note_items_sorted_for_listing = original_sorter
        db_utils.DB_PATH = original_db_path


def test_papers_db_identity_sets_are_reused_across_scan_expansions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_identity_sets = api_main._paper_id_identity_sets
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    original_build_index = api_main.paper_notes._build_index
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        def _fake_loader(*, raw_limit=5000, raw_offset=0, lightweight=False, table_columns=None):
            if raw_offset == 0:
                rows = [
                    {
                        "paper_id": "paper_real_001",
                        "title": "Real paper 001",
                        "updated_at": "2026-04-17T13:00:00Z",
                        "pdf_path": None,
                    },
                ]
                rows.extend(
                    {
                        "paper_id": f"paper-e2e-{idx:03d}",
                        "title": f"E2E Fixture {idx:03d}",
                        "updated_at": "2026-04-01T00:00:00Z",
                        "pdf_path": None,
                    }
                    for idx in range(200)
                )
                return rows
            if raw_offset == 201:
                rows = [
                    {
                        "paper_id": "paper_real_002",
                        "title": "Real paper 002",
                        "updated_at": "2026-04-16T13:00:00Z",
                        "pdf_path": None,
                    }
                ]
                return rows
            return []

        identity_call_count = 0

        def _counted_identity_sets(paper_id: str):
            nonlocal identity_call_count
            identity_call_count += 1
            return original_identity_sets(paper_id)

        note_items = [
            PaperNoteIndexItem(
                slug="paper_real_001",
                id="paper_real_001",
                title="Duplicate of first real DB row",
                note_path="Inbox/PaperPipe/Duplicate of first real DB row.md",
                updated_at="2026-04-10T00:00:00Z",
            )
        ]

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", _fake_loader)
        monkeypatch.setattr(api_main, "_paper_id_identity_sets", _counted_identity_sets)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda _: SimpleNamespace(items=note_items))

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=1, raw_limit=5000)

        assert page.selected_candidates[0]["kind"] == "db"
        assert page.selected_candidates[0]["row"]["paper_id"] == "paper_real_002"
        assert identity_call_count == 2
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main._paper_id_identity_sets = original_identity_sets
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        api_main.paper_notes._build_index = original_build_index
        db_utils.DB_PATH = original_db_path


def test_papers_hidden_fixture_db_row_does_not_block_later_real_duplicate_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    original_build_index = api_main.paper_notes._build_index
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        def _fake_loader(*, raw_limit=5000, raw_offset=0, lightweight=False, table_columns=None):
            if raw_offset == 0:
                return [
                    {
                        "paper_id": "paper-e2e-hidden-fixture-db-duplicate",
                        "title": "E2E Hidden Fixture DB Duplicate",
                        "updated_at": "2026-07-05T09:20:00Z",
                        "pdf_path": None,
                    }
                ]
            return []

        note_items = [
            PaperNoteIndexItem(
                id="workspace-real-duplicate-note-2026",
                slug="paper-e2e-hidden-fixture-db-duplicate",
                title="Workspace Real Duplicate Note",
                note_path="Inbox/PaperPipe/Workspace Real Duplicate Note.md",
                updated_at="2026-07-05T09:25:00Z",
            )
        ]

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", _fake_loader)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda _: SimpleNamespace(items=note_items))

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=0, raw_limit=5000)

        assert len(page.selected_candidates) == 1
        assert page.selected_candidates[0]["kind"] == "note"
        assert page.selected_candidates[0]["paper_id"] == "workspace-real-duplicate-note-2026"
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        api_main.paper_notes._build_index = original_build_index
        db_utils.DB_PATH = original_db_path


def test_papers_candidate_selection_uses_minimal_db_fixture_preview_record(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    original_fixture_checker = api_main.is_test_fixture_paper_record
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        def _fake_loader(*, raw_limit=5000, raw_offset=0, lightweight=False, table_columns=None):
            if raw_offset == 0:
                return [
                    {
                        "paper_id": "paper_real_fixture_preview_001",
                        "title": "Real fixture preview 001",
                        "updated_at": "2026-07-08T09:30:00Z",
                        "pdf_path": None,
                        "authors": "Real Author",
                        "doi": "10.1000/fixture-preview-real",
                    },
                    {
                        "paper_id": "paper-e2e-fixture-preview-002",
                        "title": "E2E Fixture Preview 002",
                        "updated_at": "2026-07-08T09:29:00Z",
                        "pdf_path": "/tmp/tests/fixture-preview.pdf",
                        "authors": "Fixture Author",
                        "doi": "10.1000/fixture-preview-fixture",
                    },
                ]
            return []

        def _raise_missing_vault():
            raise RuntimeError("missing vault")

        seen_key_sets: list[tuple[str, ...]] = []

        def _counted_fixture_checker(record):
            seen_key_sets.append(tuple(sorted(record.keys())))
            return original_fixture_checker(record)

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", _fake_loader)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", _raise_missing_vault)
        monkeypatch.setattr(api_main, "is_test_fixture_paper_record", _counted_fixture_checker)

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=0, raw_limit=5000)

        assert len(page.selected_candidates) == 1
        assert page.selected_candidates[0]["kind"] == "db"
        assert page.selected_candidates[0]["row"]["paper_id"] == "paper_real_fixture_preview_001"
        assert seen_key_sets
        assert set(seen_key_sets) == {("paper_id", "pdf_path", "title")}
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        api_main.is_test_fixture_paper_record = original_fixture_checker
        db_utils.DB_PATH = original_db_path


def test_papers_candidate_selection_resolves_fixture_inclusion_once(monkeypatch):
    fixture_flag_calls = 0

    def _fixture_flag():
        nonlocal fixture_flag_calls
        fixture_flag_calls += 1
        return False

    monkeypatch.setattr(api_main, "include_test_fixtures_enabled", _fixture_flag)
    monkeypatch.setattr(api_main, "_load_papers_table_columns", lambda: {"paper_id", "title", "pdf_path", "updated_at"})
    monkeypatch.setattr(
        api_main,
        "_load_paper_rows_for_listing",
        lambda *, raw_limit, raw_offset, lightweight, table_columns: [
            {
                "paper_id": "paper_selection_visibility_flag",
                "title": "Selection Visibility Flag",
                "updated_at": "2026-04-22T00:00:00Z",
                "pdf_path": None,
            }
        ],
    )
    monkeypatch.setattr(
        api_main.paper_notes,
        "_resolve_vault_path",
        lambda: (_ for _ in ()).throw(FileNotFoundError("no note context")),
    )

    page = api_main._select_visible_paper_candidates_page(limit=1, offset=0, raw_limit=5000)

    assert page.selected_candidates[0]["kind"] == "db"
    assert page.selected_candidates[0]["row"]["paper_id"] == "paper_selection_visibility_flag"
    assert fixture_flag_calls == 1


def test_papers_skip_db_identity_sets_when_note_context_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_identity_sets = api_main._paper_id_identity_sets
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        def _fake_loader(*, raw_limit=5000, raw_offset=0, lightweight=False, table_columns=None):
            if raw_offset == 0:
                return [
                    {
                        "paper_id": "paper_real_001",
                        "title": "Real paper 001",
                        "updated_at": "2026-04-17T13:00:00Z",
                        "pdf_path": None,
                    },
                    {
                        "paper_id": "paper_real_002",
                        "title": "Real paper 002",
                        "updated_at": "2026-04-16T13:00:00Z",
                        "pdf_path": None,
                    },
                ]
            return []

        def _unexpected_identity_sets(paper_id: str):
            raise AssertionError(f"db identity sets should not be computed without note context: {paper_id}")

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", _fake_loader)
        monkeypatch.setattr(api_main, "_paper_id_identity_sets", _unexpected_identity_sets)
        def _missing_vault():
            raise FileNotFoundError()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", _missing_vault)

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=0, raw_limit=5000)

        assert page.selected_candidates[0]["kind"] == "db"
        assert page.selected_candidates[0]["row"]["paper_id"] == "paper_real_001"
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main._paper_id_identity_sets = original_identity_sets
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        db_utils.DB_PATH = original_db_path


def test_papers_no_note_context_uses_requested_initial_scan_window(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        loader_calls: list[tuple[int, int, bool]] = []

        def _fake_loader(*, raw_limit=5000, raw_offset=0, lightweight=False, table_columns=None):
            loader_calls.append((raw_limit, raw_offset, lightweight))
            if raw_offset == 0:
                return [
                    {
                        "paper_id": "paper_real_small_window_001",
                        "title": "Real paper small window 001",
                        "updated_at": "2026-04-17T13:00:00Z",
                        "pdf_path": None,
                    }
                ]
            return []

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", _fake_loader)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=0, raw_limit=5000)

        assert loader_calls == [(1, 0, True)]
        assert [candidate["row"]["paper_id"] for candidate in page.selected_candidates] == [
            "paper_real_small_window_001"
        ]
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        db_utils.DB_PATH = original_db_path


def test_papers_no_note_context_stops_db_scan_after_first_real_row_fills_window(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        class _ExplodingRow:
            def __getitem__(self, key):
                raise AssertionError(f"older db rows should not be scanned once the real window is filled: {key}")

        def _fake_loader(*, raw_limit=5000, raw_offset=0, lightweight=False, table_columns=None):
            if raw_offset == 0:
                return [
                    {
                        "paper_id": "paper_real_early_break_001",
                        "title": "Real paper early break 001",
                        "updated_at": "2026-04-17T13:00:00Z",
                        "pdf_path": None,
                    },
                    _ExplodingRow(),
                ]
            return []

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", _fake_loader)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=0, raw_limit=5000)

        assert [candidate["row"]["paper_id"] for candidate in page.selected_candidates] == [
            "paper_real_early_break_001"
        ]
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        db_utils.DB_PATH = original_db_path


def test_papers_no_note_context_keeps_scanning_past_initial_fixture_until_real_row_appears(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        class _ExplodingRow:
            def __getitem__(self, key):
                raise AssertionError(
                    f"scan should stop right after the first visible real row fills the window, not later: {key}"
                )

        def _fake_loader(*, raw_limit=5000, raw_offset=0, lightweight=False, table_columns=None):
            if raw_offset == 0:
                return [
                    {
                        "paper_id": "paper-e2e-initial-fixture-row",
                        "title": "E2E Initial Fixture Row",
                        "updated_at": "2026-04-17T13:00:00Z",
                        "pdf_path": None,
                    },
                    {
                        "paper_id": "paper_real_after_hidden_001",
                        "title": "Real paper after hidden row 001",
                        "updated_at": "2026-04-17T12:00:00Z",
                        "pdf_path": None,
                    },
                    _ExplodingRow(),
                ]
            return []

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", _fake_loader)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: (_ for _ in ()).throw(FileNotFoundError()))

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=0, raw_limit=5000)

        assert [candidate["row"]["paper_id"] for candidate in page.selected_candidates] == [
            "paper_real_after_hidden_001"
        ]
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        db_utils.DB_PATH = original_db_path


def test_papers_skip_db_identity_sets_when_note_index_is_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_identity_sets = api_main._paper_id_identity_sets
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    original_build_index = api_main.paper_notes._build_index
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        def _fake_loader(*, raw_limit=5000, raw_offset=0, lightweight=False, table_columns=None):
            if raw_offset == 0:
                return [
                    {
                        "paper_id": "paper_real_empty_note_index_001",
                        "title": "Real paper empty note index 001",
                        "updated_at": "2026-04-17T13:00:00Z",
                        "pdf_path": None,
                    }
                ]
            return []

        def _unexpected_identity_sets(paper_id: str):
            raise AssertionError(f"db identity sets should not be computed with an empty note index: {paper_id}")

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", _fake_loader)
        monkeypatch.setattr(api_main, "_paper_id_identity_sets", _unexpected_identity_sets)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda _: SimpleNamespace(items=[]))

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=0, raw_limit=5000)

        assert page.selected_candidates[0]["kind"] == "db"
        assert page.selected_candidates[0]["row"]["paper_id"] == "paper_real_empty_note_index_001"
        assert page.note_items is None
        assert page.vault_path is None
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main._paper_id_identity_sets = original_identity_sets
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        api_main.paper_notes._build_index = original_build_index
        db_utils.DB_PATH = original_db_path


def test_papers_listing_uses_created_at_alias_when_updated_at_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_created_at_older",
                "Paper Created At Older",
                "INDEXED",
                None,
                "summary",
                "2026-04-01 00:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_created_at_newer",
                "Paper Created At Newer",
                "INDEXED",
                None,
                "summary",
                "2026-04-02 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(
            api_main.paper_notes,
            "_resolve_vault_path",
            lambda: (_ for _ in ()).throw(FileNotFoundError("no note context")),
        )

        client = TestClient(api_main.app)
        response = client.get("/papers", params={"limit": 1})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["paper_id"] == "paper_created_at_newer"
        assert payload[0]["updated_at"] == "2026-04-02 00:00:00"
    finally:
        db_utils.DB_PATH = original_db_path


def test_db_row_may_need_note_backed_pdf_lookup_uses_preview_access_only():
    class _PreviewOnlyRow:
        def __init__(self):
            self._payload = {
                "pdf_path": "/tmp/paperpipe-preview-only-missing.pdf",
            }

        def __getitem__(self, key):
            return self._payload[key]

        def get(self, key, default=None):
            return self._payload.get(key, default)

        def __iter__(self):
            raise AssertionError("db note-backed pdf gate should not materialize dict(row)")

    assert api_main._db_row_may_need_note_backed_pdf_lookup(_PreviewOnlyRow()) is True


def test_papers_db_fixture_checks_are_reused_across_scan_expansions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_loader = api_main._load_paper_rows_for_listing
    original_fixture_checker = api_main.is_test_fixture_paper_record
    original_resolve_vault_path = api_main.paper_notes._resolve_vault_path
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        def _fake_loader(*, raw_limit=5000, raw_offset=0, lightweight=False, table_columns=None):
            if raw_offset == 0:
                return [
                    {
                        "paper_id": "paper_real_001",
                        "title": "Real paper 001",
                        "updated_at": "2026-04-17T13:00:00Z",
                        "pdf_path": None,
                    },
                    {
                        "paper_id": "paper-e2e-000",
                        "title": "E2E Fixture 000",
                        "updated_at": "2026-04-01T00:00:00Z",
                        "pdf_path": None,
                    },
                ]
            if raw_offset == 2:
                rows = [
                    *(
                        {
                            "paper_id": f"paper-e2e-{idx:03d}",
                            "title": f"E2E Fixture {idx:03d}",
                            "updated_at": "2026-04-01T00:00:00Z",
                            "pdf_path": None,
                        }
                        for idx in range(1, 200)
                    ),
                    {
                        "paper_id": "paper_real_002",
                        "title": "Real paper 002",
                        "updated_at": "2026-04-16T13:00:00Z",
                        "pdf_path": None,
                    }
                ]
                return rows
            return []

        fixture_call_count = 0

        def _counted_fixture_checker(record):
            nonlocal fixture_call_count
            fixture_call_count += 1
            return original_fixture_checker(record)

        monkeypatch.setattr(api_main, "_load_paper_rows_for_listing", _fake_loader)
        monkeypatch.setattr(api_main, "is_test_fixture_paper_record", _counted_fixture_checker)
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "missing-vault")

        page = api_main._select_visible_paper_candidates_page(limit=1, offset=1, raw_limit=5000)

        assert page.selected_candidates[0]["kind"] == "db"
        assert page.selected_candidates[0]["row"]["paper_id"] == "paper_real_002"
        assert fixture_call_count <= 210
    finally:
        api_main._load_paper_rows_for_listing = original_loader
        api_main.is_test_fixture_paper_record = original_fixture_checker
        api_main.paper_notes._resolve_vault_path = original_resolve_vault_path
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_include_derived_access_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                doi TEXT,
                link TEXT,
                pdf_link TEXT,
                pdf_path TEXT,
                pdf_status TEXT,
                feedback_json TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        local_pdf = tmp_path / "manual.pdf"
        local_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, link, pdf_link, pdf_path, pdf_status, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_open",
                "Open Access Paper",
                "INDEXED",
                "10.1000/open",
                "https://publisher.example/open",
                "https://oa.example/open.pdf",
                None,
                None,
                "{}",
                "summary",
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, link, pdf_link, pdf_path, pdf_status, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_institution",
                "Institution Paper",
                "INDEXED",
                "10.1000/inst",
                "https://publisher.example/inst",
                None,
                None,
                "manual_required",
                "{}",
                "summary",
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, link, pdf_link, pdf_path, pdf_status, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_local",
                "Local PDF Paper",
                "INDEXED",
                "10.1000/local",
                "https://publisher.example/local",
                None,
                str(local_pdf),
                "downloaded",
                "{}",
                "summary",
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, link, pdf_link, pdf_path, pdf_status, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_unavailable",
                "Unavailable Paper",
                "INDEXED",
                None,
                None,
                None,
                None,
                None,
                "{}",
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}

        assert by_id["paper_open"]["access_summary"] == {
            "status_label": "open",
            "open_access_url": "https://oa.example/open.pdf",
            "institution_access_url": "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/open",
            "local_pdf_url": None,
        }
        assert by_id["paper_institution"]["access_summary"] == {
            "status_label": "institution_required",
            "open_access_url": None,
            "institution_access_url": "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/inst",
            "local_pdf_url": None,
        }
        assert by_id["paper_local"]["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/local",
            "local_pdf_url": "/papers/paper_local/pdf",
        }
        assert by_id["paper_unavailable"]["access_summary"] == {
            "status_label": "unavailable",
            "open_access_url": None,
            "institution_access_url": None,
            "local_pdf_url": None,
        }

        detail = client.get("/papers/paper_institution")
        assert detail.status_code == 200
        assert detail.json()["access_summary"]["status_label"] == "institution_required"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_detail_includes_pdf_exists_and_missing_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "p_missing_pdf",
                "Missing PDF Paper",
                "INDEXED",
                str(tmp_path / "no_such_file.pdf"),
                "summary",
            ),
        )
        existing_pdf = tmp_path / "existing.pdf"
        existing_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "p_has_pdf",
                "Has PDF Paper",
                "INDEXED",
                str(existing_pdf),
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        detail_missing = client.get("/papers/p_missing_pdf")
        assert detail_missing.status_code == 200
        payload_missing = detail_missing.json()
        assert payload_missing["paper_id"] == "p_missing_pdf"
        assert payload_missing["pdf_exists"] is False
        assert payload_missing["pdf_status"] == "missing"

        detail_ok = client.get("/papers/p_has_pdf")
        assert detail_ok.status_code == 200
        payload_ok = detail_ok.json()
        assert payload_ok["paper_id"] == "p_has_pdf"
        assert payload_ok["pdf_exists"] is True
        assert payload_ok["ops_summary"] is None

        missing = client.get("/papers/nope")
        assert missing.status_code == 404

        listing = client.get("/papers")
        assert listing.status_code == 200
        rows = listing.json()
        by_id = {row["paper_id"]: row for row in rows}
        assert by_id["p_missing_pdf"]["pdf_exists"] is False
        assert by_id["p_missing_pdf"]["pdf_status"] == "missing"
        assert by_id["p_has_pdf"]["pdf_exists"] is True
        assert by_id["p_has_pdf"]["pdf_status"] is None
        assert by_id["p_has_pdf"]["ops_summary"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_detail_and_pdf_route_fall_back_to_note_backed_local_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        local_pdf = tmp_path / "library" / "dubois.pdf"
        local_pdf.parent.mkdir(parents=True, exist_ok=True)
        local_pdf.write_bytes(b"%PDF-1.4\n%note-backed fixture\n")

        note_id = "zotero:duboisAlzheimerDiseaseClinicalBiological2024"
        note_title = "Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1016/S1474-4422(24)00001-2",
                pdf_url=local_pdf.resolve().as_uri(),
            ),
        )
        _write_artifact_run(
            artifacts_dir / "duboisAlzheimerDiseaseClinicalBiological2024" / "run-001",
            claimset={"claims": [{"id": "claim-1", "text": "Example claim"}]},
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{note_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == note_id
        assert payload["title"] == note_title
        assert payload["pdf_exists"] is True
        assert payload["status"] == "completed"
        assert payload["issues_state"] == "clear"
        assert payload["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1016/S1474-4422(24)00001-2",
            "local_pdf_url": f"/papers/{quote(note_id, safe='')}/pdf",
        }
        assert payload["ops_summary"]["state"] == "action_needed"
        assert payload["ops_summary"]["latest_run_id"] == "run-001"

        pdf_response = client.get(f"/papers/{note_id}/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.headers["content-type"] == "application/pdf"
        assert pdf_response.content.startswith(b"%PDF-1.4")
    finally:
        db_utils.DB_PATH = original_db_path


def test_note_backed_paper_detail_surfaces_latest_run_id_without_ops_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_id = "zotero:noteOnlyRunFallback2026"
        note_title = "Note-only latest run fallback"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/note-run-fallback",
            ),
        )

        run_dir = artifacts_dir / "noteOnlyRunFallback2026" / "run-note-only"
        run_dir.mkdir(parents=True, exist_ok=True)

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("job-note-only", "run-note-only", "noteOnlyRunFallback2026", "completed", str(run_dir)),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(
            api_main,
            "_latest_run_id_for_candidate_ids",
            lambda candidate_ids: (_ for _ in ()).throw(
                AssertionError(f"unexpected note-backed latest_run_id fallback for {candidate_ids}")
            ),
        )

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{quote(note_id, safe='')}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == note_id
        assert payload["ops_summary"] is None
        assert payload["latest_run_id"] == "run-note-only"

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id[note_id]["ops_summary"] is None
        assert by_id[note_id]["latest_run_id"] == "run-note-only"
    finally:
        db_utils.DB_PATH = original_db_path


def test_note_backed_paper_detail_falls_back_to_artifact_dirs_when_jobs_table_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        vault_dir = tmp_path / "vault"
        note_id = "zotero:noteOnlyRunNoJobsTable2026"
        note_title = "Note-only latest run without jobs table"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/note-run-no-jobs",
            ),
        )

        run_dir = artifacts_dir / "noteOnlyRunNoJobsTable2026" / "run-note-only"
        run_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{quote(note_id, safe='')}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == note_id
        assert payload["latest_run_id"] == "run-note-only"
    finally:
        db_utils.DB_PATH = original_db_path


def test_note_backed_paper_detail_skips_latest_run_fallback_when_artifact_cache_already_proves_miss(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_id = "zotero:noteOnlyRunClearMiss2026"
        note_title = "Note-only latest run clear miss"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/note-run-clear-miss",
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(
            api_main,
            "_latest_run_id_for_candidate_ids",
            lambda candidate_ids: (_ for _ in ()).throw(
                AssertionError(f"unexpected note-backed latest_run_id fallback for clear miss {candidate_ids}")
            ),
        )

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{quote(note_id, safe='')}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == note_id
        assert payload["ops_summary"] is None
        assert payload["latest_run_id"] is None

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id[note_id]["ops_summary"] is None
        assert by_id[note_id]["latest_run_id"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_note_backed_paper_detail_and_pdf_accept_stripped_id_for_prefixed_note(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        local_pdf = tmp_path / "library" / "stripped-note.pdf"
        local_pdf.parent.mkdir(parents=True, exist_ok=True)
        local_pdf.write_bytes(b"%PDF-1.4\n%stripped note-backed fixture\n")

        note_id = "zotero:strippedNoteBacked2026"
        note_title = "Stripped Note-backed Detail"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/stripped-note-backed",
                pdf_url=local_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("note-backed detail/pdf should use the without-ops note loader")
            ),
            raising=False,
        )

        client = TestClient(api_main.app)

        detail = client.get("/papers/strippedNoteBacked2026")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == note_id
        assert payload["title"] == note_title
        assert payload["pdf_exists"] is True
        assert payload["access_summary"]["local_pdf_url"] == f"/papers/{quote(note_id, safe='')}/pdf"

        pdf_response = client.get("/papers/strippedNoteBacked2026/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.content.startswith(b"%PDF-1.4")
    finally:
        db_utils.DB_PATH = original_db_path


def test_note_backed_paper_detail_exposes_note_slug_when_slug_route_resolves_canonical_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_id = "paper-e2e-note-backed-bbox-001"
        note_slug = "zoteroe2eNoteBackedBBox2026"
        note_title = "E2E Note-backed BBox Fixture"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_slug}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/e2e-note-bbox",
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{quote(note_slug, safe='')}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == note_id
        assert payload["note_slug"] == note_slug
        assert payload["title"] == note_title
    finally:
        db_utils.DB_PATH = original_db_path


def test_db_backed_paper_detail_exposes_note_slug_with_targeted_note_lookup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "db-detail-note-slug.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%db detail note slug\n")
        paper_id = "paper-db-detail-note-slug-001"
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_id,
                "DB Detail Note Slug Fixture",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-17 12:00:00",
                "2026-04-17 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        note_slug = "dbDetailNoteSlugFixture2026"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_slug}.md",
            _note_content(
                note_id=paper_id,
                alias="DB Detail Note Slug Fixture",
                doi="10.1000/db-detail-note-slug",
                pdf_url=live_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_full_lookup(*args, **kwargs):
            raise AssertionError("db-backed detail note_slug should use targeted note lookup, not full lookup")

        monkeypatch.setattr(api_main, "_build_note_item_lookup", _unexpected_full_lookup, raising=False)

        client = TestClient(api_main.app)
        detail = client.get(f"/papers/{quote(paper_id, safe='')}")

        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == paper_id
        assert payload["note_slug"] == note_slug
        assert payload["pdf_exists"] is True
    finally:
        db_utils.DB_PATH = original_db_path


def test_db_backed_paper_detail_skips_targeted_lookup_when_note_index_is_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "db-detail-empty-note-index.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%db detail empty note index\n")
        paper_id = "paper-db-detail-empty-note-index-001"
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_id,
                "DB Detail Empty Note Index Fixture",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-22 12:00:00",
                "2026-04-22 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda _: SimpleNamespace(items=[]))

        def _unexpected_targeted_lookup(*args, **kwargs):
            raise AssertionError("db-backed detail should not build targeted note lookup when the note index is empty")

        monkeypatch.setattr(api_main, "_build_note_item_lookup_for_paper_ids", _unexpected_targeted_lookup)

        client = TestClient(api_main.app)
        detail = client.get(f"/papers/{quote(paper_id, safe='')}")

        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == paper_id
        assert payload["note_slug"] is None
        assert payload["pdf_exists"] is True
    finally:
        db_utils.DB_PATH = original_db_path


def test_db_backed_paper_detail_and_pdf_accept_note_slug_route_without_note_backed_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "db-note-slug-route.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%db note slug route\n")
        paper_id = "paper-db-note-slug-route-001"
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_id,
                "DB Note Slug Route Fixture",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-20 12:00:00",
                "2026-04-20 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        note_slug = "dbNoteSlugRouteFixture2026"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_slug}.md",
            _note_content(
                note_id=paper_id,
                alias="DB Note Slug Route Fixture",
                doi="10.1000/db-note-slug-route",
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("db-backed slug route should resolve note identity without the full note-ops loader")
            ),
            raising=False,
        )

        def _unexpected_note_backed_item(*args, **kwargs):
            raise AssertionError("db-backed slug route should not fall back to full note-backed detail")

        def _unexpected_note_backed_pdf(*args, **kwargs):
            raise AssertionError("db-backed slug route should not fall back to note-backed pdf lookup")

        def _unexpected_targeted_lookup(*args, **kwargs):
            raise AssertionError("db-backed live-pdf slug route should not need targeted note lookup")

        monkeypatch.setattr(api_main, "_build_note_backed_paper_item", _unexpected_note_backed_item)
        monkeypatch.setattr(api_main, "_build_note_backed_pdf_path", _unexpected_note_backed_pdf)
        monkeypatch.setattr(api_main, "_build_note_item_lookup_for_paper_ids", _unexpected_targeted_lookup)

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{quote(note_slug, safe='')}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == paper_id
        assert payload["note_slug"] == note_slug
        assert payload["pdf_exists"] is True
        assert payload["access_summary"]["local_pdf_url"] == f"/papers/{quote(paper_id, safe='')}/pdf"

        pdf_response = client.get(f"/papers/{quote(note_slug, safe='')}/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.content.startswith(b"%PDF-1.4")
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_rail_note_backed_rows_expose_note_slug(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_id = "paper-e2e-note-backed-bbox-001"
        note_slug = "zoteroe2eNoteBackedBBox2026"
        note_title = "E2E Note-backed BBox Fixture"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_slug}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/e2e-note-bbox",
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        client = TestClient(api_main.app)
        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})

        assert rail_listing.status_code == 200
        rows = rail_listing.json()
        assert len(rows) == 1
        assert rows[0]["paper_id"] == note_id
        assert rows[0]["note_slug"] == note_slug
    finally:
        db_utils.DB_PATH = original_db_path


def test_db_backed_note_slug_route_with_missing_db_pdf_reuses_resolved_note_target(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "db-note-slug-route-recovered.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%db note slug route recovered\n")
        paper_id = "paper-db-note-slug-route-recovered-001"
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_id,
                "DB Note Slug Route Recovered Fixture",
                "INDEXED",
                "",
                "summary",
                "2026-04-21 12:00:00",
                "2026-04-21 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        note_slug = "dbNoteSlugRouteRecoveredFixture2026"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_slug}.md",
            _note_content(
                note_id=paper_id,
                alias="DB Note Slug Route Recovered Fixture",
                doi="10.1000/db-note-slug-route-recovered",
                pdf_url=live_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        lookup_item_slugs: list[list[str]] = []
        original_targeted_lookup = api_main._build_note_item_lookup_for_paper_ids

        def _counted_targeted_lookup(items, paper_ids):
            lookup_item_slugs.append([str(getattr(item, "slug", "") or "") for item in items])
            return original_targeted_lookup(items, paper_ids)

        def _unexpected_note_pdf_lookup(*args, **kwargs):
            raise AssertionError("db-backed missing-pdf slug route should reuse the resolved note target")

        monkeypatch.setattr(api_main, "_build_note_item_lookup_for_paper_ids", _counted_targeted_lookup)
        monkeypatch.setattr(api_main, "_resolve_note_backed_pdf_path_for_paper_id", _unexpected_note_pdf_lookup)

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{quote(note_slug, safe='')}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == paper_id
        assert payload["note_slug"] == note_slug
        assert payload["pdf_exists"] is True
        assert payload["access_summary"]["local_pdf_url"] == f"/papers/{quote(paper_id, safe='')}/pdf"
        assert lookup_item_slugs == [[note_slug]]

        pdf_response = client.get(f"/papers/{quote(note_slug, safe='')}/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.content.startswith(b"%PDF-1.4")
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_rail_db_backed_rows_expose_note_slug_without_targeted_lookup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "rail-note-slug-db.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%rail db row\n")
        note_id = "paper-e2e-note-backed-bbox-001"
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                "E2E Note-backed BBox Fixture",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-17 12:00:00",
                "2026-04-17 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        note_slug = "zoteroe2eNoteBackedBBox2026"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_slug}.md",
            _note_content(
                note_id=note_id,
                alias="E2E Note-backed BBox Fixture",
                doi="10.1000/e2e-note-bbox",
                pdf_url=live_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_targeted_lookup(*args, **kwargs):
            raise AssertionError("rail note_slug mapping should not require targeted note lookup")

        monkeypatch.setattr(api_main, "_build_note_item_lookup_for_paper_ids", _unexpected_targeted_lookup)

        client = TestClient(api_main.app)
        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})

        assert rail_listing.status_code == 200
        rows = rail_listing.json()
        assert len(rows) == 1
        assert rows[0]["paper_id"] == note_id
        assert rows[0]["note_slug"] == note_slug
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pages_skip_note_slug_backfill_when_page_selection_already_resolved_db_note_slug(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "selected-backfill-skip.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%selected backfill skip\n")
        note_id = "paper-e2e-note-backed-bbox-001"
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                "E2E Note-backed BBox Fixture",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-17 12:00:00",
                "2026-04-17 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        note_slug = "zoteroe2eNoteBackedBBox2026"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_slug}.md",
            _note_content(
                note_id=note_id,
                alias="E2E Note-backed BBox Fixture",
                doi="10.1000/e2e-note-bbox",
                pdf_url=live_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_backfill(*args, **kwargs):
            raise AssertionError("selected-window note_slug backfill should not run when page selection already resolved the slug")

        monkeypatch.setattr(api_main, "_backfill_note_slug_mapping_for_selected_db_paper_ids", _unexpected_backfill)

        client = TestClient(api_main.app)

        listing = client.get("/papers", params={"limit": 1, "offset": 0})
        assert listing.status_code == 200
        assert listing.json()[0]["note_slug"] == note_slug

        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})
        assert rail_listing.status_code == 200
        assert rail_listing.json()[0]["note_slug"] == note_slug
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_list_db_backed_rows_expose_note_slug_without_targeted_lookup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "list-note-slug-db.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%list db row\n")
        note_id = "paper-e2e-note-backed-bbox-001"
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                "E2E Note-backed BBox Fixture",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-17 12:00:00",
                "2026-04-17 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        note_slug = "zoteroe2eNoteBackedBBox2026"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_slug}.md",
            _note_content(
                note_id=note_id,
                alias="E2E Note-backed BBox Fixture",
                doi="10.1000/e2e-note-bbox",
                pdf_url=live_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_targeted_lookup(*args, **kwargs):
            raise AssertionError("list note_slug mapping should not require targeted note lookup")

        monkeypatch.setattr(api_main, "_build_note_item_lookup_for_paper_ids", _unexpected_targeted_lookup)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        rows = listing.json()
        assert len(rows) == 1
        assert rows[0]["paper_id"] == note_id
        assert rows[0]["note_slug"] == note_slug
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pages_backfill_note_slug_for_selected_db_rows_when_note_iteration_stops_early(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "backfill-note-slug-db.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%backfill db row\n")
        note_id = "paper_selected_db_backfill_note_slug"
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                "Selected DB row with older linked note",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-20 12:00:00",
                "2026-04-20 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        note_slug = "olderLinkedNoteSlug2026"
        note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_slug}.md"
        _write(
            note_path,
            _note_content(
                note_id=note_id,
                alias="Selected DB row with older linked note",
                doi="10.1000/backfill-note-slug",
                pdf_url=live_pdf.resolve().as_uri(),
            ),
        )
        os.utime(note_path, (1_700_000_000, 1_700_000_000))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_targeted_lookup(*args, **kwargs):
            raise AssertionError("old-note note_slug backfill should not require the broader targeted lookup helper")

        monkeypatch.setattr(api_main, "_build_note_item_lookup_for_paper_ids", _unexpected_targeted_lookup)

        client = TestClient(api_main.app)

        listing = client.get("/papers", params={"limit": 1, "offset": 0})
        assert listing.status_code == 200
        listing_rows = listing.json()
        assert len(listing_rows) == 1
        assert listing_rows[0]["paper_id"] == note_id
        assert listing_rows[0]["note_slug"] == note_slug

        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})
        assert rail_listing.status_code == 200
        rail_rows = rail_listing.json()
        assert len(rail_rows) == 1
        assert rail_rows[0]["paper_id"] == note_id
        assert rail_rows[0]["note_slug"] == note_slug
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_db_row_with_stale_pdf_path_falls_back_to_note_backed_local_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                doi TEXT,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        note_id = "zotero:stalePdfFallback2026"
        note_title = "Stale PDF fallback note"
        stale_pdf = tmp_path / "library" / "stale.pdf"
        recovered_pdf = tmp_path / "library" / "recovered.pdf"
        recovered_pdf.parent.mkdir(parents=True, exist_ok=True)
        recovered_pdf.write_bytes(b"%PDF-1.4\n%recovered note-backed pdf\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                note_id,
                note_title,
                "INDEXED",
                "10.1000/stale-fallback",
                str(stale_pdf),
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/stale-fallback",
                pdf_url=recovered_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(
            api_main,
            "_build_note_backed_paper_item",
            lambda paper_id: (_ for _ in ()).throw(
                AssertionError(f"unexpected full note-backed item build for db-backed pdf fallback: {paper_id}")
            ),
        )

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{note_id}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["pdf_exists"] is True
        assert payload["pdf_status"] is None
        assert payload["pdf_path"] == mask_local_path(str(recovered_pdf))

        assert payload["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/stale-fallback",
            "local_pdf_url": f"/papers/{quote(note_id, safe='')}/pdf",
        }

        pdf_response = client.get(f"/papers/{note_id}/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.content.startswith(b"%PDF-1.4")

        listing = client.get("/papers")
        assert listing.status_code == 200
        list_payload = {row["paper_id"]: row for row in listing.json()}[note_id]
        assert list_payload["pdf_exists"] is True
        assert list_payload["pdf_status"] is None
        assert list_payload["pdf_path"] == mask_local_path(str(recovered_pdf))
        assert list_payload["access_summary"] == payload["access_summary"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_includes_note_backed_items_and_sorts_by_note_updated_at(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_db_only",
                "DB Paper",
                "INDEXED",
                None,
                "summary",
                "2000-01-01 00:00:00",
                "2000-01-01 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        local_pdf = tmp_path / "library" / "note-only.pdf"
        local_pdf.parent.mkdir(parents=True, exist_ok=True)
        local_pdf.write_bytes(b"%PDF-1.4\n%note only\n")

        note_id = "zotero:noteOnlyPaper2026"
        note_title = "Note Only Paper"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/note-only",
                pdf_url=local_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows[:2]] == [note_id, "paper_db_only"]
        assert rows[0]["status"] == "completed"
        assert rows[0]["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/note-only",
            "local_pdf_url": f"/papers/{quote(note_id, safe='')}/pdf",
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pages_skip_note_lookup_build_for_note_only_windows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_id = "zotero:noteOnlyLookupSkip2026"
        note_title = "Note-only lookup skip"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/note-only-lookup-skip",
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_lookup_build(*args, **kwargs):
            raise AssertionError("note lookup should not be built for note-only windows")

        monkeypatch.setattr(api_main, "_build_note_item_lookup", _unexpected_lookup_build, raising=False)

        client = TestClient(api_main.app)

        listing = client.get("/papers", params={"limit": 1, "offset": 0})
        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == [note_id]

        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})
        assert rail_listing.status_code == 200
        assert [row["paper_id"] for row in rail_listing.json()] == [note_id]
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pages_skip_selected_db_row_fetch_and_artifact_preload_for_note_only_windows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_id = "zotero:noteOnlySelectedDbSkip2026"
        note_title = "Note-only selected-db skip"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/note-only-selected-db-skip",
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_row_fetch(*args, **kwargs):
            raise AssertionError("selected DB row fetch should not run for note-only windows")

        def _unexpected_artifact_preload(*args, **kwargs):
            raise AssertionError("artifact preload should not run for note-only windows")

        def _unexpected_latest_run_preload(*args, **kwargs):
            raise AssertionError("latest_run preload should not run for note-only windows")

        monkeypatch.setattr(api_main, "_fetch_listing_response_rows_by_ids", _unexpected_row_fetch)
        monkeypatch.setattr(api_main, "_fetch_listing_rail_rows_by_ids", _unexpected_row_fetch)
        monkeypatch.setattr(api_main, "_preload_artifact_snapshots_for_papers", _unexpected_artifact_preload)
        monkeypatch.setattr(api_main, "_preload_latest_run_ids_for_papers", _unexpected_latest_run_preload)

        client = TestClient(api_main.app)

        listing = client.get("/papers", params={"limit": 1, "offset": 0})
        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == [note_id]

        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})
        assert rail_listing.status_code == 200
        assert [row["paper_id"] for row in rail_listing.json()] == [note_id]
    finally:
        db_utils.DB_PATH = original_db_path


def test_note_only_paper_pages_reuse_shared_artifact_cache_within_request(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_specs = [
            ("zotero:noteOnlySharedCache2026A", "Note Only Shared Cache A", 1_720_100_001),
            ("zotero:noteOnlySharedCache2026B", "Note Only Shared Cache B", 1_720_100_000),
        ]
        for note_id, note_title, timestamp in note_specs:
            note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
            _write(
                note_path,
                _note_content(
                    note_id=note_id,
                    alias=note_title,
                    doi=f"10.1000/{note_id.split(':', 1)[1].lower()}",
                ),
            )
            os.utime(note_path, (timestamp, timestamp))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        monkeypatch.setattr(
            api_main,
            "build_ops_summary_for_candidate_ids",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("note-only multi-row pages should now reuse preloaded artifact cache before rebuilding ops summary")
            ),
        )

        client = TestClient(api_main.app)

        listing = client.get("/papers", params={"limit": 2, "offset": 0})
        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == [
            "zotero:noteOnlySharedCache2026A",
            "zotero:noteOnlySharedCache2026B",
        ]

        rail_listing = client.get("/papers/rail", params={"limit": 2, "offset": 0})
        assert rail_listing.status_code == 200
        assert [row["paper_id"] for row in rail_listing.json()] == [
            "zotero:noteOnlySharedCache2026A",
            "zotero:noteOnlySharedCache2026B",
        ]

    finally:
        db_utils.DB_PATH = original_db_path


def test_note_only_papers_listing_uses_shared_artifact_cache_without_latest_run_preload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_specs = [
            ("zotero:noteOnlyBatchRun2026A", "Note Only Batch Run A", "run-note-batch-a"),
            ("zotero:noteOnlyBatchRun2026B", "Note Only Batch Run B", "run-note-batch-b"),
        ]
        for idx, (note_id, note_title, run_id) in enumerate(note_specs):
            note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
            _write(
                note_path,
                _note_content(
                    note_id=note_id,
                    alias=note_title,
                    doi=f"10.1000/{note_id.split(':', 1)[1].lower()}",
                ),
            )
            os.utime(note_path, (1_720_200_000 + idx, 1_720_200_000 + idx))
            run_dir = artifacts_dir / note_id.split(":", 1)[1] / run_id
            run_dir.mkdir(parents=True, exist_ok=True)

        conn = db_utils.get_db_connection()
        conn.executemany(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                (
                    "job-note-batch-a",
                    "run-note-batch-a",
                    "noteOnlyBatchRun2026A",
                    "completed",
                    str(artifacts_dir / "noteOnlyBatchRun2026A" / "run-note-batch-a"),
                ),
                (
                    "job-note-batch-b",
                    "run-note-batch-b",
                    "noteOnlyBatchRun2026B",
                    "completed",
                    str(artifacts_dir / "noteOnlyBatchRun2026B" / "run-note-batch-b"),
                ),
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(
            api_main,
            "_preload_latest_run_ids_for_papers",
            lambda paper_ids: (_ for _ in ()).throw(
                AssertionError(f"unexpected note-only latest_run preload for {paper_ids}")
            ),
        )
        monkeypatch.setattr(
            api_main,
            "_latest_run_id_for_candidate_ids",
            lambda candidate_ids: (_ for _ in ()).throw(
                AssertionError(f"unexpected per-row note latest_run fallback for {candidate_ids}")
            ),
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 2, "offset": 0})

        assert listing.status_code == 200
        payload = listing.json()
        assert [row["paper_id"] for row in payload] == [
            "zotero:noteOnlyBatchRun2026B",
            "zotero:noteOnlyBatchRun2026A",
        ]
        by_id = {row["paper_id"]: row for row in payload}
        assert by_id["zotero:noteOnlyBatchRun2026A"]["latest_run_id"] == "run-note-batch-a"
        assert by_id["zotero:noteOnlyBatchRun2026B"]["latest_run_id"] == "run-note-batch-b"
    finally:
        db_utils.DB_PATH = original_db_path


def test_note_only_paper_pages_preload_artifact_snapshots_for_multi_note_windows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        note_specs = [
            ("zotero:noteOnlyPreloadOps2026A", "Note Only Preload Ops A", "run-note-preload-a"),
            ("zotero:noteOnlyPreloadOps2026B", "Note Only Preload Ops B", "run-note-preload-b"),
        ]
        for idx, (note_id, note_title, run_id) in enumerate(note_specs):
            note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
            _write(
                note_path,
                _note_content(
                    note_id=note_id,
                    alias=note_title,
                    doi=f"10.1000/{note_id.split(':', 1)[1].lower()}",
                ),
            )
            os.utime(note_path, (1_720_300_000 + idx, 1_720_300_000 + idx))
            _write_artifact_run(
                artifacts_dir / note_id.split(":", 1)[1] / run_id,
                claimset={"claims": [{"claim_id": f"claim-{idx}"}]},
                stats_report={"checks": [{"id": f"check-{idx}"}]},
            )

        conn = db_utils.get_db_connection()
        conn.executemany(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                (
                    "job-note-preload-a",
                    "run-note-preload-a",
                    "noteOnlyPreloadOps2026A",
                    "completed",
                    str(artifacts_dir / "noteOnlyPreloadOps2026A" / "run-note-preload-a"),
                ),
                (
                    "job-note-preload-b",
                    "run-note-preload-b",
                    "noteOnlyPreloadOps2026B",
                    "completed",
                    str(artifacts_dir / "noteOnlyPreloadOps2026B" / "run-note-preload-b"),
                ),
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(
            api_main,
            "build_ops_summary_for_candidate_ids",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("multi-note note-only pages should reuse preloaded artifact cache before rebuilding ops summary")
            ),
        )

        client = TestClient(api_main.app)

        listing = client.get("/papers", params={"limit": 2, "offset": 0})
        assert listing.status_code == 200
        listing_by_id = {row["paper_id"]: row for row in listing.json()}
        assert listing_by_id["zotero:noteOnlyPreloadOps2026A"]["ops_summary"]["state"] == "healthy"
        assert listing_by_id["zotero:noteOnlyPreloadOps2026B"]["ops_summary"]["state"] == "healthy"

        rail_listing = client.get("/papers/rail", params={"limit": 2, "offset": 0})
        assert rail_listing.status_code == 200
        rail_by_id = {row["paper_id"]: row for row in rail_listing.json()}
        assert rail_by_id["zotero:noteOnlyPreloadOps2026A"]["ops_summary"]["state"] == "healthy"
        assert rail_by_id["zotero:noteOnlyPreloadOps2026B"]["ops_summary"]["state"] == "healthy"
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pages_skip_note_lookup_build_for_db_windows_with_live_pdfs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        live_pdf = tmp_path / "library" / "live-db.pdf"
        live_pdf.parent.mkdir(parents=True, exist_ok=True)
        live_pdf.write_bytes(b"%PDF-1.4\n%live db pdf\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_live_pdf_only",
                "DB row with live PDF",
                "INDEXED",
                str(live_pdf),
                "summary",
                "2026-04-17 12:00:00",
                "2026-04-17 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / "Older note.md",
            _note_content(
                note_id="zotero:olderNoteOnly2026",
                alias="Older note only",
                doi="10.1000/older-note-only",
            ),
        )
        older_note_path = vault_dir / "Inbox" / "PaperPipe" / "Older note.md"
        os.utime(older_note_path, (1_710_000_000, 1_710_000_000))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_lookup_build(*args, **kwargs):
            raise AssertionError("note lookup should not be built for DB windows with live PDFs")

        monkeypatch.setattr(api_main, "_build_note_item_lookup", _unexpected_lookup_build, raising=False)

        client = TestClient(api_main.app)

        listing = client.get("/papers", params={"limit": 1, "offset": 0})
        assert listing.status_code == 200
        assert [row["paper_id"] for row in listing.json()] == ["paper_live_pdf_only"]

        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})
        assert rail_listing.status_code == 200
        assert [row["paper_id"] for row in rail_listing.json()] == ["paper_live_pdf_only"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pages_build_targeted_note_lookup_for_selected_db_pdf_fallbacks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                doi TEXT,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        stale_pdf = tmp_path / "library" / "missing-targeted.pdf"
        recovered_pdf = tmp_path / "library" / "targeted-recovered.pdf"
        recovered_pdf.parent.mkdir(parents=True, exist_ok=True)
        recovered_pdf.write_bytes(b"%PDF-1.4\n%targeted lookup recovered\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, doi, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_targeted_note_lookup",
                "Targeted note lookup",
                "INDEXED",
                "10.1000/targeted-note-lookup",
                str(stale_pdf),
                "summary",
                "2026-04-17 12:00:00",
                "2026-04-17 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        matching_note_path = vault_dir / "Inbox" / "PaperPipe" / "Targeted Note Lookup.md"
        _write(
            matching_note_path,
            _note_content(
                note_id="paper_targeted_note_lookup",
                alias="Targeted note lookup",
                doi="10.1000/targeted-note-lookup",
                pdf_url=recovered_pdf.resolve().as_uri(),
            ),
        )
        os.utime(matching_note_path, (1_710_000_100, 1_710_000_100))

        unrelated_note_path = vault_dir / "Inbox" / "PaperPipe" / "Unrelated Older Note.md"
        _write(
            unrelated_note_path,
            _note_content(
                note_id="zotero:unrelatedOlderNote2026",
                alias="Unrelated older note",
                doi="10.1000/unrelated-older-note",
            ),
        )
        os.utime(unrelated_note_path, (1_710_000_000, 1_710_000_000))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _unexpected_full_lookup(*args, **kwargs):
            raise AssertionError("page shapers should use targeted note lookup for selected DB fallback rows")

        monkeypatch.setattr(api_main, "_build_note_item_lookup", _unexpected_full_lookup, raising=False)
        original_targeted_lookup = api_main._build_note_item_lookup_for_paper_ids
        targeted_lookup_requests: list[list[str]] = []

        def _counted_targeted_lookup(items, paper_ids):
            targeted_lookup_requests.append(list(paper_ids))
            return original_targeted_lookup(items, paper_ids)

        monkeypatch.setattr(api_main, "_build_note_item_lookup_for_paper_ids", _counted_targeted_lookup)

        original_identity_sets = api_main._paper_note_identity_sets
        seen_note_ids: list[str] = []

        def _guarded_identity_sets(item):
            note_id = str(item.id or "").strip()
            seen_note_ids.append(note_id)
            if note_id == "zotero:unrelatedOlderNote2026":
                raise AssertionError("unrelated note should not be scanned once requested paper ids are resolved")
            return original_identity_sets(item)

        monkeypatch.setattr(api_main, "_paper_note_identity_sets", _guarded_identity_sets)

        client = TestClient(api_main.app)

        listing = client.get("/papers", params={"limit": 1, "offset": 0})
        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == ["paper_targeted_note_lookup"]
        assert rows[0]["pdf_exists"] is True
        assert rows[0]["note_slug"] == "Targeted Note Lookup"
        assert rows[0]["access_summary"]["local_pdf_url"] == "/papers/paper_targeted_note_lookup/pdf"

        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})
        assert rail_listing.status_code == 200
        rail_rows = rail_listing.json()
        assert [row["paper_id"] for row in rail_rows] == ["paper_targeted_note_lookup"]
        assert rail_rows[0]["note_slug"] == "Targeted Note Lookup"
        assert rail_rows[0]["access_summary"]["local_pdf_url"] == "/papers/paper_targeted_note_lookup/pdf"

        assert set(seen_note_ids) == {"paper_targeted_note_lookup"}
        assert targeted_lookup_requests == [["paper_targeted_note_lookup"], ["paper_targeted_note_lookup"]]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_reuses_cached_note_runtime_metadata_without_rereading_markdown(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        local_pdf = tmp_path / "library" / "cached-note.pdf"
        local_pdf.parent.mkdir(parents=True, exist_ok=True)
        local_pdf.write_bytes(b"%PDF-1.4\n%cached note\n")

        note_id = "zotero:cachedNotePaper2026"
        note_title = "Cached Note Paper"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/cached-note",
                pdf_url=local_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        cached_index = paper_notes_router._build_index(vault_dir)
        assert cached_index.items[0].has_runtime_source_metadata() is True

        def _unexpected_safe_read_text(path):
            raise AssertionError(f"unexpected markdown reread for cached note item: {path}")

        monkeypatch.setattr(api_main.paper_notes, "_safe_read_text", _unexpected_safe_read_text)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1})

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == [note_id]
        assert rows[0]["pdf_exists"] is True
        assert rows[0]["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/cached-note",
            "local_pdf_url": f"/papers/{quote(note_id, safe='')}/pdf",
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_note_backed_paper_detail_and_pdf_reuse_cached_runtime_metadata_without_rereading_markdown(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        local_pdf = tmp_path / "library" / "cached-detail-note.pdf"
        local_pdf.parent.mkdir(parents=True, exist_ok=True)
        local_pdf.write_bytes(b"%PDF-1.4\n%cached detail note\n")

        note_id = "zotero:cachedDetailNotePaper2026"
        note_title = "Cached Detail Note Paper"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/cached-detail-note",
                pdf_url=local_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        cached_index = paper_notes_router._build_index(vault_dir)
        assert cached_index.items[0].has_runtime_source_metadata() is True

        def _unexpected_safe_read_text(path):
            raise AssertionError(f"unexpected markdown reread for cached note detail: {path}")

        monkeypatch.setattr(api_main.paper_notes, "_safe_read_text", _unexpected_safe_read_text)

        client = TestClient(api_main.app)

        detail = client.get(f"/papers/{quote(note_id, safe='')}")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["paper_id"] == note_id
        assert payload["pdf_exists"] is True
        assert payload["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/cached-detail-note",
            "local_pdf_url": f"/papers/{quote(note_id, safe='')}/pdf",
        }

        pdf_response = client.get(f"/papers/{quote(note_id, safe='')}/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.content.startswith(b"%PDF-1.4")
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_list_builds_only_requested_note_window(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_builder = api_main._build_note_backed_paper_item_from_index_item
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()

        vault_dir = tmp_path / "vault"
        built_paper_ids: list[str] = []

        for idx in range(12):
            note_id = f"zotero:noteWindow{idx:02d}"
            note_title = f"Note Window {idx:02d}"
            note_path = vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md"
            _write(
                note_path,
                _note_content(
                    note_id=note_id,
                    alias=note_title,
                    doi=f"10.1000/note-window-{idx:02d}",
                ),
            )
            timestamp = 1_700_000_000 + idx
            os.utime(note_path, (timestamp, timestamp))

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        def _counted_builder(
            vault_path,
            target,
            *,
            paper_id,
            artifact_cache=None,
            artifacts_path=None,
        ):
            built_paper_ids.append(str(paper_id))
            return original_builder(
                vault_path,
                target,
                paper_id=paper_id,
                artifact_cache=artifact_cache,
                artifacts_path=artifacts_path,
            )

        monkeypatch.setattr(api_main, "_build_note_backed_paper_item_from_index_item", _counted_builder)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 5, "offset": 5})

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == [
            "zotero:noteWindow06",
            "zotero:noteWindow05",
            "zotero:noteWindow04",
            "zotero:noteWindow03",
            "zotero:noteWindow02",
        ]
        assert built_paper_ids == [
            "zotero:noteWindow06",
            "zotero:noteWindow05",
            "zotero:noteWindow04",
            "zotero:noteWindow03",
            "zotero:noteWindow02",
        ]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_prefers_existing_db_rows_over_note_id_variants(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "zotero:sharedPaper2026",
                "DB-authoritative Paper",
                "INDEXED",
                None,
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / "Shared Paper.md",
            _note_content(
                note_id="sharedPaper2026",
                alias="Shared Paper",
                doi="10.1000/shared-paper",
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == ["zotero:sharedPaper2026"]
        assert rows[0]["title"] == "DB-authoritative Paper"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_detail_and_pdf_route_resolve_zotero_id_variants_from_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        prefixed_pdf = tmp_path / "prefixed.pdf"
        prefixed_pdf.write_bytes(b"%PDF-1.4\n%prefixed\n")
        stripped_pdf = tmp_path / "stripped.pdf"
        stripped_pdf.write_bytes(b"%PDF-1.4\n%stripped\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "zotero:prefixedVariant2026",
                "Prefixed Variant Paper",
                "INDEXED",
                str(prefixed_pdf),
                "summary",
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "strippedVariant2026",
                "Stripped Variant Paper",
                "INDEXED",
                str(stripped_pdf),
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        prefixed_detail = client.get("/papers/prefixedVariant2026")
        assert prefixed_detail.status_code == 200
        prefixed_payload = prefixed_detail.json()
        assert prefixed_payload["paper_id"] == "zotero:prefixedVariant2026"
        assert prefixed_payload["title"] == "Prefixed Variant Paper"
        assert prefixed_payload["pdf_exists"] is True
        assert prefixed_payload["access_summary"]["local_pdf_url"] == "/papers/zotero%3AprefixedVariant2026/pdf"

        prefixed_pdf_response = client.get("/papers/prefixedVariant2026/pdf")
        assert prefixed_pdf_response.status_code == 200
        assert prefixed_pdf_response.content.startswith(b"%PDF-1.4")

        stripped_detail = client.get("/papers/zotero%3AstrippedVariant2026")
        assert stripped_detail.status_code == 200
        stripped_payload = stripped_detail.json()
        assert stripped_payload["paper_id"] == "strippedVariant2026"
        assert stripped_payload["title"] == "Stripped Variant Paper"
        assert stripped_payload["pdf_exists"] is True
        assert stripped_payload["access_summary"]["local_pdf_url"] == "/papers/strippedVariant2026/pdf"

        stripped_pdf_response = client.get("/papers/zotero%3AstrippedVariant2026/pdf")
        assert stripped_pdf_response.status_code == 200
        assert stripped_pdf_response.content.startswith(b"%PDF-1.4")
    finally:
        db_utils.DB_PATH = original_db_path


def test_artifacts_routes_resolve_zotero_id_variants_from_jobs_and_run_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        run_dir = artifacts_dir / "zotero:artifactVariant2026" / "run-artifact-variant"
        _write_artifact_run(
            run_dir,
            claimset={"claims": [{"claim_id": "claim-1"}]},
        )

        conn = db_utils.get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                "job-artifact-variant",
                "run-artifact-variant",
                "zotero:artifactVariant2026",
                "completed",
                str(run_dir),
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        latest = client.get("/artifacts/artifactVariant2026/latest")
        assert latest.status_code == 200
        latest_payload = latest.json()
        assert latest_payload["paper_id"] == "zotero:artifactVariant2026"
        assert latest_payload["run_id"] == "run-artifact-variant"
        assert latest_payload["files"]["claimset_resolved"]["exists"] is True

        explicit = client.get("/artifacts/artifactVariant2026/run-artifact-variant")
        assert explicit.status_code == 200
        explicit_payload = explicit.json()
        assert explicit_payload["paper_id"] == "zotero:artifactVariant2026"
        assert explicit_payload["run_id"] == "run-artifact-variant"
        assert explicit_payload["files"]["claimset_resolved"]["exists"] is True
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_expose_escalation_metadata_from_feedback_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                gate_decision TEXT,
                gate_reason TEXT,
                feedback_json TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_escalated",
                "Escalated Guideline Paper",
                "APPROVED",
                "APPROVED",
                "CONFIDENCE_MID,FASTLANE_GUIDANCE",
                json.dumps(
                    {
                        "escalation": {
                            "approved": True,
                            "reason": "Authoritative biomedical guidance is explicit; safe to auto-approve.",
                            "final_route": "FAST_LANE_APPROVE",
                            "in_biomedical_scope": True,
                            "reason_codes": ["FASTLANE_GUIDANCE"],
                        }
                    }
                ),
                "summary",
            ),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, gate_decision, gate_reason, feedback_json, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_pending_escalation",
                "Pending Review Paper",
                "PENDING_REVIEW",
                "PENDING_REVIEW",
                "CONFIDENCE_MID,MODEL_REVIEW_REQUIRED",
                json.dumps(
                    {
                        "escalation": {
                            "approved": False,
                            "reason": "Interesting but uncertain from metadata alone.",
                            "final_route": "QUEUE_HUMAN_REVIEW",
                            "in_biomedical_scope": True,
                            "reason_codes": ["MODEL_REVIEW_REQUIRED"],
                        }
                    }
                ),
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}

        assert by_id["paper_escalated"]["is_escalated"] is True
        assert by_id["paper_escalated"]["escalation_final_route"] == "FAST_LANE_APPROVE"
        assert by_id["paper_escalated"]["escalation_in_biomedical_scope"] is True
        assert by_id["paper_escalated"]["escalation_reason_codes"] == ["FASTLANE_GUIDANCE"]

        assert by_id["paper_pending_escalation"]["is_escalated"] is False
        assert by_id["paper_pending_escalation"]["escalation_final_route"] == "QUEUE_HUMAN_REVIEW"
        assert by_id["paper_pending_escalation"]["escalation_in_biomedical_scope"] is True
        assert by_id["paper_pending_escalation"]["escalation_reason_codes"] == ["MODEL_REVIEW_REQUIRED"]

        detail = client.get("/papers/paper_escalated")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["is_escalated"] is True
        assert payload["escalation_reason"] == "Authoritative biomedical guidance is explicit; safe to auto-approve."
        assert payload["escalation_final_route"] == "FAST_LANE_APPROVE"
        assert payload["escalation_reason_codes"] == ["FASTLANE_GUIDANCE"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_list_is_limited_and_sorted_by_updated_at(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        for idx in range(60):
            conn.execute(
                """
                INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"p_{idx:02d}",
                    f"Paper {idx:02d}",
                    "INDEXED",
                    None,
                    "summary",
                    f"2026-02-01 00:{idx % 60:02d}:00",
                    f"2026-02-01 00:{idx % 60:02d}:00",
                ),
            )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert len(rows) == 50
        assert rows[0]["paper_id"] == "p_59"
        assert rows[-1]["paper_id"] == "p_10"
        assert rows[0]["pdf_exists"] is False
        assert rows[0]["pdf_status"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_list_builds_only_requested_db_window(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_builder = api_main._build_db_backed_paper_item_from_row
    original_get_db_connection = api_main.get_db_connection
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        for idx in range(12):
            conn.execute(
                """
                INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"p_window_{idx:02d}",
                    f"Window Paper {idx:02d}",
                    "INDEXED",
                    None,
                    "summary",
                    f"2026-02-01 00:{idx:02d}:00",
                    f"2026-02-01 00:{idx:02d}:00",
                ),
            )
        conn.commit()
        conn.close()

        built_paper_ids: list[str] = []
        executed_queries: list[tuple[str, tuple[object, ...]]] = []

        class _RecordingConnection:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, params=()):
                executed_queries.append((" ".join(str(sql).split()), tuple(params)))
                return self._inner.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        def _counted_builder(row, *args, **kwargs):
            built_paper_ids.append(str(row["paper_id"]))
            return original_builder(row, *args, **kwargs)

        def _recording_get_db_connection():
            return _RecordingConnection(original_get_db_connection())

        monkeypatch.setattr(api_main, "_build_db_backed_paper_item_from_row", _counted_builder)
        monkeypatch.setattr(api_main, "get_db_connection", _recording_get_db_connection)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 5, "offset": 5})

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == [
            "p_window_06",
            "p_window_05",
            "p_window_04",
            "p_window_03",
            "p_window_02",
        ]
        assert built_paper_ids == [
            "p_window_06",
            "p_window_05",
            "p_window_04",
            "p_window_03",
            "p_window_02",
        ]
        assert any(
            "SELECT paper_id, title, updated_at, pdf_path FROM papers ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            in query
            and params == (10, 0)
            for query, params in executed_queries
        )
        assert any(
            query.startswith("SELECT paper_id")
            and "FROM papers WHERE paper_id IN (" in query
            and "SELECT * FROM papers WHERE paper_id IN (" not in query
            for query, _ in executed_queries
        )
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_expands_lightweight_scan_when_initial_window_contains_only_fixtures(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_get_db_connection = api_main.get_db_connection
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        fixture_pdf = tmp_path / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
        fixture_pdf.parent.mkdir(parents=True, exist_ok=True)
        fixture_pdf.write_text("%PDF", encoding="utf-8")
        real_pdf = tmp_path / "library" / "real.pdf"
        real_pdf.parent.mkdir(parents=True, exist_ok=True)
        real_pdf.write_text("%PDF", encoding="utf-8")

        rows: list[tuple[str, str, str, str, str, str, str]] = []
        for idx in range(205):
            rows.append(
                (
                    f"paper-e2e-{idx:03d}",
                    f"E2E Fixture {idx:03d}",
                    "INDEXED",
                    str(fixture_pdf),
                    "fixture",
                    f"2026-03-28 00:{idx % 60:02d}:00",
                    f"2026-03-28 00:{idx % 60:02d}:00",
                )
            )
        rows.append(
            (
                "paper-real-001",
                "Real Paper Beyond Seed Window",
                "INDEXED",
                str(real_pdf),
                "real",
                "2026-03-27 00:00:00",
                "2026-03-27 00:00:00",
            )
        )
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        conn.close()

        executed_queries: list[tuple[str, tuple[object, ...]]] = []

        class _RecordingConnection:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, params=()):
                executed_queries.append((" ".join(str(sql).split()), tuple(params)))
                return self._inner.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        def _recording_get_db_connection():
            return _RecordingConnection(original_get_db_connection())

        monkeypatch.setattr(api_main, "get_db_connection", _recording_get_db_connection)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == ["paper-real-001"]
        lightweight_limits = [
            params
            for query, params in executed_queries
            if "SELECT paper_id, title, updated_at, pdf_path FROM papers ORDER BY updated_at DESC LIMIT ? OFFSET ?" in query
        ]
        assert lightweight_limits[:2] == [(1, 0), (200, 1)]
        assert sum(1 for query, _ in executed_queries if "PRAGMA table_info(papers)" in query) == 1
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_rail_endpoint_returns_subset_and_skips_top_level_latest_run_lookup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                authors TEXT,
                status TEXT NOT NULL,
                doi TEXT,
                link TEXT,
                pdf_link TEXT,
                pdf_path TEXT,
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, authors, status, doi, link, pdf_link, pdf_path, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper_rail_db",
                "Rail DB Paper",
                "Tester, Alice",
                "INDEXED",
                "10.1000/rail-db",
                "https://publisher.example/rail-db",
                None,
                None,
                2,
                "Needs review",
                "flagged",
                "summary",
                "2026-04-01 00:00:00",
                "2026-04-01 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        local_pdf = tmp_path / "library" / "rail-note.pdf"
        local_pdf.parent.mkdir(parents=True, exist_ok=True)
        local_pdf.write_bytes(b"%PDF-1.4\n%rail note\n")

        note_id = "zotero:paperRailNote2026"
        note_title = "Rail Note Paper"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(
                note_id=note_id,
                alias=note_title,
                doi="10.1000/rail-note",
                pdf_url=local_pdf.resolve().as_uri(),
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(
            api_main,
            "_latest_run_id_for_candidate_ids",
            lambda candidate_ids: (_ for _ in ()).throw(
                AssertionError(f"unexpected top-level latest run lookup for {candidate_ids}")
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/papers/rail", params={"limit": 2})

        assert response.status_code == 200
        rows = response.json()
        assert [row["paper_id"] for row in rows] == [note_id, "paper_rail_db"]
        assert rows[0]["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/rail-note",
            "local_pdf_url": f"/papers/{quote(note_id, safe='')}/pdf",
        }
        assert rows[0]["issues_state"] == "clear"
        assert rows[1]["authors"] == "Tester, Alice"
        assert rows[1]["issues"] == 2
        assert rows[1]["issues_state"] == "flagged"
        assert rows[1]["access_summary"] == {
            "status_label": "institution_required",
            "open_access_url": None,
            "institution_access_url": "https://proxy.example.ac.kr/_Lib_Proxy_Url/https://doi.org/10.1000/rail-db",
            "local_pdf_url": None,
        }
        for row in rows:
            assert "latest_run_id" not in row
            assert "latest_job_id" not in row
            assert "pdf_exists" not in row
            assert "pdf_path" not in row
            assert "year" not in row
    finally:
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_uses_lightweight_db_path_without_note_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        for idx in range(8):
            conn.execute(
                """
                INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"recent_{idx}",
                    f"Recent Paper {idx}",
                    "INDEXED",
                    None,
                    "summary",
                    f"2026-04-01 00:0{idx}:00",
                    f"2026-04-01 00:0{idx}:00",
                ),
            )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda vault_path: (_ for _ in ()).throw(AssertionError()))
        monkeypatch.setattr(
            api_main,
            "_paper_id_identity_sets",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("db-only recent path should not compute note-fallback identity sets")
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 3})

        assert response.status_code == 200
        payload = response.json()
        assert [row["paper_id"] for row in payload] == ["recent_7", "recent_6", "recent_5"]
        assert [row["title"] for row in payload] == ["Recent Paper 7", "Recent Paper 6", "Recent Paper 5"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_uses_preview_access_only_for_db_rows(monkeypatch):
    class PreviewOnlyRow:
        def __init__(self, values):
            self._values = values

        def __getitem__(self, key):
            return self._values[key]

        def __iter__(self):
            raise AssertionError("recent papers db path should not materialize dict(row)")

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class FakeConn:
        def __init__(self, rows):
            self._rows = rows

        def execute(self, query, params=()):
            if "PRAGMA table_info(papers)" in query:
                return FakeCursor(
                    [
                        (0, "paper_id"),
                        (1, "title"),
                        (2, "status"),
                        (3, "pdf_path"),
                        (4, "updated_at"),
                    ]
                )
            assert "ORDER BY updated_at DESC" in query
            assert params == (2, 0)
            return FakeCursor(self._rows)

        def close(self):
            return None

    rows = [
        PreviewOnlyRow(
            {
                "paper_id": "recent_preview_3",
                "title": "Recent Preview 3",
                "status": "INDEXED",
                "updated_at": "2026-04-03 00:00:00",
                "pdf_path": None,
            }
        ),
        PreviewOnlyRow(
            {
                "paper_id": "recent_preview_2",
                "title": "Recent Preview 2",
                "status": "INDEXED",
                "updated_at": "2026-04-02 00:00:00",
                "pdf_path": None,
            }
        ),
        PreviewOnlyRow(
            {
                "paper_id": "recent_preview_1",
                "title": "Recent Preview 1",
                "status": "INDEXED",
                "updated_at": "2026-04-01 00:00:00",
                "pdf_path": None,
            }
        ),
    ]

    monkeypatch.setattr(api_main, "get_db_connection", lambda: FakeConn(rows))
    monkeypatch.setattr(
        api_main.paper_notes,
        "_resolve_vault_path",
        lambda: (_ for _ in ()).throw(AssertionError("recent db-only path should not enter note fallback")),
    )

    payload = api_main._list_recent_db_paper_items(limit=2)

    assert [row["paper_id"] for row in payload] == ["recent_preview_3", "recent_preview_2"]
    assert [row["title"] for row in payload] == ["Recent Preview 3", "Recent Preview 2"]


def test_recent_papers_endpoint_expands_db_window_when_initial_chunk_contains_only_fixtures(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_get_db_connection = api_main.get_db_connection
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        fixture_pdf = tmp_path / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
        fixture_pdf.parent.mkdir(parents=True, exist_ok=True)
        fixture_pdf.write_text("%PDF", encoding="utf-8")
        real_pdf = tmp_path / "library" / "recent-real.pdf"
        real_pdf.parent.mkdir(parents=True, exist_ok=True)
        real_pdf.write_text("%PDF", encoding="utf-8")
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "paper-e2e-recent-fixture-001",
                    "E2E Recent Fixture 001",
                    "INDEXED",
                    str(fixture_pdf),
                    "fixture",
                    "2026-04-03 00:00:00",
                    "2026-04-03 00:00:00",
                ),
                (
                    "recent-real-after-fixture",
                    "Recent Real After Prefix",
                    "INDEXED",
                    str(real_pdf),
                    "real",
                    "2026-04-02 00:00:00",
                    "2026-04-02 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        executed_queries: list[tuple[str, tuple[object, ...]]] = []

        class _RecordingConnection:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, params=()):
                executed_queries.append((" ".join(str(sql).split()), tuple(params)))
                return self._inner.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        def _recording_get_db_connection():
            return _RecordingConnection(original_get_db_connection())

        monkeypatch.setattr(api_main, "get_db_connection", _recording_get_db_connection)
        monkeypatch.setattr(
            api_main.paper_notes,
            "_resolve_vault_path",
            lambda: (_ for _ in ()).throw(FileNotFoundError("no note context")),
        )

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 1})

        assert response.status_code == 200
        payload = response.json()
        assert [row["paper_id"] for row in payload] == ["recent-real-after-fixture"]
        recent_limits = [
            params
            for query, params in executed_queries
            if "FROM papers ORDER BY updated_at DESC LIMIT ? OFFSET ?" in query
        ]
        assert recent_limits[:2] == [(1, 0), (200, 1)]
        assert sum(1 for query, _ in executed_queries if "PRAGMA table_info(papers)" in query) == 1
    finally:
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_reuses_preview_fixture_classification_across_scan_expansion(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_fixture_checker = api_main.is_test_fixture_paper_record
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        fixture_pdf = tmp_path / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
        fixture_pdf.parent.mkdir(parents=True, exist_ok=True)
        fixture_pdf.write_text("%PDF", encoding="utf-8")
        real_pdf = tmp_path / "library" / "recent-real-preview-cache.pdf"
        real_pdf.parent.mkdir(parents=True, exist_ok=True)
        real_pdf.write_text("%PDF", encoding="utf-8")
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "paper-e2e-recent-preview-fixture-001",
                    "E2E Recent Preview Fixture 001",
                    "INDEXED",
                    str(fixture_pdf),
                    "fixture",
                    "2026-04-03 00:00:00",
                    "2026-04-03 00:00:00",
                ),
                (
                    "recent-real-preview-cache",
                    "Recent Real Preview Cache",
                    "INDEXED",
                    str(real_pdf),
                    "real",
                    "2026-04-02 00:00:00",
                    "2026-04-02 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        fixture_check_calls = 0

        def _counted_fixture_checker(record):
            nonlocal fixture_check_calls
            fixture_check_calls += 1
            return original_fixture_checker(record)

        monkeypatch.setattr(api_main, "is_test_fixture_paper_record", _counted_fixture_checker)
        monkeypatch.setattr(
            api_main.paper_notes,
            "_resolve_vault_path",
            lambda: (_ for _ in ()).throw(FileNotFoundError("no note context")),
        )

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 1})

        assert response.status_code == 200
        assert [row["paper_id"] for row in response.json()] == ["recent-real-preview-cache"]
        assert fixture_check_calls == 2
    finally:
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_expands_db_window_without_refiltering_accumulated_preview_rows(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        fixture_pdf = tmp_path / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
        fixture_pdf.parent.mkdir(parents=True, exist_ok=True)
        fixture_pdf.write_text("%PDF", encoding="utf-8")
        real_pdf = tmp_path / "library" / "recent-real-no-refilter.pdf"
        real_pdf.parent.mkdir(parents=True, exist_ok=True)
        real_pdf.write_text("%PDF", encoding="utf-8")
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "paper-e2e-recent-no-refilter-fixture-001",
                    "E2E Recent No Refilter Fixture 001",
                    "INDEXED",
                    str(fixture_pdf),
                    "fixture",
                    "2026-04-03 00:00:00",
                    "2026-04-03 00:00:00",
                ),
                (
                    "recent-real-no-refilter",
                    "Recent Real No Refilter",
                    "INDEXED",
                    str(real_pdf),
                    "real",
                    "2026-04-02 00:00:00",
                    "2026-04-02 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(
            api_main,
            "prefer_non_fixture_items",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("recent db scan should not refilter accumulated preview rows")
            ),
            raising=False,
        )
        monkeypatch.setattr(
            api_main.paper_notes,
            "_resolve_vault_path",
            lambda: (_ for _ in ()).throw(FileNotFoundError("no note context")),
        )

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 1})

        assert response.status_code == 200
        assert [row["paper_id"] for row in response.json()] == ["recent-real-no-refilter"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_skips_db_identity_sets_when_note_context_is_unavailable(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "recent_identity_skip",
                "Recent Identity Skip",
                "INDEXED",
                None,
                "summary",
                "2026-04-01 00:00:00",
                "2026-04-01 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(
            api_main.paper_notes,
            "_resolve_vault_path",
            lambda: (_ for _ in ()).throw(FileNotFoundError("no note context")),
        )
        monkeypatch.setattr(
            api_main,
            "_paper_id_identity_sets",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("recent db rows should not compute note identity sets when note context is unavailable")
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 3})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["paper_id"] == "recent_identity_skip"
        assert payload[0]["title"] == "Recent Identity Skip"
    finally:
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_skips_db_identity_sets_when_note_index_is_empty(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "recent_empty_note_index",
                "Recent Empty Note Index",
                "INDEXED",
                None,
                "summary",
                "2026-04-01 00:00:00",
                "2026-04-01 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(api_main.paper_notes, "_build_index", lambda _: SimpleNamespace(items=[]))
        monkeypatch.setattr(
            api_main,
            "_paper_id_identity_sets",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("recent db rows should not compute note identity sets when the note index is empty")
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 3})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["paper_id"] == "recent_empty_note_index"
        assert payload[0]["title"] == "Recent Empty Note Index"
    finally:
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_falls_back_to_note_only_items_when_db_rows_are_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main.paper_notes,
            "_build_index",
            lambda vault_path: SimpleNamespace(
                items=[
                    PaperNoteIndexItem(
                        id="note-only-paper",
                        slug="note-only",
                        title="Note Only Paper",
                        note_path="Inbox/PaperPipe/Note only.md",
                        status="INDEXED",
                        updated_at="2026-04-11T00:00:00Z",
                    )
                ]
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 3})

        assert response.status_code == 200
        assert response.json() == [
            {
                "paper_id": "note-only-paper",
                "note_slug": None,
                "title": "Note Only Paper",
                "authors": None,
                "year": None,
                "pdf_exists": False,
                "pdf_path": None,
                "pdf_status": None,
                "status": "INDEXED",
                "issues": None,
                "issues_label": None,
                "issues_state": None,
                "latest_job_id": None,
                "latest_run_id": None,
                "updated_at": "2026-04-11T00:00:00Z",
                "is_escalated": False,
                "escalation_reason": None,
                "escalation_final_route": None,
                "escalation_in_biomedical_scope": None,
                "escalation_reason_codes": [],
                "ops_summary": None,
                "access_summary": None,
            }
        ]
    finally:
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_uses_note_fallback_without_precomputing_note_ops(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("recent papers note fallback should not precompute note ops")
            ),
            raising=False,
        )
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="recent-note-only-paper",
                    slug="recent-note-only",
                    title="Recent Note Only Paper",
                    note_path="Inbox/PaperPipe/Recent note only.md",
                    status="INDEXED",
                    updated_at="2026-04-12T00:00:00Z",
                )
            ],
            raising=False,
        )

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 3})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["paper_id"] == "recent-note-only-paper"
        assert payload[0]["title"] == "Recent Note Only Paper"
        assert payload[0]["status"] == "INDEXED"
        assert payload[0]["updated_at"] == "2026-04-12T00:00:00Z"
        assert payload[0]["ops_summary"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_resolves_fixture_inclusion_once_for_note_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    fixture_flag_calls = 0

    def _fixture_flag():
        nonlocal fixture_flag_calls
        fixture_flag_calls += 1
        return False

    monkeypatch.setattr(api_main, "include_test_fixtures_enabled", _fixture_flag)
    monkeypatch.setattr(api_main, "_load_papers_table_columns", lambda: {"paper_id", "title", "status", "updated_at"})
    monkeypatch.setattr(
        api_main,
        "_load_recent_db_rows",
        lambda *, raw_limit, raw_offset, table_columns: [
            {
                "paper_id": "recent_visibility_flag_db",
                "title": "Recent Visibility Flag DB",
                "status": "INDEXED",
                "updated_at": "2026-04-22T00:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
    monkeypatch.setattr(
        api_main,
        "_load_deduped_note_items_without_ops",
        lambda vault_path: [
            PaperNoteIndexItem(
                id="recent-visibility-flag-note",
                slug="recent-visibility-flag-note",
                title="Recent Visibility Flag Note",
                note_path="Inbox/PaperPipe/Recent Visibility Flag Note.md",
                status="INDEXED",
                updated_at="2026-04-21T00:00:00Z",
            )
        ],
        raising=False,
    )

    payload = api_main._list_recent_db_paper_items(limit=3)

    assert [item["paper_id"] for item in payload] == [
        "recent_visibility_flag_db",
        "recent-visibility-flag-note",
    ]
    assert fixture_flag_calls == 1


def test_recent_papers_endpoint_skips_hidden_fixture_note_metadata_after_real_note_is_visible(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    original_db_path = db_utils.DB_PATH
    original_metadata_helper = api_main._paper_note_listing_candidate_metadata
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id="recent-real-visible-note",
                    slug="recent-real-visible-note",
                    title="Recent Real Visible Note",
                    note_path="Inbox/PaperPipe/Recent Real Visible Note.md",
                    status="INDEXED",
                    updated_at="2026-04-13T00:00:00Z",
                ),
                PaperNoteIndexItem(
                    id="paper-e2e-recent-hidden-fixture-note",
                    slug="recent-hidden-fixture-note",
                    title="E2E Recent Hidden Fixture Note",
                    note_path="Inbox/PaperPipe/E2E Recent Hidden Fixture Note.md",
                    status="INDEXED",
                    updated_at="2026-04-12T00:00:00Z",
                ),
            ],
            raising=False,
        )

        def _guarded_metadata(note_item):
            if str(getattr(note_item, "id", "") or "").strip() == "paper-e2e-recent-hidden-fixture-note":
                raise AssertionError(
                    "recent note fallback should not build listing metadata for hidden fixture notes after a real note is visible"
                )
            return original_metadata_helper(note_item)

        monkeypatch.setattr(api_main, "_paper_note_listing_candidate_metadata", _guarded_metadata)

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 3})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["paper_id"] == "recent-real-visible-note"
    finally:
        api_main._paper_note_listing_candidate_metadata = original_metadata_helper
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_dedupes_note_variant_of_existing_db_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "shared-recent-paper",
                "DB Recent Paper",
                "INDEXED",
                None,
                "summary",
                "2026-04-17 12:00:00",
                "2026-04-17 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main.paper_notes,
            "_build_index",
            lambda vault_path: SimpleNamespace(
                items=[
                    PaperNoteIndexItem(
                        id="zotero:sharedRecentPaper2026",
                        slug="shared-recent-paper",
                        title="Shared Recent Paper Note",
                        note_path="Inbox/PaperPipe/Shared recent paper.md",
                        status="INDEXED",
                        updated_at="2026-04-17T11:59:00Z",
                    ),
                    PaperNoteIndexItem(
                        id="note-only-recent-paper",
                        slug="note-only-recent-paper",
                        title="Note Only Recent Paper",
                        note_path="Inbox/PaperPipe/Note only recent paper.md",
                        status="INDEXED",
                        updated_at="2026-04-16T00:00:00Z",
                    ),
                ]
            ),
        )

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 3})

        assert response.status_code == 200
        assert [row["paper_id"] for row in response.json()] == [
            "shared-recent-paper",
            "note-only-recent-paper",
        ]
    finally:
        db_utils.DB_PATH = original_db_path


def test_recent_papers_endpoint_skips_metadata_for_duplicate_note_variant_of_existing_db_row(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    original_metadata_helper = api_main._paper_note_listing_candidate_metadata
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "shared-recent-paper",
                "DB Recent Paper",
                "INDEXED",
                None,
                "summary",
                "2026-04-17 12:00:00",
                "2026-04-17 12:00:00",
            ),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: tmp_path / "vault")
        monkeypatch.setattr(
            api_main.paper_notes,
            "_build_index",
            lambda vault_path: SimpleNamespace(
                items=[
                    PaperNoteIndexItem(
                        id="zotero:sharedRecentPaper2026",
                        slug="shared-recent-paper",
                        title="Shared Recent Paper Note",
                        note_path="Inbox/PaperPipe/Shared recent paper.md",
                        status="INDEXED",
                        updated_at="2026-04-17T11:59:00Z",
                    ),
                    PaperNoteIndexItem(
                        id="note-only-recent-paper",
                        slug="note-only-recent-paper",
                        title="Note Only Recent Paper",
                        note_path="Inbox/PaperPipe/Note only recent paper.md",
                        status="INDEXED",
                        updated_at="2026-04-16T00:00:00Z",
                    ),
                ]
            ),
        )

        def _guarded_metadata(note_item):
            if str(getattr(note_item, "id", "") or "").strip() == "zotero:sharedRecentPaper2026":
                raise AssertionError(
                    "recent duplicate note variants should be filtered by identity before building metadata"
                )
            return original_metadata_helper(note_item)

        monkeypatch.setattr(api_main, "_paper_note_listing_candidate_metadata", _guarded_metadata)

        client = TestClient(api_main.app)
        response = client.get("/papers/recent", params={"limit": 3})

        assert response.status_code == 200
        assert [row["paper_id"] for row in response.json()] == [
            "shared-recent-paper",
            "note-only-recent-paper",
        ]
    finally:
        api_main._paper_note_listing_candidate_metadata = original_metadata_helper
        db_utils.DB_PATH = original_db_path


def test_workspace_summary_dedupes_note_only_variants_and_uses_latest_ops_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        vault_dir = tmp_path / "vault"

        canonical = PaperNoteIndexItem(
            id="zotero:workspaceDupPaper2026",
            slug="canonical-workspace-note",
            title="Workspace Duplicate Paper",
            note_path="Inbox/PaperPipe/Canonical workspace note.md",
            structured_state_present=True,
            status="INDEXED",
            updated_at="2026-04-18T00:00:00Z",
            ops_summary=PaperNoteOpsSummary(
                state="healthy",
                label="Healthy",
                reason="Saved claims and note checks are available. 1 checks are ready.",
                recommended_action="none",
                latest_run_id="run_stale_001",
                has_claimset=True,
                has_stats_report=True,
                stats_check_count=1,
            ),
        )
        legacy = PaperNoteIndexItem(
            id="workspaceDupPaper2026",
            slug="legacy-workspace-note",
            title="Workspace Duplicate Paper",
            note_path="Inbox/PaperPipe/Legacy workspace note.md",
            status="INDEXED",
            updated_at="2026-04-19T00:00:00Z",
            ops_summary=PaperNoteOpsSummary(
                state="action_needed",
                label="Action needed",
                reason="Saved note checks are missing or empty.",
                recommended_action="repair_stats",
                latest_run_id="run_repair_001",
                has_claimset=True,
                has_stats_report=False,
                stats_check_count=0,
            ),
        )

        _write_artifact_run(
            artifacts_dir / "workspaceDupPaper2026" / "run_repair_001",
            claimset={"claims": [{"claim_id": "c1"}]},
        )
        _write_artifact_run(
            artifacts_dir / "zotero:workspaceDupPaper2026" / "run_healthy_001",
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": [{"id": "check-1"}, {"id": "check-2"}]},
        )

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: vault_dir)
        monkeypatch.setattr(
            api_main.paper_notes,
            "_build_index",
            lambda vault_path: SimpleNamespace(items=[legacy, canonical]),
        )

        client = TestClient(api_main.app)
        response = client.get("/workspace-summary")

        assert response.status_code == 200
        payload = response.json()
        assert payload["saved_notes"] == 1
        assert payload["structured_notes"] == 1
        assert payload["blocked"] == 0
        assert payload["needs_review"] == 0
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_dedupe_note_only_variants_and_prefer_canonical_latest_ops(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        vault_dir = tmp_path / "vault"

        canonical_id = "zotero:noteOnlyDupPaper2026"
        legacy_id = "noteOnlyDupPaper2026"
        canonical_slug = "canonical-note-only-dup"
        legacy_slug = "legacy-note-only-dup"

        _write(
            vault_dir / "Inbox" / "PaperPipe" / "Canonical note only dup.md",
            _note_content(note_id=canonical_id, alias="Canonical Note-only Duplicate"),
        )
        _write(
            vault_dir / "Inbox" / "PaperPipe" / "Legacy note only dup.md",
            _note_content(note_id=legacy_id, alias="Legacy Note-only Duplicate"),
        )

        canonical = PaperNoteIndexItem(
            id=canonical_id,
            slug=canonical_slug,
            title="Canonical Note-only Duplicate",
            note_path="Inbox/PaperPipe/Canonical note only dup.md",
            structured_state_present=True,
            status="INDEXED",
            updated_at="2026-04-18T00:00:00Z",
            ops_summary=PaperNoteOpsSummary(
                state="healthy",
                label="Healthy",
                reason="Saved claims and note checks are available. 1 checks are ready.",
                recommended_action="none",
                latest_run_id="run_stale_001",
                has_claimset=True,
                has_stats_report=True,
                stats_check_count=1,
            ),
        )
        legacy = PaperNoteIndexItem(
            id=legacy_id,
            slug=legacy_slug,
            title="Legacy Note-only Duplicate",
            note_path="Inbox/PaperPipe/Legacy note only dup.md",
            status="INDEXED",
            updated_at="2026-04-19T00:00:00Z",
            ops_summary=PaperNoteOpsSummary(
                state="action_needed",
                label="Action needed",
                reason="Saved note checks are missing or empty.",
                recommended_action="repair_stats",
                latest_run_id="run_repair_001",
                has_claimset=True,
                has_stats_report=False,
                stats_check_count=0,
            ),
        )

        _write_artifact_run(
            artifacts_dir / legacy_id / "run_repair_001",
            claimset={"claims": [{"claim_id": "c1"}]},
        )
        _write_artifact_run(
            artifacts_dir / canonical_id / "run_healthy_001",
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": [{"id": "check-1"}, {"id": "check-2"}]},
        )

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: vault_dir)
        monkeypatch.setattr(
            api_main.paper_notes,
            "_build_index",
            lambda vault_path: SimpleNamespace(items=[legacy, canonical]),
        )

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        payload = listing.json()
        assert len(payload) == 1
        assert payload[0]["paper_id"] == canonical_id
        assert payload[0]["note_slug"] == canonical_slug
        assert payload[0]["issues_state"] == "clear"
        assert payload[0]["ops_summary"]["state"] == "healthy"
        assert payload[0]["ops_summary"]["latest_run_id"] == "run_healthy_001"
        assert payload[0]["latest_run_id"] == "run_healthy_001"

        detail = client.get(f"/papers/{legacy_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["paper_id"] == canonical_id
        assert detail_payload["note_slug"] == canonical_slug
        assert detail_payload["issues_state"] == "clear"
        assert detail_payload["ops_summary"]["state"] == "healthy"
        assert detail_payload["ops_summary"]["latest_run_id"] == "run_healthy_001"
        assert detail_payload["latest_run_id"] == "run_healthy_001"
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pages_use_note_items_without_ops_and_recompute_selected_note_ops(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        vault_dir = tmp_path / "vault"
        note_id = "zotero:selectedNoteOps2026"
        note_slug = "selected-note-ops"
        note_title = "Selected Note Ops"
        _write(
            vault_dir / "Inbox" / "PaperPipe" / f"{note_title}.md",
            _note_content(note_id=note_id, alias=note_title, doi="10.1000/selected-note-ops"),
        )

        _write_artifact_run(
            artifacts_dir / note_id / "run-selected-note-healthy",
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": [{"id": "check-1"}]},
        )

        monkeypatch.setattr(api_main.paper_notes, "_resolve_vault_path", lambda: vault_dir)
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("paper page candidate selection should not precompute note ops")
            ),
            raising=False,
        )
        monkeypatch.setattr(
            api_main,
            "_load_deduped_note_items_without_ops",
            lambda vault_path: [
                PaperNoteIndexItem(
                    id=note_id,
                    slug=note_slug,
                    title=note_title,
                    note_path=f"Inbox/PaperPipe/{note_title}.md",
                    structured_state_present=True,
                    status="INDEXED",
                    updated_at="2026-04-18T00:00:00Z",
                    ops_summary=None,
                )
            ],
            raising=False,
        )

        client = TestClient(api_main.app)

        listing = client.get("/papers", params={"limit": 1, "offset": 0})
        assert listing.status_code == 200
        listing_payload = listing.json()
        assert len(listing_payload) == 1
        assert listing_payload[0]["paper_id"] == note_id
        assert listing_payload[0]["ops_summary"]["state"] == "healthy"
        assert listing_payload[0]["ops_summary"]["latest_run_id"] == "run-selected-note-healthy"
        assert listing_payload[0]["latest_run_id"] == "run-selected-note-healthy"

        rail_listing = client.get("/papers/rail", params={"limit": 1, "offset": 0})
        assert rail_listing.status_code == 200
        rail_payload = rail_listing.json()
        assert len(rail_payload) == 1
        assert rail_payload[0]["paper_id"] == note_id
        assert rail_payload[0]["ops_summary"]["state"] == "healthy"
        assert rail_payload[0]["ops_summary"]["latest_run_id"] == "run-selected-note-healthy"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_include_operational_summary_from_artifacts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_ops_healthy", "Healthy Paper", "INDEXED", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_ops_missing", "Missing Stats Paper", "INDEXED", "summary"),
        )
        conn.commit()
        conn.close()

        _write_artifact_run(
            artifacts_dir / "paper_ops_healthy" / "run-healthy",
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": [{"id": "check-1"}, {"id": "check-2"}]},
        )
        _write_artifact_run(
            artifacts_dir / "paper_ops_missing" / "run-missing",
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": []},
        )

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_ops_healthy"]["ops_summary"]["state"] == "healthy"
        assert by_id["paper_ops_healthy"]["ops_summary"]["stats_check_count"] == 2
        assert by_id["paper_ops_healthy"]["latest_run_id"] == "run-healthy"
        assert by_id["paper_ops_missing"]["ops_summary"]["state"] == "action_needed"
        assert by_id["paper_ops_missing"]["ops_summary"]["reason"] == "Saved note checks are missing or empty."
        assert by_id["paper_ops_missing"]["latest_run_id"] == "run-missing"

        detail = client.get("/papers/paper_ops_missing")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["ops_summary"]["recommended_action"] == "repair_stats"
        assert payload["ops_summary"]["latest_run_id"] == "run-missing"
        assert payload["latest_run_id"] == "run-missing"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_prefer_latest_ops_summary_across_equivalent_paper_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("zotero:wenzelShortchainFattyAcids2020", "Candidate-linked paper", "INDEXED", "summary"),
        )
        conn.commit()
        conn.close()

        stale_run = artifacts_dir / "zotero:wenzelShortchainFattyAcids2020" / "run-stale"
        _write_artifact_run(
            stale_run,
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": []},
        )

        fresh_run = artifacts_dir / "wenzelShortchainFattyAcids2020" / "run-fresh"
        _write_artifact_run(
            fresh_run,
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": [{"id": "check-1"}, {"id": "check-2"}]},
        )

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        payload = listing.json()[0]
        assert payload["paper_id"] == "zotero:wenzelShortchainFattyAcids2020"
        assert payload["ops_summary"]["state"] == "healthy"
        assert payload["ops_summary"]["stats_check_count"] == 2
        assert payload["latest_run_id"] == "run-fresh"

        detail = client.get("/papers/zotero:wenzelShortchainFattyAcids2020")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["ops_summary"]["state"] == "healthy"
        assert detail_payload["ops_summary"]["latest_run_id"] == "run-fresh"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_hides_fixture_rows_when_real_papers_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        fixture_pdf = tmp_path / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
        fixture_pdf.parent.mkdir(parents=True, exist_ok=True)
        fixture_pdf.write_text("%PDF", encoding="utf-8")
        real_pdf = tmp_path / "library" / "real.pdf"
        real_pdf.parent.mkdir(parents=True, exist_ok=True)
        real_pdf.write_text("%PDF", encoding="utf-8")
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "paper-e2e-001",
                    "E2E Seed Paper",
                    "INDEXED",
                    str(fixture_pdf),
                    "fixture",
                    "2026-03-28 00:00:00",
                    "2026-03-28 00:00:00",
                ),
                (
                    "paper-real-001",
                    "Real Paper",
                    "INDEXED",
                    str(real_pdf),
                    "real",
                    "2026-03-27 00:00:00",
                    "2026-03-27 00:00:00",
                ),
            ],
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == ["paper-real-001"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_keeps_fixture_rows_when_only_fixtures_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        fixture_pdf = tmp_path / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
        fixture_pdf.parent.mkdir(parents=True, exist_ok=True)
        fixture_pdf.write_text("%PDF", encoding="utf-8")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "paper-e2e-001",
                "E2E Seed Paper",
                "INDEXED",
                str(fixture_pdf),
                "fixture",
                "2026-03-28 00:00:00",
                "2026-03-28 00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == ["paper-e2e-001"]
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_surface_latest_run_id_from_jobs_when_ops_summary_is_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_job_only", "Job-backed Paper", "INDEXED", "summary"),
        )
        run_dir = artifacts_dir / "paper_job_only" / "run-job-only"
        run_dir.mkdir(parents=True, exist_ok=True)
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("job-001", "run-job-only", "paper_job_only", "completed", str(run_dir)),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_job_only"]["ops_summary"] is None
        assert by_id["paper_job_only"]["latest_run_id"] == "run-job-only"

        detail = client.get("/papers/paper_job_only")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["ops_summary"] is None
        assert payload["latest_run_id"] == "run-job-only"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_surface_latest_run_id_from_candidate_job_id_when_ops_summary_is_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("zotero:paper_job_variant", "Variant Job-backed Paper", "INDEXED", "summary"),
        )
        run_dir = artifacts_dir / "paper_job_variant" / "run-job-variant"
        run_dir.mkdir(parents=True, exist_ok=True)
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("job-variant", "run-job-variant", "paper_job_variant", "completed", str(run_dir)),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["zotero:paper_job_variant"]["ops_summary"] is None
        assert by_id["zotero:paper_job_variant"]["latest_run_id"] == "run-job-variant"

        detail = client.get("/papers/zotero%3Apaper_job_variant")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["ops_summary"] is None
        assert payload["latest_run_id"] == "run-job-variant"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_uses_artifact_snapshot_run_id_without_jobs_preload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_artifact_run_only", "Artifact-backed run Paper", "INDEXED", "summary"),
        )
        run_dir = artifacts_dir / "paper_artifact_run_only" / "run-artifact-only"
        run_dir.mkdir(parents=True, exist_ok=True)
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("job-artifact-only", "run-artifact-only", "paper_artifact_run_only", "completed", str(run_dir)),
        )
        conn.commit()
        conn.close()

        def _unexpected_preload(*args, **kwargs):
            raise AssertionError("latest_run preload should not run when artifact cache already has the run id")

        monkeypatch.setattr(api_main, "_preload_latest_run_ids_for_papers", _unexpected_preload)
        monkeypatch.setattr(
            api_main,
            "_latest_run_id_for_candidate_ids",
            lambda candidate_ids: (_ for _ in ()).throw(
                AssertionError(f"unexpected per-row latest_run_id fallback for {candidate_ids}")
            ),
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_artifact_run_only"]["ops_summary"] is None
        assert by_id["paper_artifact_run_only"]["latest_run_id"] == "run-artifact-only"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_preloads_latest_run_ids_without_per_row_lookup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            [
                ("paper_job_batch_1", "Batch Job Paper 1", "INDEXED", "summary"),
                ("paper_job_batch_2", "Batch Job Paper 2", "INDEXED", "summary"),
            ],
        )
        run_dir_one = artifacts_dir / "paper_job_batch_1" / "run-batch-1"
        run_dir_two = artifacts_dir / "paper_job_batch_2" / "run-batch-2"
        run_dir_one.mkdir(parents=True, exist_ok=True)
        run_dir_two.mkdir(parents=True, exist_ok=True)
        conn.executemany(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                ("job-batch-1", "run-batch-1", "paper_job_batch_1", "completed", str(run_dir_one)),
                ("job-batch-2", "run-batch-2", "paper_job_batch_2", "completed", str(run_dir_two)),
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(
            api_main,
            "_latest_run_id_for_paper",
            lambda paper_id: (_ for _ in ()).throw(AssertionError(f"unexpected per-row lookup for {paper_id}")),
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_job_batch_1"]["latest_run_id"] == "run-batch-1"
        assert by_id["paper_job_batch_2"]["latest_run_id"] == "run-batch-2"
        assert by_id["paper_job_batch_1"]["ops_summary"] is None
        assert by_id["paper_job_batch_2"]["ops_summary"] is None
    finally:
        db_utils.DB_PATH = original_db_path


def test_single_db_row_papers_listing_skips_selected_window_preloads_and_recovers_latest_run_lazily(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_single_selected_window", "Single selected window paper", "INDEXED", "summary"),
        )
        run_dir = artifacts_dir / "paper_single_selected_window" / "run-single-selected-window"
        run_dir.mkdir(parents=True, exist_ok=True)
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                "job-single-selected-window",
                "run-single-selected-window",
                "paper_single_selected_window",
                "completed",
                str(run_dir),
            ),
        )
        conn.commit()
        conn.close()

        def _unexpected_latest_run_preload(*args, **kwargs):
            raise AssertionError("latest_run preload should not run for a single selected DB row")

        monkeypatch.setattr(api_main, "_preload_latest_run_ids_for_papers", _unexpected_latest_run_preload)

        client = TestClient(api_main.app)
        listing = client.get("/papers", params={"limit": 1, "offset": 0})

        assert listing.status_code == 200
        rows = listing.json()
        assert [row["paper_id"] for row in rows] == ["paper_single_selected_window"]
        assert rows[0]["latest_run_id"] == "run-single-selected-window"
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_preloads_note_lookup_without_per_row_note_scan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "paper_note_lookup",
                "Paper With Note-backed PDF",
                "INDEXED",
                None,
                "summary",
            ),
        )
        conn.commit()
        conn.close()

        vault_dir = tmp_path / "vault"
        local_pdf = tmp_path / "paper-note-lookup.pdf"
        local_pdf.write_bytes(b"%PDF-1.4\n%note lookup preload\n")
        _write(
            vault_dir / "Inbox" / "PaperPipe" / "Paper Note Lookup.md",
            _note_content(
                note_id="paper_note_lookup",
                alias="Paper Note Lookup",
                doi="10.1000/paper-note-lookup",
                pdf_url=f"file://{quote(str(local_pdf))}",
            ),
        )

        monkeypatch.setattr(
            paper_notes_router,
            "load_config",
            lambda: SimpleNamespace(paths=SimpleNamespace(obsidian_vault=vault_dir)),
        )
        monkeypatch.setattr(
            api_main.paper_notes,
            "_find_note_item_for_paper_id",
            lambda items, paper_id: (_ for _ in ()).throw(
                AssertionError(f"unexpected per-row note scan for {paper_id}")
            ),
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_note_lookup"]["pdf_exists"] is True
        assert by_id["paper_note_lookup"]["pdf_path"] == mask_local_path(str(local_pdf))
        assert by_id["paper_note_lookup"]["access_summary"] == {
            "status_label": "user_imported_pdf",
            "open_access_url": None,
            "institution_access_url": None,
            "local_pdf_url": "/papers/paper_note_lookup/pdf",
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_listing_preloads_ops_summary_without_per_row_artifact_scan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "storage" / "artifacts"
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(artifacts_dir))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_ops_batch", "Batch Ops Paper", "INDEXED", "summary"),
        )
        run_dir = artifacts_dir / "paper_ops_batch" / "run-ops-batch"
        _write_artifact_run(
            run_dir,
            claimset={"claims": [{"claim_id": "c1"}]},
            stats_report={"checks": [{"id": "check-1"}]},
        )
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            ("job-ops-batch", "run-ops-batch", "paper_ops_batch", "completed", str(run_dir)),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(
            paper_ops_summary,
            "preferred_artifact_paper_dir",
            lambda paper_id, root=None: (_ for _ in ()).throw(
                AssertionError(f"unexpected artifact dir scan for {paper_id}")
            ),
        )

        client = TestClient(api_main.app)
        listing = client.get("/papers")

        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_ops_batch"]["ops_summary"]["state"] == "healthy"
        assert by_id["paper_ops_batch"]["ops_summary"]["stats_check_count"] == 1
        assert by_id["paper_ops_batch"]["latest_run_id"] == "run-ops-batch"
    finally:
        db_utils.DB_PATH = original_db_path


def test_db_backed_paper_item_reuses_ops_candidate_ids_within_row_build(monkeypatch):
    candidate_id_calls: list[str] = []
    original_ops_candidate_ids = api_main._ops_summary_candidate_ids

    def _record_ops_candidate_ids(paper_id):
        candidate_id_calls.append(str(paper_id))
        return original_ops_candidate_ids(paper_id)

    monkeypatch.setattr(api_main, "_ops_summary_candidate_ids", _record_ops_candidate_ids)
    monkeypatch.setattr(api_main, "_resolve_db_backed_paper_pdf_availability", lambda *args, **kwargs: (None, False))
    monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "_latest_run_id_from_artifact_cache_for_candidate_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "_latest_run_id_for_candidate_ids", lambda *args, **kwargs: None)

    item = api_main._build_db_backed_paper_item_from_row(
        {
            "paper_id": "zotero:paper_item_ops_candidates",
            "title": "Paper item ops candidates",
            "status": "INDEXED",
            "pdf_path": None,
            "issues": 0,
            "issues_label": None,
            "issues_state": "clear",
        },
        artifact_cache={},
        artifacts_path=Path("/tmp"),
        latest_run_id_lookup={},
    )

    assert item["paper_id"] == "zotero:paper_item_ops_candidates"
    assert item["latest_run_id"] is None
    assert candidate_id_calls == ["zotero:paper_item_ops_candidates"]


def test_db_backed_paper_item_uses_preview_access_only_for_source_row(monkeypatch):
    class PreviewOnlyRow:
        def __init__(self, values):
            self._values = values

        def __getitem__(self, key):
            return self._values[key]

        def __iter__(self):
            raise AssertionError("db-backed paper item builder should not materialize dict(row)")

    monkeypatch.setattr(api_main, "_resolve_db_backed_paper_pdf_availability", lambda *args, **kwargs: (None, False))
    monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "_latest_run_id_from_artifact_cache_for_candidate_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "_latest_run_id_for_candidate_ids", lambda *args, **kwargs: None)

    row = PreviewOnlyRow(
        {
            "paper_id": "zotero:paper_item_preview_access",
            "title": "Paper item preview access",
            "authors": "Tester, Alice",
            "year": 2026,
            "doi": "10.1000/preview-access",
            "link": "https://example.com/paper-item-preview-access",
            "publisher_url": None,
            "pdf_link": None,
            "pdf_path": None,
            "pdf_status": None,
            "status": "INDEXED",
            "issues": 0,
            "issues_label": None,
            "issues_state": "clear",
            "latest_job_id": "job-preview-access",
            "updated_at": "2026-04-22T00:00:00Z",
            "is_escalated": False,
            "escalation_reason": None,
            "escalation_final_route": None,
            "escalation_in_biomedical_scope": None,
            "escalation_reason_codes": [],
            "feedback_json": json.dumps(
                {
                    "links": {
                        "institutional_proxy_url": "https://example.com/proxy-preview-access"
                    }
                }
            ),
            "abstract": "Preview access abstract",
        }
    )

    item = api_main._build_db_backed_paper_item_from_row(
        row,
        artifact_cache={},
        artifacts_path=Path("/tmp"),
        latest_run_id_lookup={},
    )

    assert item["paper_id"] == "zotero:paper_item_preview_access"
    assert item["abstract"] == "Preview access abstract"
    assert item["access_summary"].institution_access_url == "https://example.com/proxy-preview-access"
    assert item["latest_run_id"] is None


def test_db_backed_paper_item_reuses_preloaded_artifact_cache_for_ops_summary(monkeypatch):
    monkeypatch.setattr(api_main, "_resolve_db_backed_paper_pdf_availability", lambda *args, **kwargs: (None, False))
    monkeypatch.setattr(
        api_main,
        "build_ops_summary_for_candidate_ids",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("db-backed row build should reuse preloaded artifact cache before rebuilding ops summary")
        ),
    )
    monkeypatch.setattr(
        api_main,
        "_latest_run_id_from_artifact_cache_for_candidate_ids",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("db-backed row build should not rescan artifact latest-run state when ops summary has a run id")
        ),
    )

    item = api_main._build_db_backed_paper_item_from_row(
        {
            "paper_id": "paper_item_preloaded_ops_cache",
            "title": "Paper item preloaded ops cache",
            "status": "INDEXED",
            "pdf_path": None,
            "issues": 0,
            "issues_label": None,
            "issues_state": "clear",
        },
        artifact_cache={
            "paper_item_preloaded_ops_cache": paper_ops_summary.ArtifactOperationalSnapshot(
                paper_id="paper_item_preloaded_ops_cache",
                run_id="run-preloaded-ops-cache",
                updated_at="2026-04-21T00:00:00+00:00",
                mtime=1.0,
                has_claimset=True,
                has_stats_report=True,
                stats_check_count=1,
            )
        },
        artifacts_path=Path("/tmp"),
        latest_run_id_lookup={},
    )

    assert item["paper_id"] == "paper_item_preloaded_ops_cache"
    assert item["ops_summary"].state == "healthy"
    assert item["latest_run_id"] == "run-preloaded-ops-cache"


def test_db_backed_paper_item_skips_latest_run_fallback_when_artifact_cache_already_proves_miss(monkeypatch):
    monkeypatch.setattr(api_main, "_resolve_db_backed_paper_pdf_availability", lambda *args, **kwargs: (None, False))
    monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "_latest_run_id_from_artifact_cache_for_candidate_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api_main,
        "_latest_run_id_for_candidate_ids",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("db-backed row build should skip latest_run fallback when artifact cache already proves a clear miss")
        ),
    )

    paper_id = "zotero:paper_item_clear_miss"
    item = api_main._build_db_backed_paper_item_from_row(
        {
            "paper_id": paper_id,
            "title": "Paper item clear miss",
            "status": "INDEXED",
            "pdf_path": None,
            "issues": 0,
            "issues_label": None,
            "issues_state": "clear",
        },
        artifact_cache={
            candidate_id: None
            for candidate_id in api_main._ops_summary_candidate_ids(paper_id)
        },
        artifacts_path=Path("/tmp"),
        latest_run_id_lookup={},
    )

    assert item["paper_id"] == paper_id
    assert item["latest_run_id"] is None


def test_selected_db_page_context_reuses_ops_candidate_ids_across_selected_window(tmp_path, monkeypatch):
    candidate_id_calls: list[str] = []
    original_ops_candidate_ids = api_main._ops_summary_candidate_ids
    original_db_path = db_utils.DB_PATH

    db_utils.DB_PATH = tmp_path / "state.db"
    db_utils.init_db()

    def _record_ops_candidate_ids(paper_id):
        candidate_id_calls.append(str(paper_id))
        return original_ops_candidate_ids(paper_id)

    monkeypatch.setattr(api_main, "_ops_summary_candidate_ids", _record_ops_candidate_ids)
    monkeypatch.setattr(
        api_main,
        "_resolve_db_backed_paper_pdf_availability",
        lambda *args, **kwargs: (None, False),
    )
    monkeypatch.setattr(api_main, "build_ops_summary_for_candidate_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "_latest_run_id_from_artifact_cache_for_candidate_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "_latest_run_id_for_candidate_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_main, "_preload_artifact_snapshots_for_candidate_id_groups", lambda *args, **kwargs: None)

    paper_id = "zotero:selected_window_ops_candidates"
    selected_candidates = [
        {
            "kind": "db",
            "paper_id": paper_id,
            "sort_updated_at": "2026-04-21T00:00:00Z",
            "row": {
                "paper_id": paper_id,
                "title": "Selected window ops candidates",
                "status": "INDEXED",
                "pdf_path": None,
                "issues": 0,
                "issues_label": None,
                "issues_state": "clear",
                "updated_at": "2026-04-21T00:00:00Z",
            },
        }
    ]

    def _row_loader(paper_ids):
        assert paper_ids == [paper_id]
        return {paper_id: selected_candidates[0]["row"]}

    context = api_main._prepare_selected_db_paper_page_context(
        selected_candidates=selected_candidates,
        note_items=None,
        note_slug_by_db_paper_id={},
        row_loader=_row_loader,
    )

    assert context.ops_candidate_ids_by_paper_id[paper_id] == ["zotero:selected_window_ops_candidates", "selected_window_ops_candidates"]

    try:
        latest_run_lookup_candidates = api_main._selected_db_paper_ids_needing_latest_run_lookup(
            context.selected_db_paper_ids,
            context.artifact_cache,
            ops_candidate_ids_by_paper_id=context.ops_candidate_ids_by_paper_id,
        )
        assert latest_run_lookup_candidates == [paper_id]

        latest_run_lookup = api_main._preload_latest_run_ids_for_papers(
            latest_run_lookup_candidates,
            ops_candidate_ids_by_paper_id=context.ops_candidate_ids_by_paper_id,
        )
        assert latest_run_lookup == {}

        item = api_main._build_db_backed_paper_item_from_row(
            context.selected_db_rows_by_id[paper_id],
            artifact_cache=context.artifact_cache,
            artifacts_path=Path("/tmp"),
            latest_run_id_lookup=latest_run_lookup,
            ops_candidate_ids=context.ops_candidate_ids_by_paper_id[paper_id],
        )

        assert item["paper_id"] == paper_id
        assert item["latest_run_id"] is None
        assert candidate_id_calls == [paper_id]
    finally:
        db_utils.DB_PATH = original_db_path


def test_selected_db_page_context_dedupes_duplicate_selected_db_paper_ids(tmp_path, monkeypatch):
    candidate_id_calls: list[str] = []
    row_loader_calls: list[list[str]] = []
    original_ops_candidate_ids = api_main._ops_summary_candidate_ids
    original_db_path = db_utils.DB_PATH

    db_utils.DB_PATH = tmp_path / "state.db"
    db_utils.init_db()

    def _record_ops_candidate_ids(paper_id):
        candidate_id_calls.append(str(paper_id))
        return original_ops_candidate_ids(paper_id)

    monkeypatch.setattr(api_main, "_ops_summary_candidate_ids", _record_ops_candidate_ids)
    monkeypatch.setattr(api_main, "_preload_artifact_snapshots_for_candidate_id_groups", lambda *args, **kwargs: None)

    paper_id = "zotero:selected_window_duplicate_db_candidate"
    duplicate_row = {
        "paper_id": paper_id,
        "title": "Selected window duplicate DB candidate",
        "status": "INDEXED",
        "pdf_path": None,
        "issues": 0,
        "issues_label": None,
        "issues_state": "clear",
        "updated_at": "2026-04-21T00:00:00Z",
    }
    selected_candidates = [
        {
            "kind": "db",
            "paper_id": paper_id,
            "sort_updated_at": "2026-04-21T00:00:00Z",
            "row": duplicate_row,
        },
        {
            "kind": "db",
            "paper_id": paper_id,
            "sort_updated_at": "2026-04-21T00:00:00Z",
            "row": duplicate_row,
        },
    ]

    def _row_loader(paper_ids):
        row_loader_calls.append(list(paper_ids))
        return {paper_id: duplicate_row}

    try:
        context = api_main._prepare_selected_db_paper_page_context(
            selected_candidates=selected_candidates,
            note_items=None,
            note_slug_by_db_paper_id={},
            row_loader=_row_loader,
        )

        assert context.selected_db_paper_ids == [paper_id]
        assert row_loader_calls == [[paper_id]]
        assert candidate_id_calls == [paper_id]
    finally:
        db_utils.DB_PATH = original_db_path


def test_selected_db_paper_ids_needing_latest_run_lookup_reuses_artifact_checks_for_equivalent_candidate_ids(
    monkeypatch,
):
    latest_run_check_calls: list[tuple[str, ...]] = []
    artifact_coverage_calls: list[tuple[str, ...]] = []

    def _record_latest_run(candidate_ids, artifact_cache):
        latest_run_check_calls.append(tuple(candidate_ids))
        return None

    def _record_artifact_coverage(candidate_ids, artifact_cache):
        artifact_coverage_calls.append(tuple(candidate_ids))
        return True

    monkeypatch.setattr(api_main, "_latest_run_id_from_artifact_cache_for_candidate_ids", _record_latest_run)
    monkeypatch.setattr(api_main, "_artifact_cache_covers_candidate_ids", _record_artifact_coverage)

    lookup_candidates = api_main._selected_db_paper_ids_needing_latest_run_lookup(
        [
            "zotero:paper_latest_run_shared_a",
            "paper_latest_run_shared_b",
        ],
        {},
        ops_candidate_ids_by_paper_id={
            "zotero:paper_latest_run_shared_a": [
                "",
                "paper_latest_run_shared",
                " zotero:paper_latest_run_shared ",
                "paper_latest_run_shared",
            ],
            "paper_latest_run_shared_b": [
                "zotero:paper_latest_run_shared",
                "paper_latest_run_shared",
                "  ",
            ],
        },
    )

    assert lookup_candidates == []
    assert latest_run_check_calls == [
        ("paper_latest_run_shared", "zotero:paper_latest_run_shared")
    ]
    assert artifact_coverage_calls == [
        ("paper_latest_run_shared", "zotero:paper_latest_run_shared")
    ]


def test_preload_latest_run_ids_skips_candidate_ids_already_proven_missing_in_artifact_cache(tmp_path, monkeypatch):
    original_db_path = db_utils.DB_PATH
    original_get_db_connection = api_main.get_db_connection

    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        run_dir = tmp_path / "storage" / "artifacts" / "paper_latest_run_uncached" / "run-latest-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                "job-latest-run-uncached",
                "run-latest-run",
                "paper_latest_run_uncached",
                "completed",
                str(run_dir),
            ),
        )
        conn.commit()
        conn.close()

        executed_queries: list[tuple[str, tuple[object, ...]]] = []

        class _RecordingConnection:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, params=()):
                executed_queries.append((" ".join(str(sql).split()), tuple(params)))
                return self._inner.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        def _recording_get_db_connection():
            return _RecordingConnection(original_get_db_connection())

        monkeypatch.setattr(api_main, "get_db_connection", _recording_get_db_connection)

        paper_id = "zotero:paper_latest_run_uncached"
        latest_run_lookup = api_main._preload_latest_run_ids_for_papers(
            [paper_id],
            ops_candidate_ids_by_paper_id={
                paper_id: [paper_id, "", " paper_latest_run_uncached ", "  "],
            },
            artifact_cache={
                paper_id: None,
            },
        )

        jobs_queries = [
            params
            for query, params in executed_queries
            if "FROM jobs" in query and "paper_id IN (" in query
        ]
        assert jobs_queries == [("paper_latest_run_uncached",)]
        assert latest_run_lookup == {
            paper_id: "run-latest-run",
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_selected_db_paper_ids_needing_latest_run_lookup_skips_papers_when_artifact_cache_already_covers_clear_miss():
    paper_id = "zotero:paper_latest_run_clear_miss"

    lookup_candidates = api_main._selected_db_paper_ids_needing_latest_run_lookup(
        [paper_id],
        {
            paper_id: None,
            "paper_latest_run_clear_miss": None,
        },
        ops_candidate_ids_by_paper_id={
            paper_id: [paper_id, "", " paper_latest_run_clear_miss ", "  "],
        },
    )

    assert lookup_candidates == []


def test_preload_latest_run_ids_stops_after_all_owner_papers_are_resolved(tmp_path, monkeypatch):
    original_db_path = db_utils.DB_PATH
    original_get_db_connection = api_main.get_db_connection

    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        run_dir = tmp_path / "storage" / "artifacts" / "paper_many_latest_run_variants" / "run-many-latest-run"
        run_dir.mkdir(parents=True, exist_ok=True)
        first_candidate_id = "paper_many_latest_run_variants_candidate_000"
        conn.execute(
            """
            INSERT INTO jobs (job_id, run_id, paper_id, status, artifact_dir, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                "job-many-latest-run",
                "run-many-latest-run",
                first_candidate_id,
                "completed",
                str(run_dir),
            ),
        )
        conn.commit()
        conn.close()

        executed_queries: list[tuple[str, tuple[object, ...]]] = []

        class _RecordingConnection:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, params=()):
                executed_queries.append((" ".join(str(sql).split()), tuple(params)))
                return self._inner.execute(sql, params)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        def _recording_get_db_connection():
            return _RecordingConnection(original_get_db_connection())

        monkeypatch.setattr(api_main, "get_db_connection", _recording_get_db_connection)

        paper_id = "zotero:paper_many_latest_run_variants"
        candidate_ids = [
            f"paper_many_latest_run_variants_candidate_{index:03d}"
            for index in range(401)
        ]
        latest_run_lookup = api_main._preload_latest_run_ids_for_papers(
            [paper_id],
            ops_candidate_ids_by_paper_id={paper_id: candidate_ids},
        )

        jobs_queries = [
            params
            for query, params in executed_queries
            if "FROM jobs" in query and "paper_id IN (" in query
        ]
        assert len(jobs_queries) == 1
        assert first_candidate_id in jobs_queries[0]
        assert latest_run_lookup == {
            paper_id: "run-many-latest-run",
        }
    finally:
        db_utils.DB_PATH = original_db_path


def test_papers_endpoints_include_content_review_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPERPIPE_ARTIFACTS_DIR", str(tmp_path / "storage" / "artifacts"))

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                issues INTEGER,
                issues_label TEXT,
                issues_state TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_flagged", "Flagged Paper", "INDEXED", 2, "2 mapping ambiguities", None, "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_clear", "Clear Paper", "INDEXED", 0, "No critical issues", None, "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_unavailable", "Unavailable Paper", "INDEXED", 0, "Not analyzed", None, "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, issues, issues_label, issues_state, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_explicit", "Explicit State Paper", "INDEXED", 0, "No critical issues", "unavailable", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_new", "New Paper", "NEW", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_pending", "Pending Paper", "PENDING_REVIEW", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("paper_approved", "Approved Paper", "APPROVED", "summary"),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        listing = client.get("/papers")
        assert listing.status_code == 200
        by_id = {row["paper_id"]: row for row in listing.json()}
        assert by_id["paper_flagged"]["issues_state"] == "flagged"
        assert by_id["paper_clear"]["issues_state"] == "clear"
        assert by_id["paper_unavailable"]["issues_state"] == "unavailable"
        assert by_id["paper_explicit"]["issues_state"] == "unavailable"
        assert by_id["paper_new"]["issues_state"] == "unavailable"
        assert by_id["paper_pending"]["issues_state"] == "flagged"
        assert by_id["paper_approved"]["issues_state"] == "clear"

        detail = client.get("/papers/paper_unavailable")
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["issues_label"] == "Not analyzed"
        assert payload["issues_state"] == "unavailable"

        explicit_detail = client.get("/papers/paper_explicit")
        assert explicit_detail.status_code == 200
        explicit_payload = explicit_detail.json()
        assert explicit_payload["issues_label"] == "No critical issues"
        assert explicit_payload["issues_state"] == "unavailable"
    finally:
        db_utils.DB_PATH = original_db_path


def test_init_db_backfills_paper_issues_state_column(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        conn = db_utils.sqlite3.connect(db_utils.DB_PATH)
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

        db_utils.init_db()

        conn = db_utils.get_db_connection()
        columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
        conn.close()

        assert "issues_state" in columns
    finally:
        db_utils.DB_PATH = original_db_path


def test_paper_pdf_endpoint_serves_existing_file_and_handles_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    original_db_path = db_utils.DB_PATH
    db_utils.DB_PATH = tmp_path / "state.db"
    try:
        db_utils.init_db()
        conn = db_utils.get_db_connection()
        conn.execute(
            """
            CREATE TABLE papers (
                paper_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                pdf_path TEXT,
                pdf_status TEXT,
                summary TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        existing_pdf = tmp_path / "served.pdf"
        existing_pdf.write_bytes(b"%PDF-1.4\n%test\n")
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_served", "Served PDF", "INDEXED", str(existing_pdf), "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_missing_path", "Missing Path", "INDEXED", "", "summary"),
        )
        conn.execute(
            """
            INSERT INTO papers (paper_id, title, status, pdf_path, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("p_missing_file", "Missing File", "INDEXED", str(tmp_path / "gone.pdf"), "summary"),
        )
        conn.commit()
        conn.close()

        client = TestClient(api_main.app)

        served = client.get("/papers/p_served/pdf")
        assert served.status_code == 200
        assert served.headers.get("content-type", "").startswith("application/pdf")
        assert served.content.startswith(b"%PDF")

        missing_path = client.get("/papers/p_missing_path/pdf")
        assert missing_path.status_code == 404
        assert "PDF path not registered" in missing_path.json()["detail"]

        missing_file = client.get("/papers/p_missing_file/pdf")
        assert missing_file.status_code == 404
        assert "PDF file not found" in missing_file.json()["detail"]

        missing_paper = client.get("/papers/nope/pdf")
        assert missing_paper.status_code == 404
        assert missing_paper.json()["detail"] == "Paper not found"
    finally:
        db_utils.DB_PATH = original_db_path
