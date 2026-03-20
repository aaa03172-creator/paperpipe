from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from src.method_comparisons.service import generate_method_comparison, get_method_comparison
from src.schemas.method_comparison import MethodComparisonRequest


def _write_claimset(run_dir: Path, payload: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "claimset.resolved.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_note(vault_path: Path, slug: str, *, note_id: str, title: str) -> None:
    note_path = vault_path / f"{slug}.md"
    note_path.write_text(
        f"---\nid: {note_id}\naliases:\n  - {title}\n---\n\n# {title}\n",
        encoding="utf-8",
    )
    state_path = vault_path / ".pp" / slug / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "paper_slug": slug,
                "updated_at": "2026-03-18T00:00:00+00:00",
                "runs": [],
                "claimset": [],
            }
        ),
        encoding="utf-8",
    )


def test_generate_method_comparison_saves_json_csv_and_markdown(tmp_path, monkeypatch) -> None:
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    _write_note(vault_path, "paper-alpha", note_id="doi:10.1000/a", title="Alpha Trial")
    _write_note(vault_path, "paper-beta", note_id="doi:10.1000/b", title="Beta Trial")

    _write_claimset(
        artifacts_root / "doi:10.1000/a" / "run_a1",
        {
            "doc_id": "doi:10.1000/a",
            "claims": [
                {
                    "claim_id": "CLM-A",
                    "statement": "Intervention: Ketone ester. Comparator: Placebo. Primary outcome: ADAS-Cog score.",
                    "sample_size": 48,
                    "evidence_spans": [{"quote": "Intervention: Ketone ester. Comparator: Placebo. Primary outcome: ADAS-Cog score. Sample size: 48.", "page": 1}],
                }
            ],
        },
    )
    _write_claimset(
        artifacts_root / "doi:10.1000/b" / "run_b1",
        {
            "doc_id": "doi:10.1000/b",
            "claims": [
                {
                    "claim_id": "CLM-B",
                    "statement": "Intervention: MCT oil. Comparator: Standard care. Primary outcome: MMSE score.",
                    "sample_size": 32,
                    "evidence_spans": [{"quote": "Intervention: MCT oil. Comparator: Standard care. Primary outcome: MMSE score. Sample size: 32.", "page": 2}],
                }
            ],
        },
    )

    request = MethodComparisonRequest(
        comparison_id="methodcmp_service_demo",
        paper_ids=["doi:10.1000/a", "doi:10.1000/b"],
        field_ids=["intervention", "comparator", "primary_readout", "sample_size"],
    )
    result = generate_method_comparison(
        request=request,
        root=output_root,
        artifacts_root=artifacts_root,
        vault_path=vault_path,
    )

    assert result.comparison.comparison_id == "methodcmp_service_demo"
    assert [row.paper_slug for row in result.comparison.rows] == ["paper-alpha", "paper-beta"]
    assert [row.title for row in result.comparison.rows] == ["Alpha Trial", "Beta Trial"]
    assert [column.field_id for column in result.comparison.columns] == [
        "intervention",
        "comparator",
        "primary_readout",
        "sample_size",
    ]
    assert "paper_id,paper_slug,citekey,title,intervention,intervention__status,intervention__refs" in result.csv_text
    assert "Alpha Trial" in result.markdown
    assert "Ketone ester (explicit)" in result.markdown

    loaded = get_method_comparison("methodcmp_service_demo", root=output_root)
    assert loaded.comparison.model_dump(mode="json") == result.comparison.model_dump(mode="json")
    assert loaded.csv_text == result.csv_text
    assert loaded.markdown == result.markdown


def test_generate_method_comparison_resolves_title_from_db_when_available(tmp_path, monkeypatch) -> None:
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    _write_note(vault_path, "paper-alpha", note_id="paper-001", title="Fallback Note Title")
    _write_claimset(
        artifacts_root / "paper-001" / "run_001",
        {
            "doc_id": "paper-001",
            "claims": [
                {
                    "claim_id": "CLM-001",
                    "statement": "Intervention: Ketone ester.",
                    "evidence_spans": [{"quote": "Intervention: Ketone ester.", "page": 1}],
                }
            ],
        },
    )

    db_path = tmp_path / "state.db"
    monkeypatch.setenv("PAPERPIPE_DB_PATH", str(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE papers (paper_id TEXT PRIMARY KEY, title TEXT)")
    conn.execute("INSERT INTO papers (paper_id, title) VALUES (?, ?)", ("paper-001", "DB Title"))
    conn.commit()
    conn.close()

    result = generate_method_comparison(
        request=MethodComparisonRequest(
            comparison_id="methodcmp_db_title",
            paper_ids=["paper-001"],
            field_ids=["intervention"],
        ),
        root=output_root,
        artifacts_root=artifacts_root,
        vault_path=vault_path,
    )

    assert result.comparison.rows[0].title == "DB Title"


def test_generate_method_comparison_resolves_slug_via_normalized_note_identifier(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    _write_note(vault_path, "alpha-note", note_id="doi:10.1000/abc", title="Alpha Trial")
    _write_claimset(
        artifacts_root / "doi101000abc" / "run_001",
        {
            "doc_id": "doi101000abc",
            "claims": [
                {
                    "claim_id": "CLM-001",
                    "statement": "Intervention: Ketone ester.",
                    "evidence_spans": [{"quote": "Intervention: Ketone ester.", "page": 1}],
                }
            ],
        },
    )

    result = generate_method_comparison(
        request=MethodComparisonRequest(
            comparison_id="methodcmp_normalized_slug",
            paper_ids=["doi101000abc"],
            field_ids=["intervention"],
        ),
        root=output_root,
        artifacts_root=artifacts_root,
        vault_path=vault_path,
    )

    assert result.comparison.rows[0].paper_slug == "alpha-note"
    assert result.comparison.rows[0].title == "Alpha Trial"


def test_generate_method_comparison_ignores_non_paper_note_id_collisions(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / "aaa-scratch.md").write_text(
        "---\nid: doi:10.1000/abc\n---\n\n# Scratch note\n",
        encoding="utf-8",
    )
    _write_note(vault_path, "paper-alpha", note_id="doi:10.1000/abc", title="Alpha Trial")
    _write_claimset(
        artifacts_root / "doi101000abc" / "run_001",
        {
            "doc_id": "doi101000abc",
            "claims": [
                {
                    "claim_id": "CLM-001",
                    "statement": "Intervention: Ketone ester.",
                    "evidence_spans": [{"quote": "Intervention: Ketone ester.", "page": 1}],
                }
            ],
        },
    )

    result = generate_method_comparison(
        request=MethodComparisonRequest(
            comparison_id="methodcmp_note_collision",
            paper_ids=["doi101000abc"],
            field_ids=["intervention"],
        ),
        root=output_root,
        artifacts_root=artifacts_root,
        vault_path=vault_path,
    )

    assert result.comparison.rows[0].paper_slug == "paper-alpha"
    assert result.comparison.rows[0].title == "Alpha Trial"


def test_generate_method_comparison_requires_slug_resolution_without_explicit_fallback(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    _write_claimset(
        artifacts_root / "paper-001" / "run_001",
        {
            "doc_id": "paper-001",
            "claims": [
                {
                    "claim_id": "CLM-001",
                    "statement": "Intervention: Ketone ester.",
                    "evidence_spans": [{"quote": "Intervention: Ketone ester.", "page": 1}],
                }
            ],
        },
    )

    try:
        generate_method_comparison(
            request=MethodComparisonRequest(
                comparison_id="methodcmp_missing_slug",
                paper_ids=["paper-001"],
                field_ids=["intervention"],
            ),
            root=output_root,
            artifacts_root=artifacts_root,
        )
    except ValueError as exc:
        assert "paper_slug" in str(exc)
    else:
        raise AssertionError("expected slug resolution failure")


def test_generate_method_comparison_allows_explicit_slug_fallback_with_warning(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    _write_claimset(
        artifacts_root / "paper-001" / "run_001",
        {
            "doc_id": "paper-001",
            "claims": [
                {
                    "claim_id": "CLM-001",
                    "statement": "Intervention: Ketone ester.",
                    "evidence_spans": [{"quote": "Intervention: Ketone ester.", "page": 1}],
                }
            ],
        },
    )

    result = generate_method_comparison(
        request=MethodComparisonRequest(
            comparison_id="methodcmp_slug_fallback",
            paper_ids=["paper-001"],
            field_ids=["intervention"],
        ),
        root=output_root,
        artifacts_root=artifacts_root,
        allow_paper_id_slug_fallback=True,
    )

    assert result.comparison.rows[0].paper_slug == "paper-001"
    assert result.comparison.warnings == ["paper_slug unresolved for paper-001; using paper_id as fallback."]


def test_generate_method_comparison_is_deterministic_for_row_and_column_order(tmp_path) -> None:
    artifacts_root = tmp_path / "artifacts"
    output_root = tmp_path / "method_comparisons"
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    _write_note(vault_path, "paper-a", note_id="paper-a", title="Paper A")
    _write_note(vault_path, "paper-b", note_id="paper-b", title="Paper B")
    _write_claimset(
        artifacts_root / "paper-a" / "run_a",
        {
            "doc_id": "paper-a",
            "claims": [{"statement": "Intervention: A. Comparator: X.", "evidence_spans": [{"quote": "Intervention: A. Comparator: X.", "page": 1}]}],
        },
    )
    _write_claimset(
        artifacts_root / "paper-b" / "run_b",
        {
            "doc_id": "paper-b",
            "claims": [{"statement": "Intervention: B. Comparator: Y.", "evidence_spans": [{"quote": "Intervention: B. Comparator: Y.", "page": 2}]}],
        },
    )

    request = MethodComparisonRequest(
        comparison_id="methodcmp_order_demo",
        paper_ids=["paper-b", "paper-a"],
        field_ids=["comparator", "intervention"],
    )
    fixed_now = datetime(2026, 3, 18, 16, 20, 52, tzinfo=timezone.utc)
    first = generate_method_comparison(
        request=request,
        root=output_root,
        artifacts_root=artifacts_root,
        vault_path=vault_path,
        now=fixed_now,
    )
    second = generate_method_comparison(
        request=request,
        root=output_root,
        artifacts_root=artifacts_root,
        vault_path=vault_path,
        now=fixed_now,
    )

    assert [row.paper_id for row in first.comparison.rows] == ["paper-b", "paper-a"]
    assert [column.field_id for column in first.comparison.columns] == ["comparator", "intervention"]
    assert first.csv_text == second.csv_text
    assert first.markdown == second.markdown
