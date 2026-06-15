from __future__ import annotations

import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from backend import main as api_main
from scripts.eval.validate_paper_understanding_gold import validate_gold_paths
from src.schemas.claim_evidence_correction import (
    ClaimEvidenceCorrectionEvalCandidate,
    ClaimEvidenceCorrectionLocator,
    ClaimEvidenceCorrectionReviewedEvalFixture,
)
from src.schemas.paper_understanding_gold import (
    PaperUnderstandingGold,
    PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest,
    PaperUnderstandingGoldCandidateDraftPatchRequest,
    PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest,
    PaperUnderstandingGoldCandidateDraftPatchTemplateRequest,
    PaperUnderstandingGoldCurationTaskExportReport,
    PaperUnderstandingGoldCurationTarget,
    PaperUnderstandingGoldManifest,
    PaperUnderstandingGoldReleaseManifestBuildItem,
    PaperUnderstandingGoldReleasePackageReport,
    PaperUnderstandingGoldReleaseReadinessReport,
    PaperUnderstandingGoldReleaseSplitPlanReport,
    PaperUnderstandingGoldReviewerHandoffApplyPackage,
    PaperUnderstandingGoldReviewerHandoffApplyRequest,
    PaperUnderstandingGoldReviewerHandoffPackage,
    PaperUnderstandingGoldReviewerHandoffReleasePrepPackage,
    PaperUnderstandingGoldReviewerHandoffReleasePrepRequest,
    PaperUnderstandingGoldReviewerHandoffStagePackage,
    PaperUnderstandingGoldReviewerHandoffStageRequest,
)
from src.services.paper_understanding_gold_drafts import (
    apply_paper_understanding_gold_reviewer_handoff_package,
    build_paper_understanding_gold_candidate_drafts_from_reviewed_fixtures,
    build_paper_understanding_gold_candidate_draft_curation_report,
    build_paper_understanding_gold_candidate_draft_curation_progress_report,
    build_paper_understanding_gold_candidate_drafts_from_teacher_verification,
    build_paper_understanding_gold_candidate_draft_patch_template,
    build_paper_understanding_gold_curation_task_export_report,
    build_paper_understanding_gold_reviewer_handoff_release_prep_package,
    patch_paper_understanding_gold_candidate_draft,
    stage_paper_understanding_gold_reviewer_handoff_apply_package,
    stage_paper_understanding_gold_from_candidate_drafts,
    write_paper_understanding_gold_candidate_drafts,
    write_paper_understanding_gold_candidate_drafts_from_teacher_verification,
    write_paper_understanding_gold_candidate_draft_patch_result_manifest,
    write_paper_understanding_gold_candidate_draft_patch_template_manifest,
    write_paper_understanding_gold_reviewer_handoff_package,
    write_paper_understanding_gold_teacher_verification_curation_package,
    stage_paper_understanding_gold_from_patch_results,
)
from src.services.paper_understanding_gold_validation import (
    assess_paper_understanding_gold_readiness,
    build_paper_understanding_gold_curation_report,
    build_paper_understanding_gold_manifest,
    build_paper_understanding_gold_release_package_from_split_plan,
    build_paper_understanding_gold_release_package_from_staged_gold,
    build_paper_understanding_gold_release_readiness_report,
    build_paper_understanding_gold_release_split_plan_from_staging_manifest,
)


def _gold_payload() -> dict:
    return {
        "paper_id": "zotero:example2026",
        "citation": {
            "doi": "10.1000/example",
            "title": "Example evidence grounding paper",
            "authors": ["A. Researcher", "B. Reviewer"],
            "year": 2026,
        },
        "paper_type": "primary_research",
        "domain_tags": ["biomarker", "diagnostics"],
        "important_figures": [
            {
                "figure_id": "fig1",
                "label": "Figure 1",
                "page": 4,
                "caption": "Main diagnostic performance plot.",
            }
        ],
        "important_tables": [
            {
                "table_id": "tbl1",
                "label": "Table 1",
                "page": 5,
                "caption": "Cohort characteristics.",
            }
        ],
        "gold_claims": [
            {
                "statement_id": "claim-001",
                "kind": "claim",
                "text": "The biomarker separated cases from controls.",
                "review_failure_codes": ["OVERSTATED_RESULT", "OVERSTATED_RESULT"],
                "evidence_refs": [
                    {
                        "page": 4,
                        "chunk_id": "p04_c01",
                        "char_start": 20,
                        "char_end": 80,
                        "quote": "The biomarker separated cases from controls.",
                        "section": "Results",
                        "figure_id": "fig1",
                    }
                ],
            }
        ],
        "gold_methods": [
            {
                "statement_id": "method-001",
                "kind": "method",
                "text": "Cases and controls were measured with the same assay.",
                "evidence_refs": [
                    {
                        "page": 3,
                        "chunk_id": "p03_c02",
                        "quote": "Cases and controls were measured with the same assay.",
                        "section": "Methods",
                    }
                ],
            }
        ],
        "gold_results": [
            {
                "statement_id": "result-001",
                "kind": "result",
                "text": "Table 1 reports the cohort sizes.",
                "evidence_refs": [
                    {
                        "page": 5,
                        "quote": "Table 1 reports cohort sizes.",
                        "table_id": "tbl1",
                        "cell_id": "tbl1:r1:c2",
                    }
                ],
            }
        ],
        "gold_limitations": [
            {
                "statement_id": "limitation-001",
                "kind": "limitation",
                "text": "The cohort was single-center.",
                "evidence_refs": [
                    {
                        "page": 7,
                        "quote": "This single-center cohort limits generalizability.",
                        "section": "Discussion",
                    }
                ],
            }
        ],
        "gold_gaps": [
            {
                "statement_id": "gap-001",
                "kind": "gap",
                "text": "External validation remains needed.",
                "evidence_refs": [
                    {
                        "page": 7,
                        "quote": "External validation remains needed.",
                        "section": "Discussion",
                    }
                ],
            }
        ],
    }


def _readiness_pass_payload() -> dict:
    payload = _gold_payload()
    for index in range(2, 4):
        claim = dict(payload["gold_claims"][0])
        claim["statement_id"] = f"claim-00{index}"
        claim["text"] = f"Additional grounded claim {index}."
        payload["gold_claims"].append(claim)
    return payload


def _ready_gold_payload_for(
    *,
    paper_id: str,
    domain_tags: list[str],
    paper_type: str = "primary_research",
) -> dict:
    payload = _readiness_pass_payload()
    payload["paper_id"] = paper_id
    payload["citation"] = {
        **payload["citation"],
        "doi": f"10.1000/{paper_id}",
        "title": f"Ready gold {paper_id}",
    }
    payload["domain_tags"] = domain_tags
    payload["paper_type"] = paper_type
    return payload


def _write_ready_gold_manifest(
    tmp_path: Path,
    *,
    split: str,
    paper_ids: list[str],
    goldset_id: str = "paper-understanding-pilot-2026-05-22",
) -> Path:
    gold_dir = tmp_path / "gold" / split
    manifest_dir = tmp_path / "manifests"
    gold_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    gold_paths: list[Path] = []
    for paper_id in paper_ids:
        gold_path = gold_dir / f"{paper_id}.json"
        gold_path.write_text(
            json.dumps(_ready_gold_payload_for(paper_id=paper_id, domain_tags=["biomarker"])),
            encoding="utf-8",
        )
        gold_paths.append(gold_path)
    manifest_path = manifest_dir / f"{split}.json"
    manifest = build_paper_understanding_gold_manifest(
        gold_paths,
        goldset_id=goldset_id,
        goldset_split=split,
        manifest_path=manifest_path,
        require_ready=True,
    )
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest_path


def _write_ready_staging_manifest(tmp_path: Path, *, split: str, paper_id: str) -> Path:
    draft_dir = tmp_path / "drafts" / split
    stage_dir = tmp_path / "staged" / split
    draft_dir.mkdir(parents=True, exist_ok=True)
    ready_gold = PaperUnderstandingGold.model_validate(
        _ready_gold_payload_for(paper_id=paper_id, domain_tags=["biomarker"])
    )
    readiness = assess_paper_understanding_gold_readiness(ready_gold)
    draft_path = draft_dir / f"{paper_id}.candidate_draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_candidate_draft.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_kind": "claim_evidence_reviewed_eval_fixtures",
                "source_reviewed_dir": str(tmp_path / "reviewed"),
                "paper_id": ready_gold.paper_id,
                "fixture_count": 3,
                "readiness": readiness.model_dump(mode="json"),
                "draft": ready_gold.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )
    stage_paper_understanding_gold_from_candidate_drafts(
        draft_paths=[draft_path],
        out_dir=stage_dir,
    )
    return stage_dir / "staging_manifest.json"


def _write_ready_combined_staging_manifest(tmp_path: Path, *, paper_ids: list[str]) -> Path:
    stage_dir = tmp_path / "staged" / "combined"
    stage_dir.mkdir(parents=True, exist_ok=True)
    staged_paths: list[str] = []
    for paper_id in paper_ids:
        gold_path = stage_dir / f"{paper_id}.json"
        gold_path.write_text(
            json.dumps(_ready_gold_payload_for(paper_id=paper_id, domain_tags=["biomarker"])),
            encoding="utf-8",
        )
        staged_paths.append(str(gold_path))
    staging_manifest = {
        "schema_version": "paper_understanding_gold_staging_manifest.v1",
        "layer": "review_gate_artifact",
        "canonical_status": "non_canonical",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_draft_paths": [],
        "out_dir": str(stage_dir),
        "require_ready": True,
        "staged_count": len(staged_paths),
        "staged_paths": staged_paths,
        "readiness_summary": {
            "pass_count": len(staged_paths),
            "warn_count": 0,
            "fail_count": 0,
        },
    }
    path = stage_dir / "staging_manifest.json"
    path.write_text(json.dumps(staging_manifest), encoding="utf-8")
    return path


def _candidate_draft_ready_patch_payload(*, draft_path: Path, paper_id: str, out: Path | None = None) -> dict:
    ready = _ready_gold_payload_for(paper_id=paper_id, domain_tags=["biomarker"], paper_type="review")
    payload: dict = {
        "draft_path": str(draft_path),
        "reviewer_id": "curator-1",
        "review_notes": "Filled fixed-gold readiness fields from human curation.",
        "citation": ready["citation"],
        "paper_type": ready["paper_type"],
        "domain_tags": ready["domain_tags"],
        "gold_claims": ready["gold_claims"],
        "gold_methods": ready["gold_methods"],
        "gold_results": ready["gold_results"],
        "gold_limitations": ready["gold_limitations"],
        "gold_gaps": ready["gold_gaps"],
        "important_figures": ready["important_figures"],
        "important_tables": ready["important_tables"],
        "notes": "Curated candidate draft ready for staging review.",
    }
    if out is not None:
        payload["out"] = str(out)
    return payload


def _reviewed_fixture_payload(*, paper_id: str = "paper-1", claim_id: str = "claim-1") -> dict:
    fixture = ClaimEvidenceCorrectionReviewedEvalFixture(
        source_decision_id=f"decision-{claim_id}",
        intake_id=f"intake-{claim_id}",
        reviewed_at=datetime.now(timezone.utc),
        reviewer_id="reviewer-1",
        review_notes="claim/evidence verified for draft",
        source_candidate=ClaimEvidenceCorrectionEvalCandidate(
            source_correction_id=f"correction-{claim_id}",
            source_feedback_id="feedback-1",
            paper_id=paper_id,
            run_id="run-1",
            claim_id=claim_id,
            field_path="claims[0]",
            before_claim_text="The paper proves broad benefit.",
            after_claim_text="The intervention improved survival in the study cohort.",
            before_evidence_refs=[],
            after_evidence_refs=[
                ClaimEvidenceCorrectionLocator(
                    page=2,
                    chunk_id="chunk-results",
                    quote="The intervention improved survival in the study cohort.",
                    section="Results",
                )
            ],
            reason_codes=["OVERSTATED_RESULT"],
            reviewer_id="reviewer-1",
            feedback_export_status="linked",
        ),
    )
    return fixture.model_dump(mode="json")


def _teacher_verification_payload(*, accepted: bool = True) -> dict:
    return {
        "schema_version": "teacher_verification.v1",
        "paper_id": "zotero:hanssonBloodBiomarkersAlzheimers2023",
        "accepted": accepted,
        "teacher_output": {
            "doc_id": "file:Hansson - Blood biomarkers for Alzheimer disease.pdf",
            "claims": [
                {
                    "claim_id": "CLM-001",
                    "type": "finding",
                    "statement": "Blood biomarkers can support Alzheimer disease diagnosis in clinical settings.",
                    "evidence_spans": [
                        {
                            "page": 2,
                            "chunk_id": "chunk-001",
                            "char_start": 12,
                            "char_end": 92,
                            "quote": "Blood biomarkers can support Alzheimer disease diagnosis in clinical settings.",
                            "section": "Abstract",
                            "rationale": "The sentence states the diagnostic support claim directly.",
                        }
                    ],
                },
                {
                    "claim_id": "CLM-002",
                    "type": "result",
                    "statement": "The review reports multiple blood biomarker use cases.",
                    "evidence_spans": [
                        {
                            "page": 4,
                            "chunk_id": "chunk-004",
                            "quote": "Multiple blood biomarker use cases are discussed.",
                            "section": "Results",
                            "table_id": "tbl-use-cases",
                        }
                    ],
                },
            ],
        },
    }


def _write_ready_reviewer_handoff_package(
    tmp_path: Path,
) -> tuple[Path, Path, PaperUnderstandingGoldReviewerHandoffPackage]:
    teacher_dir = tmp_path / "teacher"
    handoff_dir = tmp_path / "reviewer_handoff"
    package_out = tmp_path / "reviewer_handoff.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    package = write_paper_understanding_gold_reviewer_handoff_package(
        paths=[teacher_dir],
        out_dir=handoff_dir,
        reviewer_id="curator-1",
        package_out=package_out,
    )
    template_path = Path(package.patch_template_manifest.template_paths[0])
    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    template_payload["patch_request"] = _candidate_draft_ready_patch_payload(
        draft_path=Path(package.curation_package.draft_manifest.draft_paths[0]),
        paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
        out=handoff_dir / "patched_drafts" / "ready.candidate_draft.json",
    )
    template_path.write_text(json.dumps(template_payload), encoding="utf-8")
    return package_out, handoff_dir, package


def _write_ready_reviewer_handoff_apply_package(
    tmp_path: Path,
) -> tuple[Path, Path]:
    package_out, _handoff_dir, _package = _write_ready_reviewer_handoff_package(tmp_path)
    apply_dir = tmp_path / "handoff_apply"
    apply_out = tmp_path / "handoff_apply.json"
    apply_paper_understanding_gold_reviewer_handoff_package(
        PaperUnderstandingGoldReviewerHandoffApplyRequest(
            reviewer_handoff_package_path=str(package_out),
            out_dir=str(apply_dir),
            out=str(apply_out),
        )
    )
    return apply_out, apply_dir


def _write_ready_reviewer_handoff_stage_package(
    tmp_path: Path,
) -> tuple[Path, Path]:
    apply_out, _apply_dir = _write_ready_reviewer_handoff_apply_package(tmp_path)
    stage_dir = tmp_path / "handoff_stage"
    stage_out = tmp_path / "handoff_stage.json"
    stage_paper_understanding_gold_reviewer_handoff_apply_package(
        PaperUnderstandingGoldReviewerHandoffStageRequest(
            reviewer_handoff_apply_package_path=str(apply_out),
            out_dir=str(stage_dir),
            out=str(stage_out),
        )
    )
    return stage_out, stage_dir


def test_paper_understanding_gold_accepts_claim_method_result_limitation_gap_contract():
    gold = PaperUnderstandingGold.model_validate(_gold_payload())

    assert gold.schema_version == "paper_understanding_gold.v1"
    assert gold.paper_id == "zotero:example2026"
    assert gold.citation.doi == "10.1000/example"
    assert len(list(gold.iter_statements())) == 5
    assert gold.gold_claims[0].evidence_refs[0].figure_id == "fig1"
    assert gold.gold_claims[0].review_failure_codes == ["OVERSTATED_RESULT"]
    assert gold.gold_results[0].evidence_refs[0].table_id == "tbl1"


def test_paper_understanding_gold_rejects_claim_without_evidence():
    payload = _gold_payload()
    payload["gold_claims"][0]["evidence_refs"] = []

    with pytest.raises(ValidationError, match="at least 1 item"):
        PaperUnderstandingGold.model_validate(payload)


def test_paper_understanding_gold_rejects_wrong_statement_kind():
    payload = _gold_payload()
    payload["gold_methods"][0]["kind"] = "result"

    with pytest.raises(ValidationError, match="gold_methods entries must use kind=method"):
        PaperUnderstandingGold.model_validate(payload)


def test_paper_understanding_gold_rejects_undeclared_figure_and_table_refs():
    payload = _gold_payload()
    payload["gold_claims"][0]["evidence_refs"][0]["figure_id"] = "fig-missing"

    with pytest.raises(ValidationError, match="undeclared figure_id=fig-missing"):
        PaperUnderstandingGold.model_validate(payload)

    payload = _gold_payload()
    payload["gold_results"][0]["evidence_refs"][0]["table_id"] = "tbl-missing"

    with pytest.raises(ValidationError, match="undeclared table_id=tbl-missing"):
        PaperUnderstandingGold.model_validate(payload)


def test_validate_paper_understanding_gold_paths_reports_invalid_files(tmp_path: Path):
    valid_path = tmp_path / "valid.json"
    invalid_path = tmp_path / "invalid.json"
    valid_path.write_text(json.dumps(_gold_payload()), encoding="utf-8")
    invalid = _gold_payload()
    invalid["gold_claims"][0]["evidence_refs"] = []
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")

    summary = validate_gold_paths([tmp_path])

    assert summary["checked_count"] == 2
    assert summary["valid_count"] == 1
    assert summary["invalid_count"] == 1
    assert summary["valid"][0]["paper_id"] == "zotero:example2026"
    assert summary["valid"][0]["claim_count"] == 1
    assert summary["valid"][0]["readiness_status"] == "warn"
    assert summary["valid"][0]["readiness_reason_codes"] == ["CLAIM_COUNT_OUT_OF_RANGE"]
    assert summary["readiness"]["warn_count"] == 1
    assert "invalid.json" in summary["invalid"][0]["path"]


def test_paper_understanding_gold_readiness_passes_complete_curated_record():
    payload = _readiness_pass_payload()
    gold = PaperUnderstandingGold.model_validate(payload)

    readiness = assess_paper_understanding_gold_readiness(gold)

    assert readiness.schema_version == "paper_understanding_gold_readiness.v1"
    assert readiness.status == "pass"
    assert readiness.reason_codes == []


def test_validate_paper_understanding_gold_paths_require_ready_rejects_schema_valid_warning(tmp_path: Path):
    gold_path = tmp_path / "valid_but_warn.json"
    gold_path.write_text(json.dumps(_gold_payload()), encoding="utf-8")

    summary = validate_gold_paths([gold_path], require_ready=True)

    assert summary["require_ready"] is True
    assert summary["valid_count"] == 0
    assert summary["invalid_count"] == 1
    assert "gold readiness not pass: status=warn reason_codes=CLAIM_COUNT_OUT_OF_RANGE" in summary["invalid"][0][
        "error"
    ]
    assert summary["readiness"]["pass_count"] == 0


def test_paper_understanding_gold_readiness_fails_missing_context_fields():
    payload = _gold_payload()
    payload["gold_methods"] = []
    payload["gold_results"] = []
    payload["gold_limitations"] = []
    payload["domain_tags"] = []
    payload["important_figures"] = []
    payload["important_tables"] = []
    payload["gold_claims"][0]["evidence_refs"][0].pop("figure_id")
    payload["citation"].pop("doi")
    gold = PaperUnderstandingGold.model_validate(payload)

    readiness = assess_paper_understanding_gold_readiness(gold)

    assert readiness.status == "fail"
    assert readiness.reason_codes == [
        "CLAIM_COUNT_OUT_OF_RANGE",
        "METHOD_MISSING",
        "RESULT_MISSING",
        "LIMITATION_MISSING",
        "DOMAIN_TAGS_MISSING",
        "IMPORTANT_VISUALS_MISSING",
        "EXTERNAL_ID_MISSING",
    ]


def test_paper_understanding_gold_manifest_accepts_fixed_split_contract():
    manifest = PaperUnderstandingGoldManifest.model_validate(
        {
            "goldset_id": "paper-understanding-pilot-2026-05-22",
            "goldset_split": "eval",
            "items": [
                {
                    "paper_id": "zotero:example2026",
                    "gold_path": "../gold/example.json",
                    "paper_type": "primary_research",
                    "domain_tags": ["biomarker", "biomarker"],
                }
            ],
        }
    )

    assert manifest.schema_version == "paper_understanding_gold_manifest.v1"
    assert manifest.goldset_id == "paper-understanding-pilot-2026-05-22"
    assert manifest.goldset_split == "eval"
    assert manifest.items[0].domain_tags == ["biomarker"]


def test_paper_understanding_gold_manifest_rejects_duplicate_paper_ids():
    with pytest.raises(ValidationError, match="manifest paper_id contains duplicate id=zotero:example2026"):
        PaperUnderstandingGoldManifest.model_validate(
            {
                "goldset_id": "paper-understanding-pilot-2026-05-22",
                "goldset_split": "eval",
                "items": [
                    {"paper_id": "zotero:example2026", "gold_path": "../gold/example-a.json"},
                    {"paper_id": "zotero:example2026", "gold_path": "../gold/example-b.json"},
                ],
            }
        )


def test_validate_paper_understanding_gold_manifest_validates_relative_gold_paths(tmp_path: Path):
    gold_dir = tmp_path / "gold"
    manifest_dir = tmp_path / "manifests"
    gold_dir.mkdir()
    manifest_dir.mkdir()
    gold_path = gold_dir / "example.json"
    manifest_path = manifest_dir / "paper_understanding_pilot.json"
    gold_path.write_text(json.dumps(_gold_payload()), encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_manifest.v1",
                "goldset_id": "paper-understanding-pilot-2026-05-22",
                "goldset_split": "eval",
                "items": [{"paper_id": "zotero:example2026", "gold_path": "../gold/example.json"}],
            }
        ),
        encoding="utf-8",
    )

    summary = validate_gold_paths([manifest_path])

    assert summary["checked_count"] == 1
    assert summary["checked_gold_count"] == 1
    assert summary["manifest_count"] == 1
    assert summary["valid_count"] == 1
    assert summary["invalid_count"] == 0
    assert summary["manifests"][0]["goldset_id"] == "paper-understanding-pilot-2026-05-22"
    assert summary["valid"][0]["paper_id"] == "zotero:example2026"
    assert summary["valid"][0]["goldset_split"] == "eval"
    assert summary["valid"][0]["manifest_path"] == str(manifest_path)


def test_validate_paper_understanding_gold_manifest_rejects_paper_id_mismatch(tmp_path: Path):
    gold_dir = tmp_path / "gold"
    manifest_dir = tmp_path / "manifests"
    gold_dir.mkdir()
    manifest_dir.mkdir()
    gold_path = gold_dir / "example.json"
    manifest_path = manifest_dir / "paper_understanding_pilot.json"
    gold_path.write_text(json.dumps(_gold_payload()), encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_manifest.v1",
                "goldset_id": "paper-understanding-pilot-2026-05-22",
                "goldset_split": "eval",
                "items": [{"paper_id": "zotero:other2026", "gold_path": "../gold/example.json"}],
            }
        ),
        encoding="utf-8",
    )

    summary = validate_gold_paths([manifest_path])

    assert summary["valid_count"] == 0
    assert summary["invalid_count"] == 1
    assert "manifest paper_id=zotero:other2026 does not match gold paper_id=zotero:example2026" in summary[
        "invalid"
    ][0]["error"]


def test_build_paper_understanding_gold_manifest_from_valid_records(tmp_path: Path):
    gold_dir = tmp_path / "gold"
    manifest_path = tmp_path / "manifests" / "paper_understanding_eval.json"
    gold_dir.mkdir()
    manifest_path.parent.mkdir()
    gold_path = gold_dir / "example.json"
    gold_path.write_text(json.dumps(_gold_payload()), encoding="utf-8")

    manifest = build_paper_understanding_gold_manifest(
        [gold_dir],
        goldset_id="paper-understanding-pilot-2026-05-22",
        goldset_split="eval",
        manifest_path=manifest_path,
    )

    assert manifest.goldset_id == "paper-understanding-pilot-2026-05-22"
    assert manifest.goldset_split == "eval"
    assert len(manifest.items) == 1
    assert manifest.items[0].paper_id == "zotero:example2026"
    assert manifest.items[0].gold_path == "../gold/example.json"
    assert manifest.items[0].paper_type == "primary_research"
    assert manifest.items[0].domain_tags == ["biomarker", "diagnostics"]
    assert manifest.items[0].metadata["claim_count"] == 1
    assert manifest.items[0].metadata["readiness_status"] == "warn"
    assert manifest.items[0].metadata["readiness_reason_codes"] == ["CLAIM_COUNT_OUT_OF_RANGE"]
    assert manifest.notes


def test_build_paper_understanding_gold_manifest_rejects_invalid_records(tmp_path: Path):
    invalid_path = tmp_path / "invalid.json"
    invalid = _gold_payload()
    invalid["gold_claims"][0]["evidence_refs"] = []
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")

    with pytest.raises(ValueError, match="cannot build paper understanding gold manifest from invalid inputs"):
        build_paper_understanding_gold_manifest(
            [invalid_path],
            goldset_id="paper-understanding-pilot-2026-05-22",
            goldset_split="eval",
            manifest_path=tmp_path / "manifest.json",
        )


def test_build_paper_understanding_gold_manifest_require_ready_rejects_warning_records(tmp_path: Path):
    gold_path = tmp_path / "warn.json"
    gold_path.write_text(json.dumps(_gold_payload()), encoding="utf-8")

    with pytest.raises(ValueError, match="gold readiness not pass: status=warn"):
        build_paper_understanding_gold_manifest(
            [gold_path],
            goldset_id="paper-understanding-pilot-2026-05-22",
            goldset_split="eval",
            manifest_path=tmp_path / "manifest.json",
            require_ready=True,
        )


def test_build_paper_understanding_gold_manifest_cli_writes_valid_manifest(tmp_path: Path):
    gold_dir = tmp_path / "gold"
    manifest_path = tmp_path / "manifests" / "paper_understanding_eval.json"
    gold_dir.mkdir()
    manifest_path.parent.mkdir()
    (gold_dir / "example.json").write_text(json.dumps(_gold_payload()), encoding="utf-8")

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/build_paper_understanding_gold_manifest.py",
            str(gold_dir),
            "--goldset-id",
            "paper-understanding-pilot-2026-05-22",
            "--goldset-split",
            "eval",
            "--out",
            str(manifest_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_manifest.v1"
    assert payload["items"][0]["gold_path"] == "../gold/example.json"
    assert "invalid_count=0" in result.stdout


def test_build_paper_understanding_gold_manifest_cli_require_ready_rejects_warning_record(tmp_path: Path):
    gold_dir = tmp_path / "gold"
    manifest_path = tmp_path / "manifests" / "paper_understanding_eval.json"
    gold_dir.mkdir()
    manifest_path.parent.mkdir()
    (gold_dir / "example.json").write_text(json.dumps(_gold_payload()), encoding="utf-8")

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/build_paper_understanding_gold_manifest.py",
            str(gold_dir),
            "--goldset-id",
            "paper-understanding-pilot-2026-05-22",
            "--goldset-split",
            "eval",
            "--out",
            str(manifest_path),
            "--require-ready",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert not manifest_path.exists()
    assert "gold readiness not pass: status=warn" in result.stderr


def test_validate_paper_understanding_gold_api_writes_validation_summary(tmp_path: Path):
    gold_dir = tmp_path / "gold"
    out = tmp_path / "validation" / "summary.json"
    gold_dir.mkdir()
    (gold_dir / "ready.json").write_text(json.dumps(_readiness_pass_payload()), encoding="utf-8")
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/validate",
        json={
            "paths": [str(gold_dir)],
            "require_ready": True,
            "out": str(out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_validation.v1"
    assert payload["require_ready"] is True
    assert payload["valid_count"] == 1
    assert payload["invalid_count"] == 0
    assert payload["readiness"]["pass_count"] == 1
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["valid"][0]["paper_id"] == "zotero:example2026"


def test_build_paper_understanding_gold_manifest_api_writes_valid_manifest(tmp_path: Path):
    gold_dir = tmp_path / "gold"
    manifest_path = tmp_path / "manifests" / "paper_understanding_eval.json"
    gold_dir.mkdir()
    (gold_dir / "ready.json").write_text(json.dumps(_readiness_pass_payload()), encoding="utf-8")
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/manifests/build",
        json={
            "paths": [str(gold_dir)],
            "goldset_id": "paper-understanding-pilot-2026-05-22",
            "goldset_split": "eval",
            "out": str(manifest_path),
            "require_ready": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_manifest.v1"
    assert payload["goldset_id"] == "paper-understanding-pilot-2026-05-22"
    assert payload["goldset_split"] == "eval"
    assert payload["items"][0]["paper_id"] == "zotero:example2026"
    assert payload["items"][0]["gold_path"] == "../gold/ready.json"
    assert payload["items"][0]["metadata"]["readiness_status"] == "pass"
    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written["items"][0]["gold_path"] == "../gold/ready.json"
    summary = validate_gold_paths([manifest_path], require_ready=True)
    assert summary["invalid_count"] == 0


def test_build_paper_understanding_gold_manifest_from_staging_manifest(tmp_path: Path):
    draft_dir = tmp_path / "drafts"
    stage_dir = tmp_path / "staged"
    manifest_path = tmp_path / "manifests" / "paper_understanding_eval.json"
    draft_dir.mkdir()
    manifest_path.parent.mkdir()
    ready_gold = PaperUnderstandingGold.model_validate(_readiness_pass_payload())
    readiness = assess_paper_understanding_gold_readiness(ready_gold)
    draft_path = draft_dir / "ready.candidate_draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_candidate_draft.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_kind": "claim_evidence_reviewed_eval_fixtures",
                "source_reviewed_dir": str(tmp_path / "reviewed"),
                "paper_id": ready_gold.paper_id,
                "fixture_count": 3,
                "readiness": readiness.model_dump(mode="json"),
                "draft": ready_gold.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )
    staging_manifest = stage_paper_understanding_gold_from_candidate_drafts(
        draft_paths=[draft_path],
        out_dir=stage_dir,
    )
    staging_manifest_path = stage_dir / "staging_manifest.json"

    validation = validate_gold_paths([staging_manifest_path], require_ready=True)
    manifest = build_paper_understanding_gold_manifest(
        [staging_manifest_path],
        goldset_id="paper-understanding-pilot-2026-05-22",
        goldset_split="eval",
        manifest_path=manifest_path,
        require_ready=True,
    )

    assert validation["valid_count"] == 1
    assert validation["invalid_count"] == 0
    assert manifest.items[0].paper_id == ready_gold.paper_id
    assert manifest.items[0].gold_path == f"../staged/{Path(staging_manifest.staged_paths[0]).name}"
    assert manifest.items[0].metadata["readiness_status"] == "pass"


def test_build_paper_understanding_gold_manifest_cli_accepts_staging_manifest(tmp_path: Path):
    draft_dir = tmp_path / "drafts"
    stage_dir = tmp_path / "staged"
    manifest_path = tmp_path / "manifests" / "paper_understanding_eval.json"
    draft_dir.mkdir()
    manifest_path.parent.mkdir()
    ready_gold = PaperUnderstandingGold.model_validate(_readiness_pass_payload())
    readiness = assess_paper_understanding_gold_readiness(ready_gold)
    draft_path = draft_dir / "ready.candidate_draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_candidate_draft.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_kind": "claim_evidence_reviewed_eval_fixtures",
                "source_reviewed_dir": str(tmp_path / "reviewed"),
                "paper_id": ready_gold.paper_id,
                "fixture_count": 3,
                "readiness": readiness.model_dump(mode="json"),
                "draft": ready_gold.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )
    stage_paper_understanding_gold_from_candidate_drafts(
        draft_paths=[draft_path],
        out_dir=stage_dir,
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/build_paper_understanding_gold_manifest.py",
            str(stage_dir / "staging_manifest.json"),
            "--goldset-id",
            "paper-understanding-pilot-2026-05-22",
            "--goldset-split",
            "eval",
            "--out",
            str(manifest_path),
            "--require-ready",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_manifest.v1"
    assert payload["items"][0]["paper_id"] == ready_gold.paper_id
    assert "invalid_count=0" in result.stdout


def test_build_paper_understanding_gold_manifest_api_accepts_staging_manifest(tmp_path: Path):
    draft_dir = tmp_path / "drafts"
    stage_dir = tmp_path / "staged"
    manifest_path = tmp_path / "manifests" / "paper_understanding_eval.json"
    draft_dir.mkdir()
    ready_gold = PaperUnderstandingGold.model_validate(_readiness_pass_payload())
    readiness = assess_paper_understanding_gold_readiness(ready_gold)
    draft_path = draft_dir / "ready.candidate_draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_candidate_draft.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_kind": "claim_evidence_reviewed_eval_fixtures",
                "source_reviewed_dir": str(tmp_path / "reviewed"),
                "paper_id": ready_gold.paper_id,
                "fixture_count": 3,
                "readiness": readiness.model_dump(mode="json"),
                "draft": ready_gold.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )
    stage_paper_understanding_gold_from_candidate_drafts(
        draft_paths=[draft_path],
        out_dir=stage_dir,
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/manifests/build",
        json={
            "paths": [str(stage_dir / "staging_manifest.json")],
            "goldset_id": "paper-understanding-pilot-2026-05-22",
            "goldset_split": "eval",
            "out": str(manifest_path),
            "require_ready": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_manifest.v1"
    assert payload["items"][0]["paper_id"] == ready_gold.paper_id
    assert payload["items"][0]["metadata"]["readiness_status"] == "pass"


def test_build_paper_understanding_gold_curation_report_checks_split_domain_targets(tmp_path: Path):
    gold_dir = tmp_path / "gold"
    manifest_dir = tmp_path / "manifests"
    gold_dir.mkdir()
    manifest_dir.mkdir()
    (gold_dir / "biomarker.json").write_text(
        json.dumps(_ready_gold_payload_for(paper_id="paper-biomarker", domain_tags=["biomarker"])),
        encoding="utf-8",
    )
    (gold_dir / "oncology.json").write_text(
        json.dumps(_ready_gold_payload_for(paper_id="paper-oncology", domain_tags=["oncology"])),
        encoding="utf-8",
    )
    manifest_path = manifest_dir / "paper_understanding_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_manifest.v1",
                "goldset_id": "paper-understanding-pilot-2026-05-22",
                "goldset_split": "eval",
                "items": [
                    {"paper_id": "paper-biomarker", "gold_path": "../gold/biomarker.json"},
                    {"paper_id": "paper-oncology", "gold_path": "../gold/oncology.json"},
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_paper_understanding_gold_curation_report(
        [manifest_path],
        targets=[
            PaperUnderstandingGoldCurationTarget(
                goldset_split="eval",
                domain_tag="biomarker",
                min_ready_count=1,
            ),
            PaperUnderstandingGoldCurationTarget(
                goldset_split="holdout",
                domain_tag="biomarker",
                min_ready_count=1,
            ),
        ],
    )

    assert report.schema_version == "paper_understanding_gold_curation_report.v1"
    assert report.canonical_status == "non_canonical"
    assert report.manifest_count == 1
    assert report.paper_count == 2
    assert report.ready_paper_count == 2
    assert report.curation_ready is False
    assert [result.status for result in report.target_results] == ["pass", "fail"]
    assert report.target_results[0].matching_paper_ids == ["paper-biomarker"]
    assert report.target_results[1].missing_ready_count == 1
    assert "curation_targets_not_met" in report.warnings
    buckets = {
        (bucket.goldset_split, bucket.domain_tag, bucket.paper_type): bucket
        for bucket in report.buckets
    }
    assert buckets[("eval", "biomarker", None)].ready_count == 1
    assert buckets[("eval", None, "primary_research")].ready_count == 2


def test_audit_paper_understanding_goldset_curation_cli_exits_nonzero_on_target_gap(tmp_path: Path):
    gold_dir = tmp_path / "gold"
    manifest_dir = tmp_path / "manifests"
    out = tmp_path / "curation_report.json"
    gold_dir.mkdir()
    manifest_dir.mkdir()
    (gold_dir / "biomarker.json").write_text(
        json.dumps(_ready_gold_payload_for(paper_id="paper-biomarker", domain_tags=["biomarker"])),
        encoding="utf-8",
    )
    manifest_path = manifest_dir / "paper_understanding_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_manifest.v1",
                "goldset_id": "paper-understanding-pilot-2026-05-22",
                "goldset_split": "eval",
                "items": [{"paper_id": "paper-biomarker", "gold_path": "../gold/biomarker.json"}],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/audit_paper_understanding_goldset_curation.py",
            str(manifest_path),
            "--out",
            str(out),
            "--target",
            "split=eval,domain=biomarker,min=2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_curation_report.v1"
    assert payload["curation_ready"] is False
    assert payload["target_results"][0]["missing_ready_count"] == 1
    assert "[paper_understanding_gold_curation] curation_ready=False" in result.stdout


def test_paper_understanding_gold_curation_audit_api_returns_noncanonical_report(tmp_path: Path):
    gold_dir = tmp_path / "gold"
    manifest_dir = tmp_path / "manifests"
    out = tmp_path / "curation_report.json"
    gold_dir.mkdir()
    manifest_dir.mkdir()
    (gold_dir / "biomarker.json").write_text(
        json.dumps(_ready_gold_payload_for(paper_id="paper-biomarker", domain_tags=["biomarker"])),
        encoding="utf-8",
    )
    manifest_path = manifest_dir / "paper_understanding_eval.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_manifest.v1",
                "goldset_id": "paper-understanding-pilot-2026-05-22",
                "goldset_split": "eval",
                "items": [{"paper_id": "paper-biomarker", "gold_path": "../gold/biomarker.json"}],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/curation/audit",
        json={
            "paths": [str(manifest_path)],
            "out": str(out),
            "targets": [
                {
                    "goldset_split": "eval",
                    "domain_tag": "biomarker",
                    "min_ready_count": 1,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_curation_report.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["curation_ready"] is True
    assert payload["target_results"][0]["matching_paper_ids"] == ["paper-biomarker"]
    assert out.exists()


def test_build_paper_understanding_gold_release_readiness_report_requires_seed_eval_holdout(tmp_path: Path):
    seed_manifest = _write_ready_gold_manifest(tmp_path, split="seed", paper_ids=["paper-seed"])
    eval_manifest = _write_ready_gold_manifest(tmp_path, split="eval", paper_ids=["paper-eval"])
    out = tmp_path / "release_readiness.json"

    report = build_paper_understanding_gold_release_readiness_report(
        [seed_manifest, eval_manifest],
        out=out,
    )

    assert out.exists()
    assert report.schema_version == "paper_understanding_gold_release_readiness.v1"
    assert report.layer == "review_gate_artifact"
    assert report.canonical_status == "non_canonical"
    assert report.release_ready is False
    assert report.required_splits == ["seed", "eval", "holdout"]
    assert report.missing_splits == ["holdout"]
    assert "required_splits_missing" in report.blockers
    assert "gold_release_readiness_blocked" in report.warnings


def test_build_paper_understanding_gold_release_readiness_report_can_pass_complete_release(tmp_path: Path):
    manifests = [
        _write_ready_gold_manifest(tmp_path, split="seed", paper_ids=["paper-seed"]),
        _write_ready_gold_manifest(tmp_path, split="eval", paper_ids=["paper-eval"]),
        _write_ready_gold_manifest(tmp_path, split="holdout", paper_ids=["paper-holdout"]),
    ]

    report = build_paper_understanding_gold_release_readiness_report(manifests)

    assert report.release_ready is True
    assert report.blockers == []
    assert report.manifest_count == 3
    assert report.ready_count == 3
    assert [summary.goldset_split for summary in report.split_summaries] == ["seed", "eval", "holdout"]
    assert all(summary.status == "pass" for summary in report.split_summaries)


def test_build_paper_understanding_gold_release_readiness_report_blocks_duplicate_across_splits(tmp_path: Path):
    seed_manifest = _write_ready_gold_manifest(tmp_path, split="seed", paper_ids=["paper-shared"])
    eval_manifest = _write_ready_gold_manifest(tmp_path, split="eval", paper_ids=["paper-shared"])
    holdout_manifest = _write_ready_gold_manifest(tmp_path, split="holdout", paper_ids=["paper-holdout"])

    report = build_paper_understanding_gold_release_readiness_report(
        [seed_manifest, eval_manifest, holdout_manifest],
    )

    assert report.release_ready is False
    assert report.duplicate_paper_ids == ["paper-shared"]
    assert "duplicate_paper_ids_across_splits" in report.blockers


def test_audit_paper_understanding_gold_release_readiness_cli(tmp_path: Path):
    manifests = [
        _write_ready_gold_manifest(tmp_path, split="seed", paper_ids=["paper-seed"]),
        _write_ready_gold_manifest(tmp_path, split="eval", paper_ids=["paper-eval"]),
        _write_ready_gold_manifest(tmp_path, split="holdout", paper_ids=["paper-holdout"]),
    ]
    out = tmp_path / "release_readiness.json"

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/audit_paper_understanding_gold_release_readiness.py",
            *[str(path) for path in manifests],
            "--out",
            str(out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_release_readiness.v1"
    assert payload["release_ready"] is True
    assert "[paper_understanding_gold_release_readiness] release_ready=True" in result.stdout
    PaperUnderstandingGoldReleaseReadinessReport.model_validate(payload)


def test_paper_understanding_gold_release_readiness_api_returns_noncanonical_report(tmp_path: Path):
    manifests = [
        _write_ready_gold_manifest(tmp_path, split="seed", paper_ids=["paper-seed"]),
        _write_ready_gold_manifest(tmp_path, split="eval", paper_ids=["paper-eval"]),
        _write_ready_gold_manifest(tmp_path, split="holdout", paper_ids=["paper-holdout"]),
    ]
    out = tmp_path / "release_readiness.json"
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/release-readiness/audit",
        json={
            "manifest_paths": [str(path) for path in manifests],
            "out": str(out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_release_readiness.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["release_ready"] is True
    assert out.exists()


def test_package_paper_understanding_gold_release_from_staged_gold(tmp_path: Path):
    split_items = []
    for split in ("seed", "eval", "holdout"):
        staging_manifest = _write_ready_staging_manifest(
            tmp_path,
            split=split,
            paper_id=f"paper-{split}",
        )
        split_items.append(
            PaperUnderstandingGoldReleaseManifestBuildItem(
                staging_manifest_path=str(staging_manifest),
                goldset_split=split,
                manifest_out=str(tmp_path / "manifests" / f"{split}.json"),
            )
        )
    release_out = tmp_path / "release_readiness.json"
    package_out = tmp_path / "release_package.json"

    report = build_paper_understanding_gold_release_package_from_staged_gold(
        goldset_id="paper-understanding-pilot-2026-05-22",
        split_manifests=split_items,
        release_readiness_out=release_out,
        package_out=package_out,
    )

    assert package_out.exists()
    assert release_out.exists()
    assert report.schema_version == "paper_understanding_gold_release_package.v1"
    assert report.canonical_status == "non_canonical"
    assert report.release_readiness.release_ready is True
    assert len(report.manifest_paths) == 3
    assert [item.goldset_split for item in report.source_split_manifests] == ["seed", "eval", "holdout"]
    assert [item.manifest_out for item in report.source_split_manifests] == [
        str(tmp_path / "manifests" / "seed.json"),
        str(tmp_path / "manifests" / "eval.json"),
        str(tmp_path / "manifests" / "holdout.json"),
    ]
    for manifest_path in report.manifest_paths:
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        assert payload["schema_version"] == "paper_understanding_gold_manifest.v1"
        assert payload["goldset_id"] == "paper-understanding-pilot-2026-05-22"


def test_package_paper_understanding_gold_release_from_staged_gold_cli(tmp_path: Path):
    split_args = []
    for split in ("seed", "eval", "holdout"):
        staging_manifest = _write_ready_staging_manifest(
            tmp_path,
            split=split,
            paper_id=f"paper-{split}",
        )
        split_args.extend(
            [
                "--split-manifest",
                f"split={split},staging={staging_manifest},out={tmp_path / 'manifests' / f'{split}.json'}",
            ]
        )
    release_out = tmp_path / "release_readiness.json"
    package_out = tmp_path / "release_package.json"

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/package_paper_understanding_gold_release_from_staged_gold.py",
            "--goldset-id",
            "paper-understanding-pilot-2026-05-22",
            *split_args,
            "--release-readiness-out",
            str(release_out),
            "--package-out",
            str(package_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(package_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_release_package.v1"
    assert [item["goldset_split"] for item in payload["source_split_manifests"]] == ["seed", "eval", "holdout"]
    assert payload["release_readiness"]["release_ready"] is True
    assert "[paper_understanding_gold_release_package] release_ready=True" in result.stdout
    PaperUnderstandingGoldReleasePackageReport.model_validate(payload)


def test_package_paper_understanding_gold_release_from_staged_gold_api(tmp_path: Path):
    split_manifests = []
    for split in ("seed", "eval", "holdout"):
        staging_manifest = _write_ready_staging_manifest(
            tmp_path,
            split=split,
            paper_id=f"paper-{split}",
        )
        split_manifests.append(
            {
                "staging_manifest_path": str(staging_manifest),
                "goldset_split": split,
                "manifest_out": str(tmp_path / "manifests" / f"{split}.json"),
            }
        )
    release_out = tmp_path / "release_readiness.json"
    package_out = tmp_path / "release_package.json"
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/release-readiness/package-from-staged-gold",
        json={
            "goldset_id": "paper-understanding-pilot-2026-05-22",
            "split_manifests": split_manifests,
            "release_readiness_out": str(release_out),
            "package_out": str(package_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_release_package.v1"
    assert [item["goldset_split"] for item in payload["source_split_manifests"]] == ["seed", "eval", "holdout"]
    assert payload["release_readiness"]["release_ready"] is True
    assert release_out.exists()
    assert package_out.exists()


def test_build_paper_understanding_gold_release_split_plan_from_staging_manifest(tmp_path: Path):
    staging_manifest = _write_ready_combined_staging_manifest(
        tmp_path,
        paper_ids=["paper-a", "paper-b", "paper-c"],
    )
    out_dir = tmp_path / "release_splits"
    manifest_out_dir = tmp_path / "release_manifests"
    plan_out = tmp_path / "release_split_plan.json"

    report = build_paper_understanding_gold_release_split_plan_from_staging_manifest(
        staging_manifest_path=staging_manifest,
        out_dir=out_dir,
        manifest_out_dir=manifest_out_dir,
        out=plan_out,
    )

    assert plan_out.exists()
    assert report.schema_version == "paper_understanding_gold_release_split_plan.v1"
    assert report.canonical_status == "non_canonical"
    assert report.release_ready_candidate is True
    assert report.ready_input_count == 3
    assert report.invalid_input_count == 0
    assert [item.goldset_split for item in report.split_items] == ["seed", "eval", "holdout"]
    assert [item.staged_count for item in report.split_items] == [1, 1, 1]
    assert all(Path(item.staging_manifest_path).exists() for item in report.split_items)
    assert all(Path(item.manifest_out).parent == manifest_out_dir.resolve() for item in report.split_manifests)

    release_out = tmp_path / "release_readiness.json"
    package = build_paper_understanding_gold_release_package_from_staged_gold(
        goldset_id="paper-understanding-pilot-2026-05-22",
        split_manifests=report.split_manifests,
        release_readiness_out=release_out,
    )
    assert package.release_readiness.release_ready is True


def test_build_paper_understanding_gold_release_split_plan_cli(tmp_path: Path):
    staging_manifest = _write_ready_combined_staging_manifest(
        tmp_path,
        paper_ids=["paper-a", "paper-b", "paper-c"],
    )
    out_dir = tmp_path / "release_splits"
    manifest_out_dir = tmp_path / "release_manifests"
    plan_out = tmp_path / "release_split_plan.json"

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/build_paper_understanding_gold_release_split_plan_from_staged_gold.py",
            str(staging_manifest),
            "--out-dir",
            str(out_dir),
            "--manifest-out-dir",
            str(manifest_out_dir),
            "--out",
            str(plan_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(plan_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_release_split_plan.v1"
    assert payload["release_ready_candidate"] is True
    assert "[paper_understanding_gold_release_split_plan] release_ready_candidate=True" in result.stdout
    PaperUnderstandingGoldReleaseSplitPlanReport.model_validate(payload)


def test_build_paper_understanding_gold_release_split_plan_api(tmp_path: Path):
    staging_manifest = _write_ready_combined_staging_manifest(
        tmp_path,
        paper_ids=["paper-a", "paper-b", "paper-c"],
    )
    out_dir = tmp_path / "release_splits"
    manifest_out_dir = tmp_path / "release_manifests"
    plan_out = tmp_path / "release_split_plan.json"
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/release-readiness/split-plan-from-staged-gold",
        json={
            "staging_manifest_path": str(staging_manifest),
            "out_dir": str(out_dir),
            "manifest_out_dir": str(manifest_out_dir),
            "out": str(plan_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_release_split_plan.v1"
    assert payload["release_ready_candidate"] is True
    assert [item["goldset_split"] for item in payload["split_items"]] == ["seed", "eval", "holdout"]
    assert plan_out.exists()


def test_package_paper_understanding_gold_release_from_split_plan(tmp_path: Path):
    staging_manifest = _write_ready_combined_staging_manifest(
        tmp_path,
        paper_ids=["paper-a", "paper-b", "paper-c"],
    )
    split_plan_out = tmp_path / "release_split_plan.json"
    split_plan = build_paper_understanding_gold_release_split_plan_from_staging_manifest(
        staging_manifest_path=staging_manifest,
        out_dir=tmp_path / "release_splits",
        manifest_out_dir=tmp_path / "release_manifests",
        out=split_plan_out,
    )
    release_out = tmp_path / "release_readiness.json"
    package_out = tmp_path / "release_package.json"

    package = build_paper_understanding_gold_release_package_from_split_plan(
        goldset_id="paper-understanding-pilot-2026-05-22",
        split_plan_path=split_plan_out,
        release_readiness_out=release_out,
        package_out=package_out,
    )

    assert split_plan.release_ready_candidate is True
    assert package_out.exists()
    assert package.schema_version == "paper_understanding_gold_release_package.v1"
    assert [item.goldset_split for item in package.source_split_manifests] == ["seed", "eval", "holdout"]
    assert package.release_readiness.release_ready is True
    assert package.release_readiness_report_path == str(release_out.resolve())


def test_package_paper_understanding_gold_release_from_split_plan_cli(tmp_path: Path):
    staging_manifest = _write_ready_combined_staging_manifest(
        tmp_path,
        paper_ids=["paper-a", "paper-b", "paper-c"],
    )
    split_plan_out = tmp_path / "release_split_plan.json"
    build_paper_understanding_gold_release_split_plan_from_staging_manifest(
        staging_manifest_path=staging_manifest,
        out_dir=tmp_path / "release_splits",
        manifest_out_dir=tmp_path / "release_manifests",
        out=split_plan_out,
    )
    release_out = tmp_path / "release_readiness.json"
    package_out = tmp_path / "release_package.json"

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/package_paper_understanding_gold_release_from_split_plan.py",
            "--goldset-id",
            "paper-understanding-pilot-2026-05-22",
            "--split-plan",
            str(split_plan_out),
            "--release-readiness-out",
            str(release_out),
            "--package-out",
            str(package_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(package_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_release_package.v1"
    assert [item["goldset_split"] for item in payload["source_split_manifests"]] == ["seed", "eval", "holdout"]
    assert payload["release_readiness"]["release_ready"] is True
    assert "[paper_understanding_gold_release_package] release_ready=True" in result.stdout
    PaperUnderstandingGoldReleasePackageReport.model_validate(payload)


def test_package_paper_understanding_gold_release_from_split_plan_api(tmp_path: Path):
    staging_manifest = _write_ready_combined_staging_manifest(
        tmp_path,
        paper_ids=["paper-a", "paper-b", "paper-c"],
    )
    split_plan_out = tmp_path / "release_split_plan.json"
    build_paper_understanding_gold_release_split_plan_from_staging_manifest(
        staging_manifest_path=staging_manifest,
        out_dir=tmp_path / "release_splits",
        manifest_out_dir=tmp_path / "release_manifests",
        out=split_plan_out,
    )
    release_out = tmp_path / "release_readiness.json"
    package_out = tmp_path / "release_package.json"
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/release-readiness/package-from-split-plan",
        json={
            "goldset_id": "paper-understanding-pilot-2026-05-22",
            "split_plan_path": str(split_plan_out),
            "release_readiness_out": str(release_out),
            "package_out": str(package_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_release_package.v1"
    assert [item["goldset_split"] for item in payload["source_split_manifests"]] == ["seed", "eval", "holdout"]
    assert payload["release_readiness"]["release_ready"] is True
    assert release_out.exists()
    assert package_out.exists()


def test_validate_paper_understanding_gold_cli_require_ready_accepts_ready_record(tmp_path: Path):
    ready_path = tmp_path / "ready.json"
    ready_path.write_text(json.dumps(_readiness_pass_payload()), encoding="utf-8")

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/validate_paper_understanding_gold.py",
            str(ready_path),
            "--require-ready",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert '"require_ready": true' in result.stdout
    assert '"pass_count": 1' in result.stdout


def test_draft_paper_understanding_gold_from_reviewed_fixtures(tmp_path: Path):
    reviewed_dir = tmp_path / "reviewed"
    reviewed_dir.mkdir()
    (reviewed_dir / "fixture.json").write_text(
        json.dumps(_reviewed_fixture_payload(paper_id="paper-1", claim_id="claim-1")),
        encoding="utf-8",
    )

    drafts = build_paper_understanding_gold_candidate_drafts_from_reviewed_fixtures(reviewed_dir=reviewed_dir)

    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.schema_version == "paper_understanding_gold_candidate_draft.v1"
    assert draft.canonical_status == "non_canonical"
    assert draft.paper_id == "paper-1"
    assert draft.fixture_count == 1
    assert draft.draft.paper_id == "paper-1"
    assert draft.draft.gold_claims[0].text == "The intervention improved survival in the study cohort."
    assert draft.draft.gold_claims[0].evidence_refs[0].chunk_id == "chunk-results"
    assert draft.readiness.status == "fail"
    assert "METHOD_MISSING" in draft.readiness.reason_codes


def test_write_paper_understanding_gold_candidate_drafts_manifest(tmp_path: Path):
    reviewed_dir = tmp_path / "reviewed"
    out_dir = tmp_path / "drafts"
    reviewed_dir.mkdir()
    (reviewed_dir / "fixture.json").write_text(
        json.dumps(_reviewed_fixture_payload(paper_id="paper-1", claim_id="claim-1")),
        encoding="utf-8",
    )

    manifest = write_paper_understanding_gold_candidate_drafts(
        reviewed_dir=reviewed_dir,
        out_dir=out_dir,
    )

    assert manifest.schema_version == "paper_understanding_gold_candidate_draft_manifest.v1"
    assert manifest.canonical_status == "non_canonical"
    assert manifest.draft_count == 1
    assert manifest.readiness_summary["fail_count"] == 1
    assert (out_dir / "manifest.json").exists()
    draft_payload = json.loads(Path(manifest.draft_paths[0]).read_text(encoding="utf-8"))
    assert draft_payload["draft"]["schema_version"] == "paper_understanding_gold.v1"
    assert draft_payload["readiness"]["status"] == "fail"


def test_draft_paper_understanding_gold_from_reviewed_fixtures_cli(tmp_path: Path):
    goldset_root = tmp_path / "goldset"
    reviewed_dir = goldset_root / "reviews" / "claim_evidence_eval_candidates" / "reviewed"
    reviewed_dir.mkdir(parents=True)
    (reviewed_dir / "fixture.json").write_text(
        json.dumps(_reviewed_fixture_payload(paper_id="paper-1", claim_id="claim-1")),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/draft_paper_understanding_gold_from_reviewed_fixtures.py",
            "--goldset-root",
            str(goldset_root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[paper_understanding_gold_drafts] draft_count=1" in result.stdout
    manifest_path = goldset_root / "reviews" / "paper_understanding_gold_drafts" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["canonical_status"] == "non_canonical"
    assert manifest["draft_count"] == 1


def test_draft_paper_understanding_gold_from_reviewed_fixtures_api(tmp_path: Path):
    reviewed_dir = tmp_path / "reviewed"
    out_dir = tmp_path / "drafts"
    reviewed_dir.mkdir()
    (reviewed_dir / "fixture.json").write_text(
        json.dumps(_reviewed_fixture_payload(paper_id="paper-1", claim_id="claim-1")),
        encoding="utf-8",
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/from-reviewed-fixtures",
        json={
            "reviewed_dir": str(reviewed_dir),
            "out_dir": str(out_dir),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_manifest.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["draft_count"] == 1
    assert (out_dir / "manifest.json").exists()


def test_draft_paper_understanding_gold_from_teacher_verification(tmp_path: Path):
    teacher_path = tmp_path / "teacher_verification.json"
    teacher_path.write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")

    drafts = build_paper_understanding_gold_candidate_drafts_from_teacher_verification(paths=[teacher_path])

    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.schema_version == "paper_understanding_gold_candidate_draft.v1"
    assert draft.source_kind == "teacher_verification"
    assert draft.canonical_status == "non_canonical"
    assert draft.paper_id == "zotero:hanssonBloodBiomarkersAlzheimers2023"
    assert draft.fixture_count == 2
    assert draft.draft.gold_claims[0].text == "Blood biomarkers can support Alzheimer disease diagnosis in clinical settings."
    assert draft.draft.gold_claims[0].evidence_refs[0].chunk_id == "chunk-001"
    assert draft.draft.gold_results[0].evidence_refs[0].table_id == "tbl-use-cases"
    assert draft.draft.important_tables[0].table_id == "tbl-use-cases"
    assert draft.readiness.status == "fail"
    assert "METHOD_MISSING" in draft.readiness.reason_codes


def test_write_paper_understanding_gold_teacher_verification_drafts_manifest(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    out_dir = tmp_path / "teacher_drafts"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    (teacher_dir / "unaccepted.json").write_text(
        json.dumps(_teacher_verification_payload(accepted=False)),
        encoding="utf-8",
    )

    manifest = write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[teacher_dir],
        out_dir=out_dir,
    )

    assert manifest.schema_version == "paper_understanding_gold_candidate_draft_manifest.v1"
    assert manifest.canonical_status == "non_canonical"
    assert manifest.draft_count == 1
    assert manifest.readiness_summary["fail_count"] == 1
    assert (out_dir / "manifest.json").exists()
    draft_payload = json.loads(Path(manifest.draft_paths[0]).read_text(encoding="utf-8"))
    assert draft_payload["source_kind"] == "teacher_verification"
    assert draft_payload["draft"]["schema_version"] == "paper_understanding_gold.v1"


def test_draft_paper_understanding_gold_from_teacher_verification_cli(tmp_path: Path):
    goldset_root = tmp_path / "goldset"
    teacher_dir = tmp_path / "teacher"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/draft_paper_understanding_gold_from_teacher_verification.py",
            str(teacher_dir),
            "--goldset-root",
            str(goldset_root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[paper_understanding_gold_teacher_drafts] draft_count=1" in result.stdout
    manifest_path = goldset_root / "reviews" / "paper_understanding_gold_teacher_drafts" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["canonical_status"] == "non_canonical"
    assert manifest["draft_count"] == 1


def test_draft_paper_understanding_gold_from_teacher_verification_api(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    out_dir = tmp_path / "teacher_drafts"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/from-teacher-verification",
        json={
            "paths": [str(teacher_dir)],
            "out_dir": str(out_dir),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_manifest.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["draft_count"] == 1
    draft_payload = json.loads(Path(payload["draft_paths"][0]).read_text(encoding="utf-8"))
    assert draft_payload["source_kind"] == "teacher_verification"


def test_candidate_draft_curation_report_summarizes_readiness_blockers(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    out = tmp_path / "draft_curation_report.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    manifest = write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[teacher_dir],
        out_dir=draft_dir,
    )

    report = build_paper_understanding_gold_candidate_draft_curation_report(
        draft_paths=[Path(manifest.draft_paths[0])],
        out=out,
    )

    assert out.exists()
    assert report.schema_version == "paper_understanding_gold_candidate_draft_curation_report.v1"
    assert report.canonical_status == "non_canonical"
    assert report.draft_count == 1
    assert report.fail_count == 1
    assert report.curation_ready is False
    assert report.reason_code_counts["METHOD_MISSING"] == 1
    assert report.items[0].source_kind == "teacher_verification"
    assert report.items[0].claim_count == 1
    assert report.items[0].result_count == 1
    assert "Add at least one grounded method statement." in report.items[0].next_actions
    method_task = next(task for task in report.items[0].tasks if task.reason_code == "METHOD_MISSING")
    assert method_task.target_field == "gold_methods"
    assert method_task.minimum_required == 1
    assert "Methods" in (method_task.evidence_hint or "")


def test_teacher_verification_curation_package_writes_drafts_and_report(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    out_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")

    package = write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=out_dir,
        package_out=package_out,
    )

    assert package_out.exists()
    assert package.schema_version == "paper_understanding_gold_teacher_verification_curation_package.v1"
    assert package.canonical_status == "non_canonical"
    assert package.draft_manifest.draft_count == 1
    assert package.curation_report.draft_count == 1
    assert package.curation_ready is False
    assert package.warnings == ["candidate_drafts_not_ready"]
    assert Path(package.draft_manifest_path).exists()
    assert Path(package.curation_report_path).exists()


def test_teacher_verification_curation_package_cli_exits_nonzero_for_not_ready_drafts(tmp_path: Path):
    goldset_root = tmp_path / "goldset"
    teacher_dir = goldset_root / "accepted"
    package_out = tmp_path / "teacher_curation_package.json"
    teacher_dir.mkdir(parents=True)
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/package_paper_understanding_gold_teacher_verification_curation.py",
            str(teacher_dir),
            "--goldset-root",
            str(goldset_root),
            "--out",
            str(package_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[paper_understanding_gold_teacher_curation_package] draft_count=1" in result.stdout
    assert "[paper_understanding_gold_teacher_curation_package] curation_ready=False" in result.stdout
    payload = json.loads(package_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_teacher_verification_curation_package.v1"
    assert payload["curation_report"]["warnings"] == ["candidate_drafts_not_ready"]


def test_candidate_draft_curation_report_cli_exits_nonzero_for_not_ready_draft(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    out = tmp_path / "draft_curation_report.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[teacher_dir],
        out_dir=draft_dir,
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/audit_paper_understanding_gold_candidate_drafts.py",
            str(draft_dir),
            "--out",
            str(out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[paper_understanding_gold_candidate_draft_curation] draft_count=1" in result.stdout
    assert "[paper_understanding_gold_candidate_draft_curation] curation_ready=False" in result.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_curation_report.v1"
    assert payload["warnings"] == ["candidate_drafts_not_ready"]
    method_task = next(task for task in payload["items"][0]["tasks"] if task["reason_code"] == "METHOD_MISSING")
    assert method_task["target_field"] == "gold_methods"


def test_candidate_draft_curation_report_api_returns_noncanonical_report(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    out = tmp_path / "draft_curation_report.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[teacher_dir],
        out_dir=draft_dir,
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/curation/audit",
        json={
            "draft_paths": [str(draft_dir)],
            "out": str(out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_curation_report.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["draft_count"] == 1
    assert payload["curation_ready"] is False
    assert payload["reason_code_counts"]["METHOD_MISSING"] == 1
    assert out.exists()


def test_teacher_verification_curation_package_api_returns_noncanonical_package(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    out_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/from-teacher-verification/curation-package",
        json={
            "paths": [str(teacher_dir)],
            "out_dir": str(out_dir),
            "out": str(package_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_teacher_verification_curation_package.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["draft_manifest"]["draft_count"] == 1
    assert payload["curation_report"]["draft_count"] == 1
    assert payload["curation_ready"] is False
    assert payload["curation_report"]["items"][0]["tasks"]
    assert package_out.exists()


def test_reviewer_handoff_package_writes_templates_progress_and_task_export(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    out_dir = tmp_path / "reviewer_handoff"
    package_out = tmp_path / "reviewer_handoff.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")

    package = write_paper_understanding_gold_reviewer_handoff_package(
        paths=[teacher_dir],
        out_dir=out_dir,
        reviewer_id="curator-1",
        package_out=package_out,
    )

    assert package_out.exists()
    assert package.schema_version == "paper_understanding_gold_reviewer_handoff_package.v1"
    assert package.canonical_status == "non_canonical"
    assert package.draft_count == 1
    assert package.patch_template_manifest.template_count == 1
    assert package.open_task_count > 0
    assert package.curation_ready is False
    assert Path(package.curation_package_path).exists()
    assert Path(package.patch_template_manifest_path).exists()
    assert Path(package.curation_progress_report_path).exists()
    assert Path(package.curation_task_export_path).exists()
    assert package.curation_task_export_csv_path is not None
    assert Path(package.curation_task_export_csv_path).exists()
    assert package.reviewer_guide_path is not None
    guide_path = Path(package.reviewer_guide_path)
    assert guide_path.exists()
    guide_text = guide_path.read_text(encoding="utf-8")
    assert "Paper Understanding Gold Reviewer Handoff" in guide_text
    assert "Highest Priority Tasks" in guide_text
    assert "Tasks By Stage" in guide_text
    assert "EXTERNAL_ID_MISSING" in guide_text
    assert "method_context" in guide_text
    assert "--require-edited" in guide_text
    PaperUnderstandingGoldReviewerHandoffPackage.model_validate_json(package_out.read_text(encoding="utf-8"))


def test_reviewer_handoff_package_cli_exits_nonzero_for_open_tasks(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    out_dir = tmp_path / "reviewer_handoff"
    package_out = tmp_path / "reviewer_handoff.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/package_paper_understanding_gold_reviewer_handoff.py",
            str(teacher_dir),
            "--out-dir",
            str(out_dir),
            "--reviewer-id",
            "curator-1",
            "--out",
            str(package_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(package_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_reviewer_handoff_package.v1"
    assert payload["open_task_count"] > 0
    assert "[paper_understanding_gold_reviewer_handoff_package] open_task_count=" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_package] curation_stage_counts=" in result.stdout
    assert "metadata:" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_package] review_priority_counts=" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_package] reviewer_guide=" in result.stdout
    assert payload["reviewer_guide_path"].endswith("reviewer_guide.md")
    assert (out_dir / "reviewer_guide.md").exists()


def test_reviewer_handoff_package_api_returns_noncanonical_package(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    out_dir = tmp_path / "reviewer_handoff"
    package_out = tmp_path / "reviewer_handoff.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/from-teacher-verification/reviewer-handoff-package",
        json={
            "paths": [str(teacher_dir)],
            "out_dir": str(out_dir),
            "reviewer_id": "curator-1",
            "out": str(package_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_reviewer_handoff_package.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["draft_count"] == 1
    assert payload["patch_template_manifest"]["template_count"] == 1
    assert payload["open_task_count"] > 0
    assert payload["reviewer_guide_path"].endswith("reviewer_guide.md")
    assert (out_dir / "reviewer_guide.md").exists()
    assert package_out.exists()


def test_reviewer_handoff_apply_package_marks_unedited_scaffold_as_unedited(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    handoff_dir = tmp_path / "reviewer_handoff"
    package_out = tmp_path / "reviewer_handoff.json"
    apply_dir = tmp_path / "handoff_apply"
    apply_out = tmp_path / "handoff_apply.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_reviewer_handoff_package(
        paths=[teacher_dir],
        out_dir=handoff_dir,
        reviewer_id="curator-1",
        package_out=package_out,
    )

    package = apply_paper_understanding_gold_reviewer_handoff_package(
        PaperUnderstandingGoldReviewerHandoffApplyRequest(
            reviewer_handoff_package_path=str(package_out),
            out_dir=str(apply_dir),
            out=str(apply_out),
        )
    )

    assert package.result_count == 1
    assert package.curation_ready_count == 0
    assert package.not_ready_count == 1
    assert package.patch_result_manifest.edited_result_count == 0
    assert package.patch_result_manifest.unedited_result_count == 1
    assert "unedited_patch_result_count=1" in package.patch_result_manifest.warnings
    assert "all_patch_results_unedited" in package.patch_result_manifest.warnings
    assert package.ready_to_stage_count == 0
    assert package.remaining_task_count > 0
    assert package.curation_progress_report.items[0].status == "patched_not_ready"
    payload = json.loads(apply_out.read_text(encoding="utf-8"))
    assert payload["patch_result_manifest"]["edited_result_count"] == 0
    assert payload["patch_result_manifest"]["unedited_result_count"] == 1


def test_reviewer_handoff_apply_package_can_require_edited_templates(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    handoff_dir = tmp_path / "reviewer_handoff"
    package_out = tmp_path / "reviewer_handoff.json"
    apply_dir = tmp_path / "handoff_apply"
    apply_out = tmp_path / "handoff_apply.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_reviewer_handoff_package(
        paths=[teacher_dir],
        out_dir=handoff_dir,
        reviewer_id="curator-1",
        package_out=package_out,
    )

    with pytest.raises(ValueError, match="reviewer handoff apply requires edited patch templates"):
        apply_paper_understanding_gold_reviewer_handoff_package(
            PaperUnderstandingGoldReviewerHandoffApplyRequest(
                reviewer_handoff_package_path=str(package_out),
                out_dir=str(apply_dir),
                out=str(apply_out),
                require_edited=True,
            )
        )

    assert not apply_out.exists()
    assert not apply_dir.exists()


def test_reviewer_handoff_apply_package_refreshes_progress_and_task_export(tmp_path: Path):
    package_out, _, _package = _write_ready_reviewer_handoff_package(tmp_path)
    apply_dir = tmp_path / "handoff_apply"
    apply_out = tmp_path / "handoff_apply.json"

    package = apply_paper_understanding_gold_reviewer_handoff_package(
        PaperUnderstandingGoldReviewerHandoffApplyRequest(
            reviewer_handoff_package_path=str(package_out),
            out_dir=str(apply_dir),
            out=str(apply_out),
        )
    )

    assert apply_out.exists()
    assert package.schema_version == "paper_understanding_gold_reviewer_handoff_apply_package.v1"
    assert package.canonical_status == "non_canonical"
    assert package.result_count == 1
    assert package.curation_ready_count == 1
    assert package.not_ready_count == 0
    assert package.patch_result_manifest.edited_result_count == 1
    assert package.patch_result_manifest.unedited_result_count == 0
    assert package.ready_to_stage_count == 1
    assert package.remaining_task_count == 0
    assert Path(package.patch_result_manifest_path).exists()
    assert Path(package.curation_progress_report_path).exists()
    assert Path(package.curation_task_export_path).exists()
    assert package.curation_task_export_csv_path is not None
    assert Path(package.curation_task_export_csv_path).exists()
    assert package.curation_progress_report.items[0].status == "ready_to_stage"
    assert package.curation_task_export.open_task_count == 0
    PaperUnderstandingGoldReviewerHandoffApplyPackage.model_validate_json(
        apply_out.read_text(encoding="utf-8")
    )


def test_reviewer_handoff_apply_cli_refreshes_progress_and_task_export(tmp_path: Path):
    package_out, _, _package = _write_ready_reviewer_handoff_package(tmp_path)
    apply_dir = tmp_path / "handoff_apply"
    apply_out = tmp_path / "handoff_apply.json"

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py",
            str(package_out),
            "--out-dir",
            str(apply_dir),
            "--out",
            str(apply_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[paper_understanding_gold_reviewer_handoff_apply] result_count=1" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_apply] remaining_task_count=0" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_apply] edited_result_count=1" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_apply] unedited_result_count=0" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_apply] curation_stage_counts=-" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_apply] review_priority_counts=-" in result.stdout
    payload = json.loads(apply_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_reviewer_handoff_apply_package.v1"
    assert payload["not_ready_count"] == 0
    assert payload["patch_result_manifest"]["edited_result_count"] == 1
    assert payload["patch_result_manifest"]["unedited_result_count"] == 0
    assert (apply_dir / "patch_results" / "manifest.json").exists()
    assert (apply_dir / "curation_tasks.csv").exists()


def test_reviewer_handoff_apply_cli_can_require_edited_templates(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    handoff_dir = tmp_path / "reviewer_handoff"
    package_out = tmp_path / "reviewer_handoff.json"
    apply_dir = tmp_path / "handoff_apply"
    apply_out = tmp_path / "handoff_apply.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_reviewer_handoff_package(
        paths=[teacher_dir],
        out_dir=handoff_dir,
        reviewer_id="curator-1",
        package_out=package_out,
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py",
            str(package_out),
            "--out-dir",
            str(apply_dir),
            "--out",
            str(apply_out),
            "--require-edited",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "reviewer handoff apply requires edited patch templates" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_apply] finding_count=4" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_apply] finding.1=no_edited_patch_results" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_apply] finding.2=unedited_patch_result_count=1" in result.stdout
    assert (
        "[paper_understanding_gold_reviewer_handoff_apply] "
        "finding.3=unedited_patch_template_path_count=1"
    ) in result.stdout
    assert (
        "[paper_understanding_gold_reviewer_handoff_apply] "
        "finding.4=unedited_patch_template_paths_sample="
    ) in result.stdout
    assert ".patch_template.json" in result.stdout
    assert not apply_out.exists()
    assert not apply_dir.exists()


def test_reviewer_handoff_apply_api_returns_noncanonical_package(tmp_path: Path):
    package_out, _, _package = _write_ready_reviewer_handoff_package(tmp_path)
    apply_dir = tmp_path / "handoff_apply"
    apply_out = tmp_path / "handoff_apply.json"
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/reviewer-handoff/apply",
        json={
            "reviewer_handoff_package_path": str(package_out),
            "out_dir": str(apply_dir),
            "out": str(apply_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_reviewer_handoff_apply_package.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["result_count"] == 1
    assert payload["curation_ready_count"] == 1
    assert payload["remaining_task_count"] == 0
    assert apply_out.exists()


def test_reviewer_handoff_apply_api_can_require_edited_templates(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    handoff_dir = tmp_path / "reviewer_handoff"
    package_out = tmp_path / "reviewer_handoff.json"
    apply_dir = tmp_path / "handoff_apply"
    apply_out = tmp_path / "handoff_apply.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_reviewer_handoff_package(
        paths=[teacher_dir],
        out_dir=handoff_dir,
        reviewer_id="curator-1",
        package_out=package_out,
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/reviewer-handoff/apply",
        json={
            "reviewer_handoff_package_path": str(package_out),
            "out_dir": str(apply_dir),
            "out": str(apply_out),
            "require_edited": True,
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["message"] == "Reviewer handoff apply requires edited patch templates."
    assert "no_edited_patch_results" in detail["findings"]
    assert "unedited_patch_result_count=1" in detail["findings"]
    assert "unedited_patch_template_path_count=1" in detail["findings"]
    assert any(item.startswith("unedited_patch_template_paths_sample=") for item in detail["findings"])
    assert not apply_out.exists()
    assert not apply_dir.exists()


def test_reviewer_handoff_stage_package_stages_ready_apply_package(tmp_path: Path):
    apply_out, _apply_dir = _write_ready_reviewer_handoff_apply_package(tmp_path)
    stage_dir = tmp_path / "handoff_stage"
    stage_out = tmp_path / "handoff_stage.json"

    package = stage_paper_understanding_gold_reviewer_handoff_apply_package(
        PaperUnderstandingGoldReviewerHandoffStageRequest(
            reviewer_handoff_apply_package_path=str(apply_out),
            out_dir=str(stage_dir),
            out=str(stage_out),
        )
    )

    assert stage_out.exists()
    assert package.schema_version == "paper_understanding_gold_reviewer_handoff_stage_package.v1"
    assert package.canonical_status == "non_canonical"
    assert package.staged_count == 1
    assert package.curation_complete is True
    assert package.remaining_task_count == 0
    assert Path(package.staging_manifest_path).exists()
    assert Path(package.curation_progress_report_path).exists()
    assert Path(package.curation_task_export_path).exists()
    assert package.curation_task_export_csv_path is not None
    assert Path(package.curation_task_export_csv_path).exists()
    assert package.curation_progress_report.items[0].status == "staged"
    assert package.staging_manifest.staged_paths
    staged_payload = json.loads(Path(package.staging_manifest.staged_paths[0]).read_text(encoding="utf-8"))
    assert staged_payload["schema_version"] == "paper_understanding_gold.v1"
    PaperUnderstandingGoldReviewerHandoffStagePackage.model_validate_json(
        stage_out.read_text(encoding="utf-8")
    )


def test_reviewer_handoff_stage_cli_stages_ready_apply_package(tmp_path: Path):
    apply_out, _apply_dir = _write_ready_reviewer_handoff_apply_package(tmp_path)
    stage_dir = tmp_path / "handoff_stage"
    stage_out = tmp_path / "handoff_stage.json"

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/stage_paper_understanding_gold_reviewer_handoff.py",
            str(apply_out),
            "--out-dir",
            str(stage_dir),
            "--out",
            str(stage_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[paper_understanding_gold_reviewer_handoff_stage] staged_count=1" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_stage] remaining_task_count=0" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_stage] curation_stage_counts=-" in result.stdout
    assert "[paper_understanding_gold_reviewer_handoff_stage] review_priority_counts=-" in result.stdout
    payload = json.loads(stage_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_reviewer_handoff_stage_package.v1"
    assert payload["curation_complete"] is True
    assert (stage_dir / "staged_gold" / "staging_manifest.json").exists()
    assert (stage_dir / "curation_tasks.csv").exists()


def test_reviewer_handoff_stage_api_returns_noncanonical_package(tmp_path: Path):
    apply_out, _apply_dir = _write_ready_reviewer_handoff_apply_package(tmp_path)
    stage_dir = tmp_path / "handoff_stage"
    stage_out = tmp_path / "handoff_stage.json"
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/reviewer-handoff/stage",
        json={
            "reviewer_handoff_apply_package_path": str(apply_out),
            "out_dir": str(stage_dir),
            "out": str(stage_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_reviewer_handoff_stage_package.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["staged_count"] == 1
    assert payload["curation_complete"] is True
    assert payload["remaining_task_count"] == 0
    assert stage_out.exists()


def test_reviewer_handoff_release_prep_package_builds_single_split_release(tmp_path: Path):
    stage_out, _stage_dir = _write_ready_reviewer_handoff_stage_package(tmp_path)
    release_dir = tmp_path / "handoff_release"
    release_out = tmp_path / "handoff_release.json"

    package = build_paper_understanding_gold_reviewer_handoff_release_prep_package(
        PaperUnderstandingGoldReviewerHandoffReleasePrepRequest(
            reviewer_handoff_stage_package_path=str(stage_out),
            out_dir=str(release_dir),
            goldset_id="paper-understanding-pilot-2026-05-22",
            split_names=["eval"],
            required_splits=["eval"],
            out=str(release_out),
        )
    )

    assert release_out.exists()
    assert package.schema_version == "paper_understanding_gold_reviewer_handoff_release_prep_package.v1"
    assert package.canonical_status == "non_canonical"
    assert package.staged_count == 1
    assert package.split_count == 1
    assert package.release_ready_candidate is True
    assert package.release_ready is True
    assert package.release_package is not None
    assert package.release_package.release_readiness.release_ready is True
    assert package.release_package_path is not None
    assert package.release_readiness_report_path is not None
    assert Path(package.split_plan_path).exists()
    assert Path(package.release_package_path).exists()
    assert Path(package.release_readiness_report_path).exists()
    assert package.split_plan.split_items[0].goldset_split == "eval"
    PaperUnderstandingGoldReviewerHandoffReleasePrepPackage.model_validate_json(
        release_out.read_text(encoding="utf-8")
    )


def test_reviewer_handoff_release_prep_cli_builds_single_split_release(tmp_path: Path):
    stage_out, _stage_dir = _write_ready_reviewer_handoff_stage_package(tmp_path)
    release_dir = tmp_path / "handoff_release"
    release_out = tmp_path / "handoff_release.json"

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/prep_paper_understanding_gold_reviewer_handoff_release.py",
            str(stage_out),
            "--out-dir",
            str(release_dir),
            "--goldset-id",
            "paper-understanding-pilot-2026-05-22",
            "--split",
            "eval",
            "--required-split",
            "eval",
            "--out",
            str(release_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[paper_understanding_gold_reviewer_handoff_release_prep] release_ready=True" in result.stdout
    payload = json.loads(release_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_reviewer_handoff_release_prep_package.v1"
    assert payload["release_ready"] is True
    assert (release_dir / "release_split_plan.json").exists()
    assert (release_dir / "release_package.json").exists()
    assert (release_dir / "release_readiness.json").exists()


def test_reviewer_handoff_release_prep_api_returns_noncanonical_package(tmp_path: Path):
    stage_out, _stage_dir = _write_ready_reviewer_handoff_stage_package(tmp_path)
    release_dir = tmp_path / "handoff_release"
    release_out = tmp_path / "handoff_release.json"
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/reviewer-handoff/release-prep",
        json={
            "reviewer_handoff_stage_package_path": str(stage_out),
            "out_dir": str(release_dir),
            "goldset_id": "paper-understanding-pilot-2026-05-22",
            "split_names": ["eval"],
            "required_splits": ["eval"],
            "out": str(release_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_reviewer_handoff_release_prep_package.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["release_ready_candidate"] is True
    assert payload["release_ready"] is True
    assert payload["release_package"]["release_readiness"]["release_ready"] is True
    assert release_out.exists()


def test_patch_paper_understanding_gold_candidate_draft_recalculates_readiness(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    patched_path = tmp_path / "patched.candidate_draft.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    manifest = write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[teacher_dir],
        out_dir=draft_dir,
    )
    draft_path = Path(manifest.draft_paths[0])
    request = PaperUnderstandingGoldCandidateDraftPatchRequest.model_validate(
        _candidate_draft_ready_patch_payload(
            draft_path=draft_path,
            paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
            out=patched_path,
        )
    )

    result = patch_paper_understanding_gold_candidate_draft(request)

    assert result.schema_version == "paper_understanding_gold_candidate_draft_patch_result.v1"
    assert result.canonical_status == "non_canonical"
    assert result.before_readiness.status == "fail"
    assert result.after_readiness.status == "pass"
    assert result.curation_ready is True
    assert "gold_methods" in result.changed_fields
    assert result.reviewer_id == "curator-1"
    assert patched_path.exists()
    patched_payload = json.loads(patched_path.read_text(encoding="utf-8"))
    assert patched_payload["readiness"]["status"] == "pass"
    assert patched_payload["draft"]["paper_type"] == "review"


def test_candidate_draft_patch_template_is_valid_editable_patch_scaffold(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    template_out = tmp_path / "patch_template.json"
    patched_path = tmp_path / "patched.candidate_draft.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    manifest = write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[teacher_dir],
        out_dir=draft_dir,
    )
    draft_path = Path(manifest.draft_paths[0])

    template = build_paper_understanding_gold_candidate_draft_patch_template(
        PaperUnderstandingGoldCandidateDraftPatchTemplateRequest(
            draft_path=str(draft_path),
            patched_draft_out=str(patched_path),
            reviewer_id="curator-1",
            out=str(template_out),
        )
    )

    assert template_out.exists()
    assert template.schema_version == "paper_understanding_gold_candidate_draft_patch_template.v1"
    assert template.canonical_status == "non_canonical"
    assert template.readiness.status == "fail"
    assert any(task.reason_code == "METHOD_MISSING" for task in template.open_tasks)
    scaffold = PaperUnderstandingGoldCandidateDraftPatchRequest.model_validate(
        template.patch_request.model_dump(mode="json")
    )
    assert scaffold.draft_path == str(draft_path.resolve())
    assert scaffold.out == str(patched_path)

    filled_payload = template.patch_request.model_dump(mode="json")
    filled_payload.update(
        _candidate_draft_ready_patch_payload(
            draft_path=draft_path,
            paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
            out=patched_path,
        )
    )
    result = patch_paper_understanding_gold_candidate_draft(
        PaperUnderstandingGoldCandidateDraftPatchRequest.model_validate(filled_payload)
    )

    assert result.curation_ready is True
    assert result.after_readiness.status == "pass"
    assert patched_path.exists()


def test_candidate_draft_patch_template_cli_writes_noncanonical_template(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    template_out = tmp_path / "patch_template.json"
    patched_path = tmp_path / "patched.candidate_draft.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    manifest = write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[teacher_dir],
        out_dir=draft_dir,
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/build_paper_understanding_gold_candidate_draft_patch_template.py",
            manifest.draft_paths[0],
            "--patched-draft-out",
            str(patched_path),
            "--reviewer-id",
            "curator-1",
            "--out",
            str(template_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[paper_understanding_gold_candidate_draft_patch_template] open_task_count=" in result.stdout
    payload = json.loads(template_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_patch_template.v1"
    assert payload["patch_request"]["out"] == str(patched_path.resolve())


def test_candidate_draft_patch_template_api_returns_template(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    template_out = tmp_path / "patch_template.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    manifest = write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[teacher_dir],
        out_dir=draft_dir,
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/patch-template",
        json={
            "draft_path": manifest.draft_paths[0],
            "out": str(template_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_patch_template.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["open_tasks"]
    assert template_out.exists()


def test_candidate_draft_patch_template_manifest_writes_templates_for_package(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    patched_dir = tmp_path / "patched"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )

    manifest = write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(package_out),
            out_dir=str(template_dir),
            patched_draft_out_dir=str(patched_dir),
            reviewer_id="curator-1",
        )
    )

    assert manifest.schema_version == "paper_understanding_gold_candidate_draft_patch_template_manifest.v1"
    assert manifest.canonical_status == "non_canonical"
    assert manifest.template_count == 1
    assert manifest.open_task_count > 0
    assert manifest.readiness_summary["fail_count"] == 1
    assert (template_dir / "manifest.json").exists()
    template_payload = json.loads(Path(manifest.template_paths[0]).read_text(encoding="utf-8"))
    assert template_payload["patch_request"]["reviewer_id"] == "curator-1"
    assert template_payload["patch_request"]["out"].startswith(str(patched_dir.resolve()))


def test_candidate_draft_patch_template_manifest_cli_writes_manifest(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/build_paper_understanding_gold_candidate_draft_patch_templates.py",
            str(package_out),
            "--out-dir",
            str(template_dir),
            "--reviewer-id",
            "curator-1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[paper_understanding_gold_candidate_draft_patch_templates] template_count=1" in result.stdout
    payload = json.loads((template_dir / "manifest.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_patch_template_manifest.v1"
    assert payload["template_count"] == 1


def test_candidate_draft_patch_template_manifest_api_returns_manifest(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/patch-templates/build",
        json={
            "curation_package_path": str(package_out),
            "out_dir": str(template_dir),
            "reviewer_id": "curator-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_patch_template_manifest.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["template_count"] == 1
    assert (template_dir / "manifest.json").exists()


def test_candidate_draft_patch_result_manifest_applies_edited_templates(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    patched_dir = tmp_path / "patched"
    result_dir = tmp_path / "patch_results"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    package = write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )
    template_manifest = write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(package_out),
            out_dir=str(template_dir),
            patched_draft_out_dir=str(patched_dir),
            reviewer_id="curator-1",
        )
    )
    template_path = Path(template_manifest.template_paths[0])
    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    template_payload["patch_request"] = _candidate_draft_ready_patch_payload(
        draft_path=Path(package.draft_manifest.draft_paths[0]),
        paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
        out=patched_dir / "ready.candidate_draft.json",
    )
    template_path.write_text(json.dumps(template_payload), encoding="utf-8")

    manifest = write_paper_understanding_gold_candidate_draft_patch_result_manifest(
        PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest(
            patch_template_paths=[str(template_dir / "manifest.json")],
            out_dir=str(result_dir),
        )
    )

    assert manifest.schema_version == "paper_understanding_gold_candidate_draft_patch_result_manifest.v1"
    assert manifest.canonical_status == "non_canonical"
    assert manifest.result_count == 1
    assert manifest.curation_ready_count == 1
    assert manifest.not_ready_count == 0
    assert manifest.readiness_summary == {"pass_count": 1, "warn_count": 0, "fail_count": 0}
    assert Path(manifest.patch_result_paths[0]).exists()
    assert (result_dir / "manifest.json").exists()

    progress = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=package_out,
        patch_template_paths=[template_dir / "manifest.json"],
        patch_result_paths=[result_dir],
    )
    assert progress.templated_count == 0
    assert progress.patched_count == 1
    assert progress.ready_to_stage_count == 1
    assert progress.items[0].status == "ready_to_stage"


def test_candidate_draft_patch_result_manifest_cli_applies_edited_templates(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    patched_dir = tmp_path / "patched"
    result_dir = tmp_path / "patch_results"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    package = write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )
    template_manifest = write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(package_out),
            out_dir=str(template_dir),
            patched_draft_out_dir=str(patched_dir),
        )
    )
    template_path = Path(template_manifest.template_paths[0])
    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    template_payload["patch_request"] = _candidate_draft_ready_patch_payload(
        draft_path=Path(package.draft_manifest.draft_paths[0]),
        paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
        out=patched_dir / "ready.candidate_draft.json",
    )
    template_path.write_text(json.dumps(template_payload), encoding="utf-8")

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/apply_paper_understanding_gold_candidate_draft_patch_templates.py",
            str(template_dir / "manifest.json"),
            "--out-dir",
            str(result_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[paper_understanding_gold_candidate_draft_patch_results] result_count=1" in result.stdout
    assert "[paper_understanding_gold_candidate_draft_patch_results] curation_ready_count=1" in result.stdout
    payload = json.loads((result_dir / "manifest.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_patch_result_manifest.v1"
    assert payload["not_ready_count"] == 0


def test_candidate_draft_patch_result_manifest_api_returns_manifest(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    patched_dir = tmp_path / "patched"
    result_dir = tmp_path / "patch_results"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    package = write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )
    template_manifest = write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(package_out),
            out_dir=str(template_dir),
            patched_draft_out_dir=str(patched_dir),
        )
    )
    template_path = Path(template_manifest.template_paths[0])
    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    template_payload["patch_request"] = _candidate_draft_ready_patch_payload(
        draft_path=Path(package.draft_manifest.draft_paths[0]),
        paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
        out=patched_dir / "ready.candidate_draft.json",
    )
    template_path.write_text(json.dumps(template_payload), encoding="utf-8")
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/patch-templates/apply",
        json={
            "patch_template_paths": [str(template_dir / "manifest.json")],
            "out_dir": str(result_dir),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_patch_result_manifest.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["result_count"] == 1
    assert payload["curation_ready_count"] == 1
    assert (result_dir / "manifest.json").exists()


def test_patch_paper_understanding_gold_candidate_draft_cli_writes_result(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    patch_path = tmp_path / "patch.json"
    patched_path = tmp_path / "patched.candidate_draft.json"
    result_out = tmp_path / "patch_result.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    manifest = write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[teacher_dir],
        out_dir=draft_dir,
    )
    patch_path.write_text(
        json.dumps(
            _candidate_draft_ready_patch_payload(
                draft_path=Path(manifest.draft_paths[0]),
                paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
            )
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/patch_paper_understanding_gold_candidate_draft.py",
            str(patch_path),
            "--out",
            str(patched_path),
            "--result-out",
            str(result_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[paper_understanding_gold_candidate_draft_patch] after_readiness=pass" in result.stdout
    payload = json.loads(result_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_patch_result.v1"
    assert payload["curation_ready"] is True
    assert patched_path.exists()


def test_patch_paper_understanding_gold_candidate_draft_api_returns_patch_result(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    patched_path = tmp_path / "patched.candidate_draft.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    manifest = write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=[teacher_dir],
        out_dir=draft_dir,
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/patch",
        json=_candidate_draft_ready_patch_payload(
            draft_path=Path(manifest.draft_paths[0]),
            paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
            out=patched_path,
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_patch_result.v1"
    assert payload["before_readiness"]["status"] == "fail"
    assert payload["after_readiness"]["status"] == "pass"
    assert payload["curation_ready"] is True
    assert patched_path.exists()


def test_candidate_draft_curation_progress_tracks_patch_and_stage_status(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    patched_path = tmp_path / "patched.candidate_draft.json"
    patch_result_out = tmp_path / "patch_result.json"
    stage_dir = tmp_path / "staged"
    progress_out = tmp_path / "progress.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    package = write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )

    initial = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=package_out,
    )

    assert initial.schema_version == "paper_understanding_gold_candidate_draft_curation_progress.v1"
    assert initial.canonical_status == "non_canonical"
    assert initial.draft_count == 1
    assert initial.not_started_count == 1
    assert initial.templated_count == 0
    assert initial.remaining_task_count > 0
    assert initial.items[0].status == "not_started"

    template_dir = tmp_path / "patch_templates"
    template_manifest = write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(package_out),
            out_dir=str(template_dir),
            patched_draft_out_dir=str(tmp_path / "patched_templates"),
            reviewer_id="curator",
        )
    )
    templated = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=package_out,
        patch_template_paths=[template_dir / "manifest.json"],
    )

    assert template_manifest.template_count == 1
    assert templated.not_started_count == 0
    assert templated.templated_count == 1
    assert templated.patched_count == 0
    assert templated.remaining_task_count > 0
    assert templated.items[0].status == "templated"
    assert templated.items[0].latest_patch_template_path == template_manifest.template_paths[0]

    patch_result = patch_paper_understanding_gold_candidate_draft(
        PaperUnderstandingGoldCandidateDraftPatchRequest.model_validate(
            _candidate_draft_ready_patch_payload(
                draft_path=Path(package.draft_manifest.draft_paths[0]),
                paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
                out=patched_path,
            )
        )
    )
    patch_result_out.write_text(patch_result.model_dump_json(indent=2), encoding="utf-8")

    patched = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=package_out,
        patch_template_paths=[template_dir / "manifest.json"],
        patch_result_paths=[patch_result_out],
    )

    assert patched.templated_count == 0
    assert patched.patched_count == 1
    assert patched.ready_to_stage_count == 1
    assert patched.remaining_task_count == 0
    assert patched.items[0].status == "ready_to_stage"
    assert patched.items[0].latest_patch_result_path == str(patch_result_out)

    stage_paper_understanding_gold_from_candidate_drafts(
        draft_paths=[patched_path],
        out_dir=stage_dir,
    )
    staged = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=package_out,
        patch_template_paths=[template_dir / "manifest.json"],
        patch_result_paths=[patch_result_out],
        staged_paths=[stage_dir],
        out=progress_out,
    )

    assert progress_out.exists()
    assert staged.staged_count == 1
    assert staged.curation_complete is True
    assert staged.items[0].status == "staged"
    assert staged.items[0].latest_patch_template_path == template_manifest.template_paths[0]
    assert staged.items[0].staged_gold_path


def test_export_paper_understanding_gold_curation_tasks_from_progress(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "drafts"
    package_out = tmp_path / "curation_package.json"
    export_out = tmp_path / "curation_tasks.json"
    progress_out = tmp_path / "curation_progress.json"
    csv_out = tmp_path / "curation_tasks.csv"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )

    report = build_paper_understanding_gold_curation_task_export_report(
        curation_package_path=package_out,
        progress_report_out=progress_out,
        csv_out=csv_out,
        out=export_out,
    )

    assert report.schema_version == "paper_understanding_gold_curation_task_export.v1"
    assert report.canonical_status == "non_canonical"
    assert report.curation_progress_report_path == str(progress_out.resolve())
    assert report.paper_count == 1
    assert report.open_task_count == len(report.items)
    assert report.open_task_count > 0
    assert report.reason_code_counts["METHOD_MISSING"] == 1
    assert "gold_methods" in report.target_field_counts
    assert report.curation_stage_counts["metadata"] >= 1
    assert report.review_priority_counts["10"] == 1
    assert all(item.curation_stage for item in report.items)
    assert all(item.review_priority >= 0 for item in report.items)
    assert [item.review_priority for item in report.items] == sorted(item.review_priority for item in report.items)
    assert report.items[0].reason_code == "EXTERNAL_ID_MISSING"
    assert progress_out.exists()
    assert export_out.exists()
    assert csv_out.exists()
    csv_text = csv_out.read_text(encoding="utf-8")
    assert "paper_id,task_id,status" in csv_text
    assert "curation_stage,review_priority" in csv_text
    PaperUnderstandingGoldCurationTaskExportReport.model_validate_json(export_out.read_text(encoding="utf-8"))


def test_export_paper_understanding_gold_curation_tasks_cli(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "drafts"
    package_out = tmp_path / "curation_package.json"
    export_out = tmp_path / "curation_tasks.json"
    csv_out = tmp_path / "curation_tasks.csv"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/export_paper_understanding_gold_curation_tasks.py",
            str(package_out),
            "--csv-out",
            str(csv_out),
            "--out",
            str(export_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(export_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_curation_task_export.v1"
    assert payload["open_task_count"] > 0
    assert csv_out.exists()
    assert "[paper_understanding_gold_curation_task_export] open_task_count=" in result.stdout
    assert "[paper_understanding_gold_curation_task_export] curation_stage_counts=" in result.stdout
    assert "metadata:" in result.stdout
    assert "[paper_understanding_gold_curation_task_export] review_priority_counts=" in result.stdout


def test_export_paper_understanding_gold_curation_tasks_api(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "drafts"
    package_out = tmp_path / "curation_package.json"
    export_out = tmp_path / "curation_tasks.json"
    csv_out = tmp_path / "curation_tasks.csv"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/curation/tasks/export",
        json={
            "curation_package_path": str(package_out),
            "csv_out": str(csv_out),
            "out": str(export_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_curation_task_export.v1"
    assert payload["open_task_count"] > 0
    assert export_out.exists()
    assert csv_out.exists()


def test_candidate_draft_curation_progress_cli_exits_nonzero_when_incomplete(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    progress_out = tmp_path / "progress.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/audit_paper_understanding_gold_candidate_draft_curation_progress.py",
            str(package_out),
            "--out",
            str(progress_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[paper_understanding_gold_curation_progress] curation_complete=False" in result.stdout
    payload = json.loads(progress_out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_curation_progress.v1"
    assert payload["not_started_count"] == 1


def test_candidate_draft_curation_progress_cli_tracks_patch_templates(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    progress_out = tmp_path / "progress.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )
    write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(package_out),
            out_dir=str(template_dir),
        )
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/audit_paper_understanding_gold_candidate_draft_curation_progress.py",
            str(package_out),
            "--patch-template",
            str(template_dir / "manifest.json"),
            "--out",
            str(progress_out),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "[paper_understanding_gold_curation_progress] templated_count=1" in result.stdout
    payload = json.loads(progress_out.read_text(encoding="utf-8"))
    assert payload["not_started_count"] == 0
    assert payload["templated_count"] == 1
    assert payload["items"][0]["status"] == "templated"
    assert payload["items"][0]["latest_patch_template_path"]


def test_candidate_draft_curation_progress_api_returns_report(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    progress_out = tmp_path / "progress.json"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )
    write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(package_out),
            out_dir=str(template_dir),
        )
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/curation/progress",
        json={
            "curation_package_path": str(package_out),
            "patch_template_paths": [str(template_dir)],
            "out": str(progress_out),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_candidate_draft_curation_progress.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["draft_count"] == 1
    assert payload["templated_count"] == 1
    assert payload["items"][0]["status"] == "templated"
    assert payload["curation_complete"] is False
    assert progress_out.exists()


def test_stage_paper_understanding_gold_from_candidate_draft_requires_ready(tmp_path: Path):
    reviewed_dir = tmp_path / "reviewed"
    draft_dir = tmp_path / "drafts"
    stage_dir = tmp_path / "staged"
    reviewed_dir.mkdir()
    (reviewed_dir / "fixture.json").write_text(
        json.dumps(_reviewed_fixture_payload(paper_id="paper-1", claim_id="claim-1")),
        encoding="utf-8",
    )
    draft_manifest = write_paper_understanding_gold_candidate_drafts(
        reviewed_dir=reviewed_dir,
        out_dir=draft_dir,
    )

    with pytest.raises(ValueError, match="cannot stage not-ready paper understanding gold drafts"):
        stage_paper_understanding_gold_from_candidate_drafts(
            draft_paths=[Path(draft_manifest.draft_paths[0])],
            out_dir=stage_dir,
        )

    assert not stage_dir.exists()


def test_stage_paper_understanding_gold_from_candidate_draft_writes_ready_gold(tmp_path: Path):
    draft_dir = tmp_path / "drafts"
    stage_dir = tmp_path / "staged"
    draft_dir.mkdir()
    ready_gold = PaperUnderstandingGold.model_validate(_readiness_pass_payload())
    readiness = assess_paper_understanding_gold_readiness(ready_gold)
    draft_path = draft_dir / "ready.candidate_draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_candidate_draft.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_kind": "claim_evidence_reviewed_eval_fixtures",
                "source_reviewed_dir": str(tmp_path / "reviewed"),
                "paper_id": ready_gold.paper_id,
                "fixture_count": 3,
                "readiness": readiness.model_dump(mode="json"),
                "draft": ready_gold.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )

    manifest = stage_paper_understanding_gold_from_candidate_drafts(
        draft_paths=[draft_path],
        out_dir=stage_dir,
    )

    assert manifest.schema_version == "paper_understanding_gold_staging_manifest.v1"
    assert manifest.canonical_status == "non_canonical"
    assert manifest.require_ready is True
    assert manifest.staged_count == 1
    assert manifest.readiness_summary["pass_count"] == 1
    staged_payload = json.loads(Path(manifest.staged_paths[0]).read_text(encoding="utf-8"))
    assert staged_payload["schema_version"] == "paper_understanding_gold.v1"
    assert staged_payload["paper_id"] == ready_gold.paper_id
    assert (stage_dir / "staging_manifest.json").exists()


def test_stage_paper_understanding_gold_from_candidate_drafts_cli(tmp_path: Path):
    goldset_root = tmp_path / "goldset"
    draft_dir = tmp_path / "drafts"
    draft_dir.mkdir()
    ready_gold = PaperUnderstandingGold.model_validate(_readiness_pass_payload())
    readiness = assess_paper_understanding_gold_readiness(ready_gold)
    draft_path = draft_dir / "ready.candidate_draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_candidate_draft.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_kind": "claim_evidence_reviewed_eval_fixtures",
                "source_reviewed_dir": str(tmp_path / "reviewed"),
                "paper_id": ready_gold.paper_id,
                "fixture_count": 3,
                "readiness": readiness.model_dump(mode="json"),
                "draft": ready_gold.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/stage_paper_understanding_gold_from_candidate_drafts.py",
            str(draft_path),
            "--goldset-root",
            str(goldset_root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[paper_understanding_gold_staging] staged_count=1" in result.stdout
    manifest_path = goldset_root / "reviews" / "paper_understanding_gold_staged" / "staging_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["canonical_status"] == "non_canonical"
    assert manifest["staged_count"] == 1


def test_stage_paper_understanding_gold_from_candidate_drafts_api(tmp_path: Path):
    draft_dir = tmp_path / "drafts"
    stage_dir = tmp_path / "staged"
    draft_dir.mkdir()
    ready_gold = PaperUnderstandingGold.model_validate(_readiness_pass_payload())
    readiness = assess_paper_understanding_gold_readiness(ready_gold)
    draft_path = draft_dir / "ready.candidate_draft.json"
    draft_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_understanding_gold_candidate_draft.v1",
                "layer": "review_gate_artifact",
                "canonical_status": "non_canonical",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_kind": "claim_evidence_reviewed_eval_fixtures",
                "source_reviewed_dir": str(tmp_path / "reviewed"),
                "paper_id": ready_gold.paper_id,
                "fixture_count": 3,
                "readiness": readiness.model_dump(mode="json"),
                "draft": ready_gold.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/stage",
        json={
            "draft_paths": [str(draft_path)],
            "out_dir": str(stage_dir),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_staging_manifest.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["staged_count"] == 1
    assert (stage_dir / "staging_manifest.json").exists()


def test_stage_paper_understanding_gold_from_patch_results_completes_progress(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    patched_dir = tmp_path / "patched"
    result_dir = tmp_path / "patch_results"
    stage_dir = tmp_path / "staged"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    package = write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )
    template_manifest = write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(package_out),
            out_dir=str(template_dir),
            patched_draft_out_dir=str(patched_dir),
        )
    )
    template_path = Path(template_manifest.template_paths[0])
    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    template_payload["patch_request"] = _candidate_draft_ready_patch_payload(
        draft_path=Path(package.draft_manifest.draft_paths[0]),
        paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
        out=patched_dir / "ready.candidate_draft.json",
    )
    template_path.write_text(json.dumps(template_payload), encoding="utf-8")
    patch_manifest = write_paper_understanding_gold_candidate_draft_patch_result_manifest(
        PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest(
            patch_template_paths=[str(template_dir / "manifest.json")],
            out_dir=str(result_dir),
        )
    )

    staging_manifest = stage_paper_understanding_gold_from_patch_results(
        patch_result_paths=[result_dir / "manifest.json"],
        out_dir=stage_dir,
    )

    assert staging_manifest.schema_version == "paper_understanding_gold_staging_manifest.v1"
    assert staging_manifest.canonical_status == "non_canonical"
    assert staging_manifest.staged_count == 1
    assert staging_manifest.source_draft_paths == [str(patched_dir / "ready.candidate_draft.json")]
    progress = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=package_out,
        patch_template_paths=[template_dir / "manifest.json"],
        patch_result_paths=[patch_manifest.patch_result_paths[0]],
        staged_paths=[stage_dir],
    )
    assert progress.staged_count == 1
    assert progress.remaining_task_count == 0
    assert progress.curation_complete is True
    assert progress.items[0].status == "staged"


def test_stage_paper_understanding_gold_from_patch_results_cli(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    patched_dir = tmp_path / "patched"
    result_dir = tmp_path / "patch_results"
    goldset_root = tmp_path / "goldset"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    package = write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )
    template_manifest = write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(package_out),
            out_dir=str(template_dir),
            patched_draft_out_dir=str(patched_dir),
        )
    )
    template_path = Path(template_manifest.template_paths[0])
    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    template_payload["patch_request"] = _candidate_draft_ready_patch_payload(
        draft_path=Path(package.draft_manifest.draft_paths[0]),
        paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
        out=patched_dir / "ready.candidate_draft.json",
    )
    template_path.write_text(json.dumps(template_payload), encoding="utf-8")
    write_paper_understanding_gold_candidate_draft_patch_result_manifest(
        PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest(
            patch_template_paths=[str(template_dir / "manifest.json")],
            out_dir=str(result_dir),
        )
    )

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/stage_paper_understanding_gold_from_patch_results.py",
            str(result_dir / "manifest.json"),
            "--goldset-root",
            str(goldset_root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "[paper_understanding_gold_staging_from_patch_results] staged_count=1" in result.stdout
    manifest_path = goldset_root / "reviews" / "paper_understanding_gold_staged" / "staging_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["canonical_status"] == "non_canonical"
    assert manifest["staged_count"] == 1


def test_stage_paper_understanding_gold_from_patch_results_api(tmp_path: Path):
    teacher_dir = tmp_path / "teacher"
    draft_dir = tmp_path / "teacher_drafts"
    package_out = tmp_path / "teacher_curation_package.json"
    template_dir = tmp_path / "patch_templates"
    patched_dir = tmp_path / "patched"
    result_dir = tmp_path / "patch_results"
    stage_dir = tmp_path / "staged"
    teacher_dir.mkdir()
    (teacher_dir / "accepted.json").write_text(json.dumps(_teacher_verification_payload()), encoding="utf-8")
    package = write_paper_understanding_gold_teacher_verification_curation_package(
        paths=[teacher_dir],
        out_dir=draft_dir,
        package_out=package_out,
    )
    template_manifest = write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(package_out),
            out_dir=str(template_dir),
            patched_draft_out_dir=str(patched_dir),
        )
    )
    template_path = Path(template_manifest.template_paths[0])
    template_payload = json.loads(template_path.read_text(encoding="utf-8"))
    template_payload["patch_request"] = _candidate_draft_ready_patch_payload(
        draft_path=Path(package.draft_manifest.draft_paths[0]),
        paper_id="zotero:hanssonBloodBiomarkersAlzheimers2023",
        out=patched_dir / "ready.candidate_draft.json",
    )
    template_path.write_text(json.dumps(template_payload), encoding="utf-8")
    write_paper_understanding_gold_candidate_draft_patch_result_manifest(
        PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest(
            patch_template_paths=[str(template_dir / "manifest.json")],
            out_dir=str(result_dir),
        )
    )
    client = TestClient(api_main.app)

    response = client.post(
        "/paper-understanding-gold/candidate-drafts/stage-from-patch-results",
        json={
            "patch_result_paths": [str(result_dir / "manifest.json")],
            "out_dir": str(stage_dir),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "paper_understanding_gold_staging_manifest.v1"
    assert payload["canonical_status"] == "non_canonical"
    assert payload["staged_count"] == 1
    assert (stage_dir / "staging_manifest.json").exists()


def test_validate_paper_understanding_gold_cli_exits_nonzero_for_invalid_file(tmp_path: Path):
    invalid_path = tmp_path / "invalid.json"
    invalid = _gold_payload()
    invalid["important_tables"] = []
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")

    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/eval/validate_paper_understanding_gold.py",
            str(invalid_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "invalid_count" in result.stdout
    assert "undeclared table_id=tbl1" in result.stdout
