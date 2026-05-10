from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import yaml

from src.profiles.research_dna_schema import (
    ApprovalAuditEntry,
    ExternalBenchmarkManifest,
    ExternalBenchmarkStudyDecision,
    InterviewLogEntry,
    QueryVersion,
    ResearchDNA,
    RunLogEntry,
    ScreeningLogEntry,
)
from src.profiles.research_dna_store import (
    ResearchDNARevisionConflictError,
    append_approval_audit,
    append_interview_log,
    append_run_log,
    append_screening_log,
    load_external_benchmark_manifest,
    load_external_benchmark_manifest_from_path,
    list_research_dna_ids,
    load_research_dna,
    research_dna_benchmark_manifest_path,
    research_dna_log_path,
    research_dna_profile_path,
    save_external_benchmark_manifest,
    save_research_dna,
)


def _sample_dna() -> ResearchDNA:
    return ResearchDNA(
        id="dna_mci_medium_chain_triglycerides",
        title="Mild cognitive impairment and medium-chain triglycerides",
        intent="systematic_review",
        query_versions=[
            QueryVersion(
                version="v1",
                mode="recall",
                per_db={"pubmed": "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"},
                change_summary="initial draft",
                created_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
                created_by="human_cli:tester",
            )
        ],
    )


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_research_dna_store_roundtrip_creates_expected_layout(tmp_path):
    root = tmp_path / "research_dna"
    dna = _sample_dna()

    save_research_dna(dna, root)
    loaded = load_research_dna(dna.id, root)

    assert loaded.id == dna.id
    assert research_dna_profile_path(dna.id, root).exists()
    assert (root / dna.id / "versions" / "v1.yaml").exists()
    assert (root / dna.id / "logs").exists()
    assert list_research_dna_ids(root) == [dna.id]
    snapshot = yaml.safe_load((root / dna.id / "versions" / "v1.yaml").read_text(encoding="utf-8"))
    assert snapshot["schema_version"] == "research_dna.query_snapshot.v1"
    assert snapshot["dna_id"] == dna.id
    assert snapshot["query_version"]["version"] == "v1"
    assert "pilot" not in snapshot


def test_research_dna_store_appends_typed_logs(tmp_path):
    root = tmp_path / "research_dna"
    dna = _sample_dna()
    save_research_dna(dna, root)

    ts = datetime(2026, 3, 11, 1, 0, tzinfo=timezone.utc)
    append_interview_log(
        dna.id,
        InterviewLogEntry(
            ts=ts,
            dna_id=dna.id,
            round="researcher",
            question_id="researcher_1",
            question="What is the intent?",
            answer="systematic_review",
            actor_type="human_cli",
            actor_id="tester",
        ),
        root,
    )
    append_run_log(
        dna.id,
        RunLogEntry(
            ts=ts,
            run_id="pilot_001",
            dna_id=dna.id,
            query_version="v1",
            status="completed",
            actor_type="human_cli",
            actor_id="tester",
            sources=["pubmed"],
            retrieved_count=40,
            deduped_count=30,
            dedupe_rate=0.25,
            pilot_n=30,
            labeled_count=30,
            include_count=9,
            exclude_count=18,
            unclear_count=3,
            precision_proxy=0.3,
            top_reason_codes=["wrong_population", "duplicate"],
        ),
        root,
    )
    append_screening_log(
        dna.id,
        ScreeningLogEntry(
            ts=ts,
            dna_id=dna.id,
            run_id="pilot_001",
            candidate_id="pmid:123",
            decision="exclude",
            reason_code="wrong_population",
            actor_type="human_cli",
            actor_id="tester",
        ),
        root,
    )
    append_approval_audit(
        dna.id,
        ApprovalAuditEntry(
            ts=ts,
            dna_id=dna.id,
            action="approve_pilot",
            actor_type="human_cli",
            actor_id="tester",
            reason="ready for bounded pilot",
            after_version="v1",
            run_id="pilot_001",
        ),
        root,
    )

    interview_rows = _read_jsonl(research_dna_log_path(dna.id, "interview", root))
    run_rows = _read_jsonl(research_dna_log_path(dna.id, "runs", root))
    screening_rows = _read_jsonl(research_dna_log_path(dna.id, "screening", root))
    approval_rows = _read_jsonl(research_dna_log_path(dna.id, "approval_audit", root))

    assert interview_rows[0]["round"] == "researcher"
    assert run_rows[0]["precision_proxy"] == 0.3
    assert screening_rows[0]["reason_code"] == "wrong_population"
    assert approval_rows[0]["action"] == "approve_pilot"


def test_research_dna_store_sanitizes_log_text_before_append(tmp_path):
    root = tmp_path / "research_dna"
    dna = _sample_dna()
    save_research_dna(dna, root)

    ts = datetime(2026, 3, 11, 1, 0, tzinfo=timezone.utc)
    append_interview_log(
        dna.id,
        InterviewLogEntry(
            ts=ts,
            dna_id=dna.id,
            round="researcher",
            question_id="researcher_secret",
            question="Which endpoint should we use?",
            answer="Use Authorization: Bearer dnainterviewtoken123 and sk-proj-dnainterviewsecret123456.",
            actor_type="human_cli",
            actor_id="tester",
        ),
        root,
    )
    append_screening_log(
        dna.id,
        ScreeningLogEntry(
            ts=ts,
            dna_id=dna.id,
            run_id="pilot_secret_001",
            candidate_id="pmid:123",
            decision="exclude",
            reason_code="wrong_population",
            note="Screening note mysql://ctx_user:ctx_password@example.test:3306/paperpipe",
            actor_type="human_cli",
            actor_id="tester",
        ),
        root,
    )
    append_approval_audit(
        dna.id,
        ApprovalAuditEntry(
            ts=ts,
            dna_id=dna.id,
            action="approve_pilot",
            actor_type="human_cli",
            actor_id="tester",
            reason="Approving with postgres://ctx_user:ctx_password@example.test:5432/paperpipe",
            after_version="v1",
        ),
        root,
    )

    raw_logs = "\n".join(
        [
            research_dna_log_path(dna.id, "interview", root).read_text(encoding="utf-8"),
            research_dna_log_path(dna.id, "screening", root).read_text(encoding="utf-8"),
            research_dna_log_path(dna.id, "approval_audit", root).read_text(encoding="utf-8"),
        ]
    )
    assert "dnainterviewtoken123" not in raw_logs
    assert "sk-proj-dnainterviewsecret123456" not in raw_logs
    assert "ctx_password" not in raw_logs

    interview_rows = _read_jsonl(research_dna_log_path(dna.id, "interview", root))
    screening_rows = _read_jsonl(research_dna_log_path(dna.id, "screening", root))
    approval_rows = _read_jsonl(research_dna_log_path(dna.id, "approval_audit", root))
    assert interview_rows[0]["answer"] == "Use Authorization: <redacted> and <redacted>."
    assert screening_rows[0]["note"] == "Screening note <redacted>"
    assert approval_rows[0]["reason"] == "Approving with <redacted>"


def test_research_dna_store_rejects_stale_revision_save(tmp_path):
    root = tmp_path / "research_dna"
    dna = _sample_dna()
    save_research_dna(dna, root)

    fresh = load_research_dna(dna.id, root)
    stale = load_research_dna(dna.id, root)

    fresh.title = "Fresh title"
    save_research_dna(fresh, root, expected_revision=fresh.revision)

    stale.title = "Stale title"
    with pytest.raises(ResearchDNARevisionConflictError):
        save_research_dna(stale, root, expected_revision=stale.revision)


def test_research_dna_store_rejects_path_like_ids(tmp_path):
    root = tmp_path / "research_dna"
    dna = _sample_dna()
    save_research_dna(dna, root)

    with pytest.raises(ValueError, match="dna_id"):
        research_dna_profile_path("../escape", root)

    with pytest.raises(ValueError, match="dna_id"):
        research_dna_log_path("valid/escape", "interview", root)

    with pytest.raises(ValueError, match="manifest_id"):
        research_dna_benchmark_manifest_path(dna.id, "../escape", root)


def test_research_dna_query_version_snapshots_remain_query_only_after_metadata_updates(tmp_path):
    root = tmp_path / "research_dna"
    dna = _sample_dna()
    save_research_dna(dna, root)

    loaded = load_research_dna(dna.id, root)
    loaded.pilot.goldset = ["doi:10.1000/example"]
    save_research_dna(loaded, root, expected_revision=loaded.revision)

    snapshot = yaml.safe_load((root / dna.id / "versions" / "v1.yaml").read_text(encoding="utf-8"))
    assert snapshot["schema_version"] == "research_dna.query_snapshot.v1"
    assert snapshot["query_version"]["version"] == "v1"
    assert snapshot["query_version"]["per_db"]["pubmed"] == "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"
    assert "pilot" not in snapshot


def test_research_dna_store_roundtrip_external_benchmark_manifest(tmp_path):
    root = tmp_path / "research_dna"
    dna = _sample_dna()
    save_research_dna(dna, root)

    manifest = ExternalBenchmarkManifest(
        manifest_id="pmc11074881_mci_subset_20260313",
        dna_id=dna.id,
        source_label="PMC11074881 candidate MCI subset",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC11074881/",
        created_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
        created_by="human_cli:tester",
        scope_note="Adjudicated MCI-only subset from mixed AD/MCI review",
        studies=[
            ExternalBenchmarkStudyDecision(
                source_reference="B48",
                title="A ketogenic drink improves cognition in mild cognitive impairment: results of a 6-month RCT.",
                identifier="doi:10.1002/alz.12206",
                decision="include",
                reason="Matches current MCI-only population and MCT intervention boundary",
                local_overlap=True,
            ),
            ExternalBenchmarkStudyDecision(
                source_reference="B39",
                title="Effects of beta-hydroxybutyrate on cognition in memory-impaired adults.",
                identifier="doi:10.1016/S0197-4580(03)00087-3",
                decision="exclude",
                reason="Mixed probable AD and amnestic MCI population is broader than the current DNA boundary",
                local_overlap=True,
            ),
        ],
    )

    save_external_benchmark_manifest(manifest, root)
    loaded = load_external_benchmark_manifest(dna.id, manifest.manifest_id, root)

    assert research_dna_benchmark_manifest_path(dna.id, manifest.manifest_id, root).exists()
    assert loaded.source_url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC11074881/"
    assert loaded.studies[0].decision == "include"
    assert loaded.studies[1].decision == "exclude"
    assert (
        load_external_benchmark_manifest_from_path(research_dna_benchmark_manifest_path(dna.id, manifest.manifest_id, root))
        .manifest_id
        == manifest.manifest_id
    )
