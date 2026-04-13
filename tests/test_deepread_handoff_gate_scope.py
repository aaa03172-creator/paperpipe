from src.services.deepread_handoff_gate_scope import classify_deepread_handoff_gate_scope


def test_classify_deepread_handoff_gate_scope_returns_not_applicable_for_docs_only():
    report = classify_deepread_handoff_gate_scope(
        [
            "docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md",
            "docs/reports/DeepRead_Handoff_Multicase_Baseline_2026-04-08.md",
        ]
    )

    assert report.mode == "not_applicable"
    assert report.relevant_files == []
    assert report.cross_paper_files == []
    assert report.continuity_files == []
    assert report.ignored_doc_files == [
        "docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md",
        "docs/reports/DeepRead_Handoff_Multicase_Baseline_2026-04-08.md",
    ]


def test_classify_deepread_handoff_gate_scope_recommends_continuity_for_coric_only_artifacts():
    report = classify_deepread_handoff_gate_scope(
        [
            "goldset/manifests/deepread_handoff_coric_regression_20260408.json",
            "baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_backfilled/summary.json",
        ]
    )

    assert report.mode == "continuity"
    assert report.cross_paper_files == []
    assert report.continuity_files == [
        "baselines/deepread_handoff/deepread_handoff_coric_regression_20260408_backfilled/summary.json",
        "goldset/manifests/deepread_handoff_coric_regression_20260408.json",
    ]


def test_classify_deepread_handoff_gate_scope_recommends_cross_paper_for_shared_owner_files():
    report = classify_deepread_handoff_gate_scope(
        [
            "src/services/deepread_handoff_artifacts.py",
            "tests/test_deepread_handoff_artifacts.py",
            "docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md",
        ]
    )

    assert report.mode == "cross-paper"
    assert report.cross_paper_files == [
        "src/services/deepread_handoff_artifacts.py",
        "tests/test_deepread_handoff_artifacts.py",
    ]
    assert report.ignored_doc_files == ["docs/DEEPREAD_HANDOFF_QUALITY_LOOP.md"]


def test_classify_deepread_handoff_gate_scope_recommends_cross_paper_for_multicase_artifacts():
    report = classify_deepread_handoff_gate_scope(
        [
            "goldset/manifests/deepread_handoff_multicase_regression_20260408.json",
            "snapshots/deepread_handoff_gate/deepread_handoff_gate_cross_paper_smoke_20260409/summary.json",
        ]
    )

    assert report.mode == "cross-paper"
    assert report.continuity_files == []
    assert report.cross_paper_files == [
        "goldset/manifests/deepread_handoff_multicase_regression_20260408.json",
        "snapshots/deepread_handoff_gate/deepread_handoff_gate_cross_paper_smoke_20260409/summary.json",
    ]
