from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from src.schemas.evidence_grounding_scorecard import (
    EvidenceGroundingScorecardInputBackfillReport,
    EvidenceGroundingScorecardInputBackfillRequest,
)

from src.schemas.evidence_grounding_benchmark import (
    EvidenceGroundingBenchmarkManifest,
    EvidenceGroundingBenchmarkManifestPackage,
    EvidenceGroundingBenchmarkManifestPackageFromReleasePackageRequest,
    EvidenceGroundingBenchmarkManifestFromGoldsetRequest,
    EvidenceGroundingBenchmarkManifestFromStagedGoldRequest,
    EvidenceGroundingBenchmarkReport,
    EvidenceGroundingBenchmarkRunDirMap,
    EvidenceGroundingBenchmarkRunDirMapDiscovery,
    EvidenceGroundingBenchmarkRunDirMapDiscoveryRequest,
    EvidenceGroundingBenchmarkRunDirMapRequest,
    EvidenceGroundingBenchmarkRunPackage,
    EvidenceGroundingBenchmarkRunPackageRequest,
    EvidenceGroundingBenchmarkRunRequest,
    EvidenceGroundingCandidateConfig,
    EvidenceGroundingCandidateLineagePatchApplyRequest,
    EvidenceGroundingCandidateLineagePatchTemplate,
    EvidenceGroundingCandidateLineagePatchTemplateRequest,
    EvidenceGroundingActiveReviewReadinessReport,
    EvidenceGroundingActiveReviewReadinessRequest,
    EvidenceGroundingContractCompatibilityAuditRequest,
    EvidenceGroundingContractCompatibilityFromComparisonSuiteRequest,
    EvidenceGroundingContractCompatibilityReport,
    EvidenceGroundingContractReadinessAuditRequest,
    EvidenceGroundingContractReadinessFromComparisonSuiteRequest,
    EvidenceGroundingContractReadinessFromThresholdAdoptionPackageRequest,
    EvidenceGroundingContractReadinessReport,
    EvidenceGroundingFixedGoldsetComparisonSuiteRequest,
    EvidenceGroundingFixedGoldsetComparisonSuitePackage,
    EvidenceGroundingFixedGoldsetComparisonSuitePackageFromRunPackagesRequest,
    EvidenceGroundingFixedGoldsetComparisonSuiteFromStagedGoldRequest,
    EvidenceGroundingFixedGoldsetRunReadinessAuditRequest,
    EvidenceGroundingFixedGoldsetRunReadinessReport,
    EvidenceGroundingPatchTemplateFillTaskExport,
    EvidenceGroundingPatchTemplateFillTaskExportRequest,
    EvidenceGroundingP0OverstatementReviewPacket,
    EvidenceGroundingP0OverstatementReviewPacketExportRequest,
    EvidenceGroundingP0OverstatementReviewSummary,
    EvidenceGroundingP0OverstatementReviewSummaryRequest,
    EvidenceGroundingRoadmapCompletionAuditReport,
    EvidenceGroundingRoadmapCompletionAuditFromComparisonSuitePackageRequest,
    EvidenceGroundingRoadmapCompletionAuditFromThresholdAdoptionPackageRequest,
    EvidenceGroundingRoadmapCompletionAuditRequest,
    EvidenceGroundingScorecardComparisonFromComparisonSuiteRequest,
    EvidenceGroundingScorecardComparisonRequest,
    EvidenceGroundingScorecardComparisonReport,
    EvidenceGroundingThresholdAdoptionReviewFromComparisonSuiteRequest,
    EvidenceGroundingThresholdAdoptionReviewPackage,
    EvidenceGroundingThresholdAdoptionReviewPackageFromComparisonSuitePackageRequest,
    EvidenceGroundingThresholdAdoptionReviewRequest,
    EvidenceGroundingThresholdAdoptionReviewReport,
    EvidenceGroundingThresholdCalibrationFromComparisonSuiteRequest,
    EvidenceGroundingThresholdCalibrationRequest,
    EvidenceGroundingThresholdCalibrationReport,
)
from src.services.evidence_grounding_benchmark import (
    build_evidence_grounding_benchmark_manifest_from_goldset,
    build_evidence_grounding_benchmark_manifest_package_from_candidate_lineage_patch_template,
    build_evidence_grounding_benchmark_manifest_package_from_release_package,
    build_evidence_grounding_benchmark_manifest_from_staged_gold,
    build_evidence_grounding_benchmark_run_dir_map_report_from_manifest_package,
    build_evidence_grounding_candidate_lineage_patch_template_from_manifest_package,
    build_evidence_grounding_active_review_readiness_report,
    build_evidence_grounding_contract_compatibility_report,
    build_evidence_grounding_contract_compatibility_report_from_comparison_suite,
    build_evidence_grounding_contract_readiness_report_from_comparison_suite,
    build_evidence_grounding_contract_readiness_report_from_threshold_adoption_package,
    build_evidence_grounding_contract_readiness_report,
    build_evidence_grounding_fixed_goldset_run_readiness_report,
    build_evidence_grounding_patch_template_fill_task_export,
    build_evidence_grounding_p0_overstatement_review_packet_from_benchmark_reports,
    build_evidence_grounding_p0_overstatement_review_summary,
    build_evidence_grounding_roadmap_completion_audit_report,
    build_evidence_grounding_roadmap_completion_audit_report_from_comparison_suite_package,
    build_evidence_grounding_roadmap_completion_audit_report_from_threshold_adoption_package,
    build_evidence_grounding_threshold_adoption_review_report_from_comparison_suite,
    build_evidence_grounding_threshold_adoption_review_package_from_comparison_suite_package,
    build_evidence_grounding_threshold_adoption_review_report,
    build_evidence_grounding_threshold_calibration_report,
    build_evidence_grounding_threshold_calibration_report_from_comparison_suite,
    compare_evidence_grounding_scorecard_reports,
    compare_evidence_grounding_scorecard_reports_from_comparison_suite,
    discover_evidence_grounding_benchmark_run_dir_map_from_release_package,
    load_evidence_grounding_benchmark_run_dir_map,
    run_evidence_grounding_fixed_goldset_comparison_suite_package_from_benchmark_run_packages,
    run_evidence_grounding_benchmark_package_from_manifest_package,
    run_evidence_grounding_benchmark_from_manifest_path,
    run_evidence_grounding_fixed_goldset_comparison_suite,
    run_evidence_grounding_fixed_goldset_comparison_suite_from_staged_gold,
    threshold_metric_values_from_calibration_report,
    write_evidence_grounding_p0_overstatement_review_packet,
    write_evidence_grounding_p0_overstatement_review_packet_csv,
    write_evidence_grounding_p0_overstatement_review_packet_markdown,
    write_evidence_grounding_p0_overstatement_review_summary,
    write_evidence_grounding_p0_overstatement_review_summary_open_issue_csv,
)
from src.services.evidence_grounding_scorecard_input_backfill import (
    build_evidence_grounding_scorecard_input_backfill_report,
    load_scorecard_input_backfill_items_from_benchmark_artifacts,
)
from src.services.path_masking import mask_local_paths_in_text


logger = logging.getLogger("paperpipe.backend")
router = APIRouter(prefix="/evidence-grounding", tags=["evidence-grounding"])


def _masked_error_detail(exc: Exception) -> str:
    return mask_local_paths_in_text(str(exc))


@router.post("/scorecards/input-backfill", response_model=EvidenceGroundingScorecardInputBackfillReport)
async def backfill_evidence_grounding_scorecard_inputs(
    payload: EvidenceGroundingScorecardInputBackfillRequest,
):
    try:
        manifest_items = load_scorecard_input_backfill_items_from_benchmark_artifacts(
            benchmark_manifest_paths=[Path(path) for path in payload.benchmark_manifest_paths],
            benchmark_manifest_package_paths=[
                Path(path) for path in payload.benchmark_manifest_package_paths
            ],
        )
        report = build_evidence_grounding_scorecard_input_backfill_report(
            items=[*payload.items, *manifest_items],
            out_run_root=Path(payload.out_run_root).expanduser().resolve(),
            reviewed_fixtures_dir=(
                Path(payload.reviewed_fixtures_dir).expanduser().resolve()
                if payload.reviewed_fixtures_dir
                else None
            ),
            require_reviewed_fixtures=payload.require_reviewed_fixtures,
            overwrite=payload.overwrite,
            write_scorecards=payload.write_scorecards,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
            run_dir_map_out=(
                Path(payload.run_dir_map_out).expanduser().resolve()
                if payload.run_dir_map_out
                else None
            ),
        )
        return _mask_scorecard_input_backfill_response_paths(report)
    except ValueError as exc:
        detail = mask_local_paths_in_text(str(exc))
        logger.warning("Rejected evidence-grounding scorecard input backfill request: %s", detail)
        raise HTTPException(status_code=400, detail=detail) from exc
    except Exception as exc:
        detail = mask_local_paths_in_text(str(exc))
        logger.error("Failed to backfill evidence-grounding scorecard inputs: %s", detail)
        raise HTTPException(status_code=500, detail=detail) from exc


@router.post("/benchmark-manifests/from-goldset", response_model=EvidenceGroundingBenchmarkManifest)
async def build_evidence_grounding_benchmark_manifest(
    payload: EvidenceGroundingBenchmarkManifestFromGoldsetRequest,
):
    try:
        manifest = build_evidence_grounding_benchmark_manifest_from_goldset(
            benchmark_id=payload.benchmark_id,
            goldset_manifest_path=Path(payload.goldset_manifest_path).expanduser().resolve(),
            run_root=Path(payload.run_root).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve(),
            run_dir_template=payload.run_dir_template,
            candidate_prefix=payload.candidate_prefix,
            candidate_config=payload.candidate_config,
            require_complete_candidate_config=payload.require_complete_candidate_config,
            require_ready=payload.require_ready,
            require_existing_runs=payload.require_existing_runs,
        )
        return _mask_benchmark_manifest_response_paths(manifest)
    except Exception as exc:
        logger.error("Failed to build evidence-grounding benchmark manifest: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/benchmark-manifests/from-staged-gold", response_model=EvidenceGroundingBenchmarkManifest)
async def build_evidence_grounding_benchmark_manifest_from_staged_gold_endpoint(
    payload: EvidenceGroundingBenchmarkManifestFromStagedGoldRequest,
):
    try:
        manifest = build_evidence_grounding_benchmark_manifest_from_staged_gold(
            benchmark_id=payload.benchmark_id,
            staging_manifest_path=Path(payload.staging_manifest_path).expanduser().resolve(),
            goldset_id=payload.goldset_id,
            goldset_split=payload.goldset_split,
            goldset_manifest_out=Path(payload.goldset_manifest_out).expanduser().resolve(),
            run_root=Path(payload.run_root).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve(),
            run_dir_template=payload.run_dir_template,
            candidate_prefix=payload.candidate_prefix,
            candidate_config=payload.candidate_config,
            require_complete_candidate_config=payload.require_complete_candidate_config,
            require_ready=payload.require_ready,
            require_existing_runs=payload.require_existing_runs,
        )
        return _mask_benchmark_manifest_response_paths(manifest)
    except Exception as exc:
        logger.error("Failed to build evidence-grounding benchmark manifest from staged gold: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/benchmark-manifests/from-release-package",
    response_model=EvidenceGroundingBenchmarkManifestPackage,
)
async def build_evidence_grounding_benchmark_manifest_package_from_release_endpoint(
    payload: EvidenceGroundingBenchmarkManifestPackageFromReleasePackageRequest,
):
    try:
        package = build_evidence_grounding_benchmark_manifest_package_from_release_package(
            release_package_path=Path(payload.release_package_path).expanduser().resolve(),
            run_root=Path(payload.run_root).expanduser().resolve(),
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            package_id=payload.package_id,
            benchmark_id_prefix=payload.benchmark_id_prefix,
            run_dir_template=payload.run_dir_template,
            run_dir_map_path=Path(payload.run_dir_map_path).expanduser().resolve()
            if payload.run_dir_map_path
            else None,
            candidate_prefix=payload.candidate_prefix,
            candidate_config=payload.candidate_config,
            require_complete_candidate_config=payload.require_complete_candidate_config,
            require_ready=payload.require_ready,
            require_existing_runs=payload.require_existing_runs,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_benchmark_manifest_package_response_paths(package)
    except Exception as exc:
        logger.error("Failed to build evidence-grounding benchmark manifest package from release package: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/benchmark-manifests/run-dir-map",
    response_model=EvidenceGroundingBenchmarkRunDirMap,
)
async def build_evidence_grounding_benchmark_run_dir_map_endpoint(
    payload: EvidenceGroundingBenchmarkRunDirMapRequest,
):
    try:
        report = build_evidence_grounding_benchmark_run_dir_map_report_from_manifest_package(
            benchmark_manifest_package_path=Path(payload.benchmark_manifest_package_path).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_benchmark_run_dir_map_response_paths(report)
    except Exception as exc:
        logger.error("Failed to build evidence-grounding benchmark run-dir map: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/benchmark-manifests/run-dir-map/from-release-package",
    response_model=EvidenceGroundingBenchmarkRunDirMapDiscovery,
)
async def discover_evidence_grounding_benchmark_run_dir_map_endpoint(
    payload: EvidenceGroundingBenchmarkRunDirMapDiscoveryRequest,
):
    try:
        report = discover_evidence_grounding_benchmark_run_dir_map_from_release_package(
            release_package_path=Path(payload.release_package_path).expanduser().resolve(),
            run_root=Path(payload.run_root).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
            report_out=Path(payload.report_out).expanduser().resolve() if payload.report_out else None,
            required_artifacts=payload.required_artifacts,
        )
        return _mask_benchmark_run_dir_map_discovery_response_paths(report)
    except Exception as exc:
        logger.error(
            "Failed to discover evidence-grounding benchmark run-dir map: %s",
            _masked_error_detail(exc),
        )
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/benchmark-manifests/candidate-lineage-patch-template",
    response_model=EvidenceGroundingCandidateLineagePatchTemplate,
)
async def build_evidence_grounding_candidate_lineage_patch_template_endpoint(
    payload: EvidenceGroundingCandidateLineagePatchTemplateRequest,
):
    try:
        template = build_evidence_grounding_candidate_lineage_patch_template_from_manifest_package(
            benchmark_manifest_package_path=Path(payload.benchmark_manifest_package_path).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_candidate_lineage_patch_template_response_paths(template)
    except Exception as exc:
        logger.error(
            "Failed to build evidence-grounding candidate lineage patch template: %s",
            _masked_error_detail(exc),
        )
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/benchmark-manifests/apply-candidate-lineage-patch-template",
    response_model=EvidenceGroundingBenchmarkManifestPackage,
)
async def build_evidence_grounding_benchmark_manifest_package_from_candidate_lineage_patch_template_endpoint(
    payload: EvidenceGroundingCandidateLineagePatchApplyRequest,
):
    try:
        package = build_evidence_grounding_benchmark_manifest_package_from_candidate_lineage_patch_template(
            patch_template_path=Path(payload.patch_template_path).expanduser().resolve(),
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            package_id=payload.package_id,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_benchmark_manifest_package_response_paths(package)
    except Exception as exc:
        logger.error(
            "Failed to apply evidence-grounding candidate lineage patch template: %s",
            _masked_error_detail(exc),
        )
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/benchmarks/run", response_model=EvidenceGroundingBenchmarkReport)
async def run_evidence_grounding_benchmark(
    payload: EvidenceGroundingBenchmarkRunRequest,
):
    try:
        report = run_evidence_grounding_benchmark_from_manifest_path(
            Path(payload.manifest_path).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve(),
        )
        return _mask_benchmark_response_paths(report)
    except Exception as exc:
        logger.error("Failed to run evidence-grounding benchmark: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/benchmarks/run-package", response_model=EvidenceGroundingBenchmarkRunPackage)
async def run_evidence_grounding_benchmark_package(
    payload: EvidenceGroundingBenchmarkRunPackageRequest,
):
    try:
        package = run_evidence_grounding_benchmark_package_from_manifest_package(
            benchmark_manifest_package_path=Path(payload.benchmark_manifest_package_path).expanduser().resolve(),
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            package_id=payload.package_id,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_benchmark_run_package_response_paths(package)
    except Exception as exc:
        logger.error("Failed to run evidence-grounding benchmark package: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/patch-template/fill-tasks/export",
    response_model=EvidenceGroundingPatchTemplateFillTaskExport,
)
async def export_evidence_grounding_patch_template_fill_tasks(
    payload: EvidenceGroundingPatchTemplateFillTaskExportRequest,
):
    try:
        export = build_evidence_grounding_patch_template_fill_task_export(
            fill_readiness_path=Path(payload.fill_readiness_path).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
            csv_out=Path(payload.csv_out).expanduser().resolve() if payload.csv_out else None,
            markdown_out=Path(payload.markdown_out).expanduser().resolve() if payload.markdown_out else None,
        )
        return _mask_patch_template_fill_task_export_response_paths(export)
    except ValueError as exc:
        logger.warning("Rejected evidence-grounding fill-task export request: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=400, detail=_masked_error_detail(exc)) from exc
    except Exception as exc:
        logger.error("Failed to export evidence-grounding fill tasks: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/p0-overstatement-review-packet/export",
    response_model=EvidenceGroundingP0OverstatementReviewPacket,
)
async def export_evidence_grounding_p0_overstatement_review_packet(
    payload: EvidenceGroundingP0OverstatementReviewPacketExportRequest,
):
    try:
        packet = build_evidence_grounding_p0_overstatement_review_packet_from_benchmark_reports(
            benchmark_report_paths=[
                Path(path).expanduser().resolve() for path in payload.benchmark_report_paths
            ]
        )
        if payload.out:
            out = write_evidence_grounding_p0_overstatement_review_packet(packet, Path(payload.out))
            if payload.csv_out:
                write_evidence_grounding_p0_overstatement_review_packet_csv(packet, Path(payload.csv_out))
            if payload.markdown_out:
                write_evidence_grounding_p0_overstatement_review_packet_markdown(
                    packet,
                    Path(payload.markdown_out),
                    json_path=out,
                    csv_path=Path(payload.csv_out).expanduser().resolve() if payload.csv_out else None,
                )
        return _mask_p0_overstatement_review_packet_response_paths(packet)
    except ValueError as exc:
        logger.warning("Rejected evidence-grounding P0 overstatement review packet request: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=400, detail=_masked_error_detail(exc)) from exc
    except Exception as exc:
        logger.error("Failed to export evidence-grounding P0 overstatement review packet: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/p0-overstatement-review-packet/summarize",
    response_model=EvidenceGroundingP0OverstatementReviewSummary,
)
async def summarize_evidence_grounding_p0_overstatement_review_packet(
    payload: EvidenceGroundingP0OverstatementReviewSummaryRequest,
):
    try:
        summary = build_evidence_grounding_p0_overstatement_review_summary(
            packet_path=Path(payload.packet_path).expanduser().resolve(),
            reviewed_csv_path=(
                Path(payload.reviewed_csv_path).expanduser().resolve()
                if payload.reviewed_csv_path
                else None
            ),
        )
        if payload.open_issue_csv_out:
            write_evidence_grounding_p0_overstatement_review_summary_open_issue_csv(
                summary,
                Path(payload.open_issue_csv_out),
            )
        if payload.out:
            write_evidence_grounding_p0_overstatement_review_summary(summary, Path(payload.out))
        return _mask_p0_overstatement_review_summary_response_paths(summary)
    except ValueError as exc:
        logger.warning("Rejected evidence-grounding P0 overstatement summary request: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=400, detail=_masked_error_detail(exc)) from exc
    except Exception as exc:
        logger.error("Failed to summarize evidence-grounding P0 overstatement review packet: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/active-review-readiness/audit",
    response_model=EvidenceGroundingActiveReviewReadinessReport,
)
async def audit_evidence_grounding_active_review_readiness(
    payload: EvidenceGroundingActiveReviewReadinessRequest,
):
    try:
        report = build_evidence_grounding_active_review_readiness_report(
            structured_fill_review_status_path=Path(payload.structured_fill_review_status_path).expanduser().resolve(),
            p0_summary_path=Path(payload.p0_summary_path).expanduser().resolve(),
            active_brief_audit_path=(
                Path(payload.active_brief_audit_path).expanduser().resolve()
                if payload.active_brief_audit_path
                else None
            ),
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_active_review_readiness_response_paths(report)
    except ValueError as exc:
        logger.warning("Rejected evidence-grounding active-review readiness request: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=400, detail=_masked_error_detail(exc)) from exc
    except Exception as exc:
        logger.error("Failed to audit evidence-grounding active-review readiness: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/fixed-goldset-comparison/run", response_model=EvidenceGroundingScorecardComparisonReport)
async def run_evidence_grounding_fixed_goldset_comparison(
    payload: EvidenceGroundingFixedGoldsetComparisonSuiteRequest,
):
    try:
        report = run_evidence_grounding_fixed_goldset_comparison_suite(
            goldset_manifest_path=Path(payload.goldset_manifest_path).expanduser().resolve(),
            baseline_run_root=Path(payload.baseline_run_root).expanduser().resolve(),
            candidate_run_root=Path(payload.candidate_run_root).expanduser().resolve(),
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            suite_id=payload.suite_id,
            baseline_benchmark_id=payload.baseline_benchmark_id,
            candidate_benchmark_id=payload.candidate_benchmark_id,
            run_dir_template=payload.run_dir_template,
            tolerance=payload.tolerance,
            gate_metric_names=payload.gate_metric_names,
            gate_preset=payload.gate_preset,
            threshold_preset=payload.threshold_preset,
            threshold_metric_values=_threshold_metric_values_from_options(
                threshold_calibration_report_path=payload.threshold_calibration_report_path,
                threshold_metric_values=payload.threshold_metric_values,
            ),
            baseline_candidate_config=_candidate_config_or_none(payload.baseline_candidate_config),
            candidate_candidate_config=_candidate_config_or_none(payload.candidate_candidate_config),
            require_complete_candidate_config=payload.require_complete_candidate_config,
            require_ready=payload.require_ready,
            require_existing_runs=payload.require_existing_runs,
        )
        return _mask_scorecard_comparison_response_paths(report)
    except Exception as exc:
        logger.error("Failed to run evidence-grounding fixed-goldset comparison: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/fixed-goldset-comparison/run-from-benchmark-run-packages",
    response_model=EvidenceGroundingFixedGoldsetComparisonSuitePackage,
)
async def run_evidence_grounding_fixed_goldset_comparison_from_benchmark_run_packages(
    payload: EvidenceGroundingFixedGoldsetComparisonSuitePackageFromRunPackagesRequest,
):
    try:
        package = run_evidence_grounding_fixed_goldset_comparison_suite_package_from_benchmark_run_packages(
            baseline_run_package_path=Path(payload.baseline_run_package_path).expanduser().resolve(),
            candidate_run_package_path=Path(payload.candidate_run_package_path).expanduser().resolve(),
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            package_id=payload.package_id,
            suite_id_prefix=payload.suite_id_prefix,
            tolerance=payload.tolerance,
            gate_metric_names=payload.gate_metric_names,
            gate_preset=payload.gate_preset,
            threshold_preset=payload.threshold_preset,
            threshold_metric_values=_threshold_metric_values_from_options(
                threshold_calibration_report_path=payload.threshold_calibration_report_path,
                threshold_metric_values=payload.threshold_metric_values,
            ),
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_fixed_goldset_comparison_package_response_paths(package)
    except Exception as exc:
        logger.error(
            "Failed to run evidence-grounding fixed-goldset comparison from benchmark run packages: %s",
            _masked_error_detail(exc),
        )
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/fixed-goldset-comparison/run-from-staged-gold", response_model=EvidenceGroundingScorecardComparisonReport)
async def run_evidence_grounding_fixed_goldset_comparison_from_staged_gold(
    payload: EvidenceGroundingFixedGoldsetComparisonSuiteFromStagedGoldRequest,
):
    try:
        report = run_evidence_grounding_fixed_goldset_comparison_suite_from_staged_gold(
            staging_manifest_path=Path(payload.staging_manifest_path).expanduser().resolve(),
            goldset_id=payload.goldset_id,
            goldset_split=payload.goldset_split,
            goldset_manifest_out=Path(payload.goldset_manifest_out).expanduser().resolve(),
            baseline_run_root=Path(payload.baseline_run_root).expanduser().resolve(),
            candidate_run_root=Path(payload.candidate_run_root).expanduser().resolve(),
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            suite_id=payload.suite_id,
            baseline_benchmark_id=payload.baseline_benchmark_id,
            candidate_benchmark_id=payload.candidate_benchmark_id,
            run_dir_template=payload.run_dir_template,
            tolerance=payload.tolerance,
            gate_metric_names=payload.gate_metric_names,
            gate_preset=payload.gate_preset,
            threshold_preset=payload.threshold_preset,
            threshold_metric_values=_threshold_metric_values_from_options(
                threshold_calibration_report_path=payload.threshold_calibration_report_path,
                threshold_metric_values=payload.threshold_metric_values,
            ),
            baseline_candidate_config=_candidate_config_or_none(payload.baseline_candidate_config),
            candidate_candidate_config=_candidate_config_or_none(payload.candidate_candidate_config),
            require_complete_candidate_config=payload.require_complete_candidate_config,
            require_ready=payload.require_ready,
            require_existing_runs=payload.require_existing_runs,
        )
        return _mask_scorecard_comparison_response_paths(report)
    except Exception as exc:
        logger.error("Failed to run evidence-grounding fixed-goldset comparison from staged gold: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/contract-compatibility/audit", response_model=EvidenceGroundingContractCompatibilityReport)
async def audit_evidence_grounding_contract_compatibility(
    payload: EvidenceGroundingContractCompatibilityAuditRequest,
):
    try:
        report = build_evidence_grounding_contract_compatibility_report(
            artifact_paths=[Path(path).expanduser().resolve() for path in payload.artifact_paths],
            compatibility_id=payload.compatibility_id,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_contract_compatibility_response_paths(report)
    except Exception as exc:
        logger.error("Failed to audit evidence-grounding contract compatibility: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/contract-compatibility/audit-from-comparison-suite",
    response_model=EvidenceGroundingContractCompatibilityReport,
)
async def audit_evidence_grounding_contract_compatibility_from_comparison_suite(
    payload: EvidenceGroundingContractCompatibilityFromComparisonSuiteRequest,
):
    try:
        report = build_evidence_grounding_contract_compatibility_report_from_comparison_suite(
            comparison_suite_path=Path(payload.comparison_suite_path).expanduser().resolve(),
            threshold_calibration_report_path=(
                Path(payload.threshold_calibration_report_path).expanduser().resolve()
                if payload.threshold_calibration_report_path
                else None
            ),
            threshold_adoption_review_path=(
                Path(payload.threshold_adoption_review_path).expanduser().resolve()
                if payload.threshold_adoption_review_path
                else None
            ),
            compatibility_id=payload.compatibility_id,
            include_embedded_scorecards=payload.include_embedded_scorecards,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_contract_compatibility_response_paths(report)
    except Exception as exc:
        logger.error("Failed to audit evidence-grounding contract compatibility from comparison suite: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/contract-readiness/audit", response_model=EvidenceGroundingContractReadinessReport)
async def audit_evidence_grounding_contract_readiness(
    payload: EvidenceGroundingContractReadinessAuditRequest,
):
    try:
        report = build_evidence_grounding_contract_readiness_report(
            compatibility_report_path=Path(payload.compatibility_report_path).expanduser().resolve(),
            readiness_id=payload.readiness_id,
            migration_plan_path=(
                Path(payload.migration_plan_path).expanduser().resolve() if payload.migration_plan_path else None
            ),
            backfill_plan_path=(
                Path(payload.backfill_plan_path).expanduser().resolve() if payload.backfill_plan_path else None
            ),
            public_contract_doc_path=(
                Path(payload.public_contract_doc_path).expanduser().resolve()
                if payload.public_contract_doc_path
                else None
            ),
            reviewer_approval_reference=payload.reviewer_approval_reference,
            allow_external_contract_ready=payload.allow_external_contract_ready,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_contract_readiness_response_paths(report)
    except Exception as exc:
        logger.error("Failed to audit evidence-grounding contract readiness: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/contract-readiness/audit-from-comparison-suite",
    response_model=EvidenceGroundingContractReadinessReport,
)
async def audit_evidence_grounding_contract_readiness_from_comparison_suite(
    payload: EvidenceGroundingContractReadinessFromComparisonSuiteRequest,
):
    try:
        report = build_evidence_grounding_contract_readiness_report_from_comparison_suite(
            comparison_suite_path=Path(payload.comparison_suite_path).expanduser().resolve(),
            compatibility_report_out=Path(payload.compatibility_report_out).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve(),
            threshold_calibration_report_path=(
                Path(payload.threshold_calibration_report_path).expanduser().resolve()
                if payload.threshold_calibration_report_path
                else None
            ),
            threshold_adoption_review_path=(
                Path(payload.threshold_adoption_review_path).expanduser().resolve()
                if payload.threshold_adoption_review_path
                else None
            ),
            additional_artifact_paths=[
                Path(path).expanduser().resolve() for path in payload.additional_artifact_paths
            ],
            compatibility_id=payload.compatibility_id,
            readiness_id=payload.readiness_id,
            include_embedded_scorecards=payload.include_embedded_scorecards,
            migration_plan_path=(
                Path(payload.migration_plan_path).expanduser().resolve() if payload.migration_plan_path else None
            ),
            backfill_plan_path=(
                Path(payload.backfill_plan_path).expanduser().resolve() if payload.backfill_plan_path else None
            ),
            public_contract_doc_path=(
                Path(payload.public_contract_doc_path).expanduser().resolve()
                if payload.public_contract_doc_path
                else None
            ),
            reviewer_approval_reference=payload.reviewer_approval_reference,
            allow_external_contract_ready=payload.allow_external_contract_ready,
        )
        return _mask_contract_readiness_response_paths(report)
    except Exception as exc:
        logger.error("Failed to audit evidence-grounding contract readiness from comparison suite: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/contract-readiness/audit-from-threshold-adoption-package",
    response_model=EvidenceGroundingContractReadinessReport,
)
async def audit_evidence_grounding_contract_readiness_from_threshold_adoption_package(
    payload: EvidenceGroundingContractReadinessFromThresholdAdoptionPackageRequest,
):
    try:
        report = build_evidence_grounding_contract_readiness_report_from_threshold_adoption_package(
            threshold_adoption_package_path=Path(payload.threshold_adoption_package_path).expanduser().resolve(),
            compatibility_report_out=Path(payload.compatibility_report_out).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve(),
            compatibility_id=payload.compatibility_id,
            readiness_id=payload.readiness_id,
            include_embedded_scorecards=payload.include_embedded_scorecards,
            additional_artifact_paths=[
                Path(path).expanduser().resolve() for path in payload.additional_artifact_paths
            ],
            migration_plan_path=(
                Path(payload.migration_plan_path).expanduser().resolve() if payload.migration_plan_path else None
            ),
            backfill_plan_path=(
                Path(payload.backfill_plan_path).expanduser().resolve() if payload.backfill_plan_path else None
            ),
            public_contract_doc_path=(
                Path(payload.public_contract_doc_path).expanduser().resolve()
                if payload.public_contract_doc_path
                else None
            ),
            reviewer_approval_reference=payload.reviewer_approval_reference,
            allow_external_contract_ready=payload.allow_external_contract_ready,
        )
        return _mask_contract_readiness_response_paths(report)
    except Exception as exc:
        logger.error(
            "Failed to audit evidence-grounding contract readiness from threshold adoption package: %s",
            _masked_error_detail(exc),
        )
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/threshold-calibration/build", response_model=EvidenceGroundingThresholdCalibrationReport)
async def build_evidence_grounding_threshold_calibration(
    payload: EvidenceGroundingThresholdCalibrationRequest,
):
    try:
        report = build_evidence_grounding_threshold_calibration_report(
            report_paths=[Path(path).expanduser().resolve() for path in payload.report_paths],
            calibration_id=payload.calibration_id,
            metric_names=payload.metric_names,
            metric_preset=payload.metric_preset,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_threshold_calibration_response_paths(report)
    except Exception as exc:
        logger.error("Failed to build evidence-grounding threshold calibration: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/threshold-calibration/build-from-comparison-suite",
    response_model=EvidenceGroundingThresholdCalibrationReport,
)
async def build_evidence_grounding_threshold_calibration_from_comparison_suite(
    payload: EvidenceGroundingThresholdCalibrationFromComparisonSuiteRequest,
):
    try:
        report = build_evidence_grounding_threshold_calibration_report_from_comparison_suite(
            comparison_suite_path=Path(payload.comparison_suite_path).expanduser().resolve(),
            calibration_id=payload.calibration_id,
            metric_names=payload.metric_names,
            metric_preset=payload.metric_preset,
            include_baseline_report=payload.include_baseline_report,
            include_candidate_report=payload.include_candidate_report,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_threshold_calibration_response_paths(report)
    except Exception as exc:
        logger.error("Failed to build evidence-grounding threshold calibration from comparison suite: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/scorecards/compare", response_model=EvidenceGroundingScorecardComparisonReport)
async def compare_evidence_grounding_scorecards(
    payload: EvidenceGroundingScorecardComparisonRequest,
):
    try:
        report = compare_evidence_grounding_scorecard_reports(
            baseline=Path(payload.baseline_path).expanduser().resolve(),
            candidate=Path(payload.candidate_path).expanduser().resolve(),
            tolerance=payload.tolerance,
            gate_metric_names=payload.gate_metric_names,
            gate_preset=payload.gate_preset,
            threshold_preset=payload.threshold_preset,
            threshold_metric_values=_threshold_metric_values(payload),
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_scorecard_comparison_response_paths(report)
    except Exception as exc:
        logger.error("Failed to compare evidence-grounding scorecards: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/scorecards/compare-from-comparison-suite",
    response_model=EvidenceGroundingScorecardComparisonReport,
)
async def compare_evidence_grounding_scorecards_from_comparison_suite(
    payload: EvidenceGroundingScorecardComparisonFromComparisonSuiteRequest,
):
    try:
        report = compare_evidence_grounding_scorecard_reports_from_comparison_suite(
            comparison_suite_path=Path(payload.comparison_suite_path).expanduser().resolve(),
            tolerance=payload.tolerance,
            gate_metric_names=payload.gate_metric_names,
            gate_preset=payload.gate_preset,
            threshold_preset=payload.threshold_preset,
            threshold_metric_values=payload.threshold_metric_values,
            threshold_calibration_report_path=(
                Path(payload.threshold_calibration_report_path).expanduser().resolve()
                if payload.threshold_calibration_report_path
                else None
            ),
            out=Path(payload.out).expanduser().resolve(),
        )
        return _mask_scorecard_comparison_response_paths(report)
    except Exception as exc:
        logger.error("Failed to compare evidence-grounding scorecards from comparison suite: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


def _threshold_metric_values(
    payload: EvidenceGroundingScorecardComparisonRequest,
) -> dict[str, float] | None:
    return _threshold_metric_values_from_options(
        threshold_calibration_report_path=payload.threshold_calibration_report_path,
        threshold_metric_values=payload.threshold_metric_values,
    )


def _threshold_metric_values_from_options(
    *,
    threshold_calibration_report_path: str | None,
    threshold_metric_values: dict[str, float] | None,
) -> dict[str, float] | None:
    values: dict[str, float] = {}
    if threshold_calibration_report_path:
        values.update(
            threshold_metric_values_from_calibration_report(
                Path(threshold_calibration_report_path).expanduser().resolve()
            )
        )
    if threshold_metric_values:
        values.update(threshold_metric_values)
    return values or None


def _candidate_config_or_none(
    config: EvidenceGroundingCandidateConfig | None,
) -> EvidenceGroundingCandidateConfig | None:
    if config is not None and config.has_lineage():
        return config
    return None


def _mask_scorecard_input_backfill_response_paths(
    report: EvidenceGroundingScorecardInputBackfillReport,
) -> EvidenceGroundingScorecardInputBackfillReport:
    return EvidenceGroundingScorecardInputBackfillReport.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_benchmark_manifest_response_paths(
    manifest: EvidenceGroundingBenchmarkManifest,
) -> EvidenceGroundingBenchmarkManifest:
    return EvidenceGroundingBenchmarkManifest.model_validate(
        _mask_local_path_payload(manifest.model_dump(mode="json"))
    )


def _mask_benchmark_response_paths(
    report: EvidenceGroundingBenchmarkReport,
) -> EvidenceGroundingBenchmarkReport:
    return EvidenceGroundingBenchmarkReport.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_benchmark_run_package_response_paths(
    package: EvidenceGroundingBenchmarkRunPackage,
) -> EvidenceGroundingBenchmarkRunPackage:
    return EvidenceGroundingBenchmarkRunPackage.model_validate(
        _mask_local_path_payload(package.model_dump(mode="json"))
    )


def _mask_benchmark_run_dir_map_response_paths(
    report: EvidenceGroundingBenchmarkRunDirMap,
) -> EvidenceGroundingBenchmarkRunDirMap:
    return EvidenceGroundingBenchmarkRunDirMap.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_benchmark_run_dir_map_discovery_response_paths(
    report: EvidenceGroundingBenchmarkRunDirMapDiscovery,
) -> EvidenceGroundingBenchmarkRunDirMapDiscovery:
    return EvidenceGroundingBenchmarkRunDirMapDiscovery.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_p0_overstatement_review_packet_response_paths(
    packet: EvidenceGroundingP0OverstatementReviewPacket,
) -> EvidenceGroundingP0OverstatementReviewPacket:
    return EvidenceGroundingP0OverstatementReviewPacket.model_validate(
        _mask_local_path_payload(packet.model_dump(mode="json"))
    )


def _mask_patch_template_fill_task_export_response_paths(
    export: EvidenceGroundingPatchTemplateFillTaskExport,
) -> EvidenceGroundingPatchTemplateFillTaskExport:
    return EvidenceGroundingPatchTemplateFillTaskExport.model_validate(
        _mask_local_path_payload(export.model_dump(mode="json"))
    )


def _mask_p0_overstatement_review_summary_response_paths(
    summary: EvidenceGroundingP0OverstatementReviewSummary,
) -> EvidenceGroundingP0OverstatementReviewSummary:
    return EvidenceGroundingP0OverstatementReviewSummary.model_validate(
        _mask_local_path_payload(summary.model_dump(mode="json"))
    )


def _mask_active_review_readiness_response_paths(
    report: EvidenceGroundingActiveReviewReadinessReport,
) -> EvidenceGroundingActiveReviewReadinessReport:
    return EvidenceGroundingActiveReviewReadinessReport.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_candidate_lineage_patch_template_response_paths(
    template: EvidenceGroundingCandidateLineagePatchTemplate,
) -> EvidenceGroundingCandidateLineagePatchTemplate:
    return EvidenceGroundingCandidateLineagePatchTemplate.model_validate(
        _mask_local_path_payload(template.model_dump(mode="json"))
    )


def _mask_benchmark_manifest_package_response_paths(
    package: EvidenceGroundingBenchmarkManifestPackage,
) -> EvidenceGroundingBenchmarkManifestPackage:
    return EvidenceGroundingBenchmarkManifestPackage.model_validate(
        _mask_local_path_payload(package.model_dump(mode="json"))
    )


def _mask_scorecard_comparison_response_paths(
    report: EvidenceGroundingScorecardComparisonReport,
) -> EvidenceGroundingScorecardComparisonReport:
    return EvidenceGroundingScorecardComparisonReport.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_fixed_goldset_comparison_package_response_paths(
    package: EvidenceGroundingFixedGoldsetComparisonSuitePackage,
) -> EvidenceGroundingFixedGoldsetComparisonSuitePackage:
    return EvidenceGroundingFixedGoldsetComparisonSuitePackage.model_validate(
        _mask_local_path_payload(package.model_dump(mode="json"))
    )


def _mask_contract_compatibility_response_paths(
    report: EvidenceGroundingContractCompatibilityReport,
) -> EvidenceGroundingContractCompatibilityReport:
    return EvidenceGroundingContractCompatibilityReport.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_contract_readiness_response_paths(
    report: EvidenceGroundingContractReadinessReport,
) -> EvidenceGroundingContractReadinessReport:
    return EvidenceGroundingContractReadinessReport.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_fixed_goldset_run_readiness_response_paths(
    report: EvidenceGroundingFixedGoldsetRunReadinessReport,
) -> EvidenceGroundingFixedGoldsetRunReadinessReport:
    return EvidenceGroundingFixedGoldsetRunReadinessReport.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_threshold_calibration_response_paths(
    report: EvidenceGroundingThresholdCalibrationReport,
) -> EvidenceGroundingThresholdCalibrationReport:
    return EvidenceGroundingThresholdCalibrationReport.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_threshold_adoption_response_paths(
    report: EvidenceGroundingThresholdAdoptionReviewReport,
) -> EvidenceGroundingThresholdAdoptionReviewReport:
    return EvidenceGroundingThresholdAdoptionReviewReport.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_threshold_adoption_package_response_paths(
    package: EvidenceGroundingThresholdAdoptionReviewPackage,
) -> EvidenceGroundingThresholdAdoptionReviewPackage:
    return EvidenceGroundingThresholdAdoptionReviewPackage.model_validate(
        _mask_local_path_payload(package.model_dump(mode="json"))
    )


def _mask_roadmap_completion_response_paths(
    report: EvidenceGroundingRoadmapCompletionAuditReport,
) -> EvidenceGroundingRoadmapCompletionAuditReport:
    return EvidenceGroundingRoadmapCompletionAuditReport.model_validate(
        _mask_local_path_payload(report.model_dump(mode="json"))
    )


def _mask_local_path_payload(value: Any) -> Any:
    if isinstance(value, str):
        return mask_local_paths_in_text(value)
    if isinstance(value, list):
        return [_mask_local_path_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _mask_local_path_payload(item) for key, item in value.items()}
    return value


@router.post(
    "/fixed-goldset-run-readiness/audit",
    response_model=EvidenceGroundingFixedGoldsetRunReadinessReport,
)
async def audit_evidence_grounding_fixed_goldset_run_readiness(
    payload: EvidenceGroundingFixedGoldsetRunReadinessAuditRequest,
):
    try:
        report = build_evidence_grounding_fixed_goldset_run_readiness_report(
            goldset_manifest_path=Path(payload.goldset_manifest_path).expanduser().resolve(),
            baseline_run_root=Path(payload.baseline_run_root).expanduser().resolve(),
            candidate_run_root=Path(payload.candidate_run_root).expanduser().resolve(),
            readiness_id=payload.readiness_id,
            run_dir_template=payload.run_dir_template,
            baseline_run_dir_map=(
                load_evidence_grounding_benchmark_run_dir_map(
                    Path(payload.baseline_run_dir_map_path).expanduser().resolve()
                )
                if payload.baseline_run_dir_map_path
                else None
            ),
            candidate_run_dir_map=(
                load_evidence_grounding_benchmark_run_dir_map(
                    Path(payload.candidate_run_dir_map_path).expanduser().resolve()
                )
                if payload.candidate_run_dir_map_path
                else None
            ),
            required_artifacts=payload.required_artifacts,
            optional_artifacts=payload.optional_artifacts,
            require_ready=payload.require_ready,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_fixed_goldset_run_readiness_response_paths(report)
    except Exception as exc:
        logger.error("Failed to audit evidence-grounding fixed-goldset run readiness: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/threshold-adoption/review", response_model=EvidenceGroundingThresholdAdoptionReviewReport)
async def review_evidence_grounding_threshold_adoption(
    payload: EvidenceGroundingThresholdAdoptionReviewRequest,
):
    try:
        report = build_evidence_grounding_threshold_adoption_review_report(
            calibration_report_path=Path(payload.calibration_report_path).expanduser().resolve(),
            comparison_suite_path=(
                Path(payload.comparison_suite_path).expanduser().resolve() if payload.comparison_suite_path else None
            ),
            comparison_report_path=(
                Path(payload.comparison_report_path).expanduser().resolve() if payload.comparison_report_path else None
            ),
            run_readiness_report_path=(
                Path(payload.run_readiness_report_path).expanduser().resolve()
                if payload.run_readiness_report_path
                else None
            ),
            adoption_id=payload.adoption_id,
            required_metric_names=payload.required_metric_names,
            reviewer_approval_reference=payload.reviewer_approval_reference,
            allow_production_threshold_ready=payload.allow_production_threshold_ready,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_threshold_adoption_response_paths(report)
    except Exception as exc:
        logger.error("Failed to review evidence-grounding threshold adoption: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/threshold-adoption/review-from-comparison-suite",
    response_model=EvidenceGroundingThresholdAdoptionReviewReport,
)
async def review_evidence_grounding_threshold_adoption_from_comparison_suite(
    payload: EvidenceGroundingThresholdAdoptionReviewFromComparisonSuiteRequest,
):
    try:
        report = build_evidence_grounding_threshold_adoption_review_report_from_comparison_suite(
            comparison_suite_path=Path(payload.comparison_suite_path).expanduser().resolve(),
            calibration_report_out=Path(payload.calibration_report_out).expanduser().resolve(),
            threshold_checked_comparison_report_out=Path(
                payload.threshold_checked_comparison_report_out
            ).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve(),
            calibration_id=payload.calibration_id,
            calibration_metric_names=payload.calibration_metric_names,
            calibration_metric_preset=payload.calibration_metric_preset,
            include_baseline_report=payload.include_baseline_report,
            include_candidate_report=payload.include_candidate_report,
            tolerance=payload.tolerance,
            gate_metric_names=payload.gate_metric_names,
            gate_preset=payload.gate_preset,
            threshold_metric_values=payload.threshold_metric_values,
            adoption_id=payload.adoption_id,
            required_metric_names=payload.required_metric_names,
            reviewer_approval_reference=payload.reviewer_approval_reference,
            allow_production_threshold_ready=payload.allow_production_threshold_ready,
        )
        return _mask_threshold_adoption_response_paths(report)
    except Exception as exc:
        logger.error("Failed to review evidence-grounding threshold adoption from comparison suite: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/threshold-adoption/review-from-comparison-suite-package",
    response_model=EvidenceGroundingThresholdAdoptionReviewPackage,
)
async def review_evidence_grounding_threshold_adoption_from_comparison_suite_package(
    payload: EvidenceGroundingThresholdAdoptionReviewPackageFromComparisonSuitePackageRequest,
):
    try:
        package = build_evidence_grounding_threshold_adoption_review_package_from_comparison_suite_package(
            comparison_suite_package_path=Path(payload.comparison_suite_package_path).expanduser().resolve(),
            out_dir=Path(payload.out_dir).expanduser().resolve(),
            package_id=payload.package_id,
            calibration_report_out=(
                Path(payload.calibration_report_out).expanduser().resolve()
                if payload.calibration_report_out
                else None
            ),
            calibration_id=payload.calibration_id,
            calibration_metric_names=payload.calibration_metric_names,
            calibration_metric_preset=payload.calibration_metric_preset,
            include_baseline_report=payload.include_baseline_report,
            include_candidate_report=payload.include_candidate_report,
            tolerance=payload.tolerance,
            gate_metric_names=payload.gate_metric_names,
            gate_preset=payload.gate_preset,
            threshold_metric_values=payload.threshold_metric_values,
            adoption_id_prefix=payload.adoption_id_prefix,
            required_metric_names=payload.required_metric_names,
            reviewer_approval_reference=payload.reviewer_approval_reference,
            allow_production_threshold_ready=payload.allow_production_threshold_ready,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_threshold_adoption_package_response_paths(package)
    except Exception as exc:
        logger.error("Failed to review evidence-grounding threshold adoption from comparison suite package: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post("/roadmap-completion/audit", response_model=EvidenceGroundingRoadmapCompletionAuditReport)
async def audit_evidence_grounding_roadmap_completion(
    payload: EvidenceGroundingRoadmapCompletionAuditRequest,
):
    try:
        report = build_evidence_grounding_roadmap_completion_audit_report(
            audit_id=payload.audit_id,
            scorecard_path=Path(payload.scorecard_path).expanduser().resolve() if payload.scorecard_path else None,
            comparison_suite_path=(
                Path(payload.comparison_suite_path).expanduser().resolve() if payload.comparison_suite_path else None
            ),
            baseline_benchmark_report_path=(
                Path(payload.baseline_benchmark_report_path).expanduser().resolve()
                if payload.baseline_benchmark_report_path
                else None
            ),
            candidate_benchmark_report_path=(
                Path(payload.candidate_benchmark_report_path).expanduser().resolve()
                if payload.candidate_benchmark_report_path
                else None
            ),
            comparison_report_path=(
                Path(payload.comparison_report_path).expanduser().resolve()
                if payload.comparison_report_path
                else None
            ),
            run_readiness_report_path=(
                Path(payload.run_readiness_report_path).expanduser().resolve()
                if payload.run_readiness_report_path
                else None
            ),
            threshold_calibration_report_path=(
                Path(payload.threshold_calibration_report_path).expanduser().resolve()
                if payload.threshold_calibration_report_path
                else None
            ),
            threshold_adoption_review_path=(
                Path(payload.threshold_adoption_review_path).expanduser().resolve()
                if payload.threshold_adoption_review_path
                else None
            ),
            threshold_adoption_package_path=(
                Path(payload.threshold_adoption_package_path).expanduser().resolve()
                if payload.threshold_adoption_package_path
                else None
            ),
            contract_readiness_report_path=(
                Path(payload.contract_readiness_report_path).expanduser().resolve()
                if payload.contract_readiness_report_path
                else None
            ),
            gold_release_package_path=(
                Path(payload.gold_release_package_path).expanduser().resolve()
                if payload.gold_release_package_path
                else None
            ),
            gold_release_readiness_report_path=(
                Path(payload.gold_release_readiness_report_path).expanduser().resolve()
                if payload.gold_release_readiness_report_path
                else None
            ),
            correction_log_path=(
                Path(payload.correction_log_path).expanduser().resolve() if payload.correction_log_path else None
            ),
            additional_artifact_paths=[
                Path(path).expanduser().resolve() for path in payload.additional_artifact_paths
            ],
            goldset_root=Path(payload.goldset_root).expanduser().resolve() if payload.goldset_root else None,
            run_root=Path(payload.run_root).expanduser().resolve() if payload.run_root else None,
            required_ready_gold_count=payload.required_ready_gold_count,
            required_ready_run_count=payload.required_ready_run_count,
            inventory_required_artifacts=payload.inventory_required_artifacts,
            out=Path(payload.out).expanduser().resolve() if payload.out else None,
        )
        return _mask_roadmap_completion_response_paths(report)
    except Exception as exc:
        logger.error("Failed to audit evidence-grounding roadmap completion: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/roadmap-completion/audit-from-comparison-suite-package",
    response_model=EvidenceGroundingRoadmapCompletionAuditReport,
)
async def audit_evidence_grounding_roadmap_completion_from_comparison_suite_package(
    payload: EvidenceGroundingRoadmapCompletionAuditFromComparisonSuitePackageRequest,
):
    try:
        report = build_evidence_grounding_roadmap_completion_audit_report_from_comparison_suite_package(
            comparison_suite_path=Path(payload.comparison_suite_path).expanduser().resolve(),
            threshold_calibration_report_out=Path(payload.threshold_calibration_report_out).expanduser().resolve(),
            threshold_checked_comparison_report_out=Path(
                payload.threshold_checked_comparison_report_out
            ).expanduser().resolve(),
            threshold_adoption_review_out=Path(payload.threshold_adoption_review_out).expanduser().resolve(),
            contract_compatibility_report_out=Path(payload.contract_compatibility_report_out).expanduser().resolve(),
            contract_readiness_report_out=Path(payload.contract_readiness_report_out).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve(),
            audit_id=payload.audit_id,
            calibration_id=payload.calibration_id,
            calibration_metric_names=payload.calibration_metric_names,
            calibration_metric_preset=payload.calibration_metric_preset,
            include_baseline_report=payload.include_baseline_report,
            include_candidate_report=payload.include_candidate_report,
            tolerance=payload.tolerance,
            gate_metric_names=payload.gate_metric_names,
            gate_preset=payload.gate_preset,
            threshold_metric_values=payload.threshold_metric_values,
            adoption_id=payload.adoption_id,
            required_metric_names=payload.required_metric_names,
            threshold_reviewer_approval_reference=payload.threshold_reviewer_approval_reference,
            allow_production_threshold_ready=payload.allow_production_threshold_ready,
            compatibility_id=payload.compatibility_id,
            readiness_id=payload.readiness_id,
            include_embedded_scorecards=payload.include_embedded_scorecards,
            migration_plan_path=(
                Path(payload.migration_plan_path).expanduser().resolve() if payload.migration_plan_path else None
            ),
            backfill_plan_path=(
                Path(payload.backfill_plan_path).expanduser().resolve() if payload.backfill_plan_path else None
            ),
            public_contract_doc_path=(
                Path(payload.public_contract_doc_path).expanduser().resolve()
                if payload.public_contract_doc_path
                else None
            ),
            contract_reviewer_approval_reference=payload.contract_reviewer_approval_reference,
            allow_external_contract_ready=payload.allow_external_contract_ready,
            additional_artifact_paths=[
                Path(path).expanduser().resolve() for path in payload.additional_artifact_paths
            ],
            gold_release_goldset_id=payload.gold_release_goldset_id,
            gold_release_staged_split_manifests=payload.gold_release_staged_split_manifests,
            gold_release_split_plan_path=(
                Path(payload.gold_release_split_plan_path).expanduser().resolve()
                if payload.gold_release_split_plan_path
                else None
            ),
            gold_release_package_out=(
                Path(payload.gold_release_package_out).expanduser().resolve()
                if payload.gold_release_package_out
                else None
            ),
            gold_release_package_path=(
                Path(payload.gold_release_package_path).expanduser().resolve()
                if payload.gold_release_package_path
                else None
            ),
            gold_release_manifest_paths=(
                [Path(path).expanduser().resolve() for path in payload.gold_release_manifest_paths]
                if payload.gold_release_manifest_paths
                else None
            ),
            gold_release_readiness_report_out=(
                Path(payload.gold_release_readiness_report_out).expanduser().resolve()
                if payload.gold_release_readiness_report_out
                else None
            ),
            gold_release_readiness_report_path=(
                Path(payload.gold_release_readiness_report_path).expanduser().resolve()
                if payload.gold_release_readiness_report_path
                else None
            ),
            gold_release_required_splits=payload.gold_release_required_splits,
            gold_release_min_ready_per_split=payload.gold_release_min_ready_per_split,
            gold_release_require_single_goldset_id=payload.gold_release_require_single_goldset_id,
            correction_log_path=(
                Path(payload.correction_log_path).expanduser().resolve() if payload.correction_log_path else None
            ),
            goldset_root=Path(payload.goldset_root).expanduser().resolve() if payload.goldset_root else None,
            run_root=Path(payload.run_root).expanduser().resolve() if payload.run_root else None,
            required_ready_gold_count=payload.required_ready_gold_count,
            required_ready_run_count=payload.required_ready_run_count,
            inventory_required_artifacts=payload.inventory_required_artifacts,
        )
        return _mask_roadmap_completion_response_paths(report)
    except Exception as exc:
        logger.error("Failed to audit evidence-grounding roadmap completion from package: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc


@router.post(
    "/roadmap-completion/audit-from-threshold-adoption-package",
    response_model=EvidenceGroundingRoadmapCompletionAuditReport,
)
async def audit_evidence_grounding_roadmap_completion_from_threshold_adoption_package(
    payload: EvidenceGroundingRoadmapCompletionAuditFromThresholdAdoptionPackageRequest,
):
    try:
        report = build_evidence_grounding_roadmap_completion_audit_report_from_threshold_adoption_package(
            threshold_adoption_package_path=Path(payload.threshold_adoption_package_path).expanduser().resolve(),
            contract_compatibility_report_out=Path(payload.contract_compatibility_report_out).expanduser().resolve(),
            contract_readiness_report_out=Path(payload.contract_readiness_report_out).expanduser().resolve(),
            out=Path(payload.out).expanduser().resolve(),
            representative_split=payload.representative_split,
            audit_id=payload.audit_id,
            compatibility_id=payload.compatibility_id,
            readiness_id=payload.readiness_id,
            include_embedded_scorecards=payload.include_embedded_scorecards,
            migration_plan_path=(
                Path(payload.migration_plan_path).expanduser().resolve() if payload.migration_plan_path else None
            ),
            backfill_plan_path=(
                Path(payload.backfill_plan_path).expanduser().resolve() if payload.backfill_plan_path else None
            ),
            public_contract_doc_path=(
                Path(payload.public_contract_doc_path).expanduser().resolve()
                if payload.public_contract_doc_path
                else None
            ),
            contract_reviewer_approval_reference=payload.contract_reviewer_approval_reference,
            allow_external_contract_ready=payload.allow_external_contract_ready,
            additional_artifact_paths=[
                Path(path).expanduser().resolve() for path in payload.additional_artifact_paths
            ],
            gold_release_goldset_id=payload.gold_release_goldset_id,
            gold_release_staged_split_manifests=payload.gold_release_staged_split_manifests,
            gold_release_split_plan_path=(
                Path(payload.gold_release_split_plan_path).expanduser().resolve()
                if payload.gold_release_split_plan_path
                else None
            ),
            gold_release_package_out=(
                Path(payload.gold_release_package_out).expanduser().resolve()
                if payload.gold_release_package_out
                else None
            ),
            gold_release_package_path=(
                Path(payload.gold_release_package_path).expanduser().resolve()
                if payload.gold_release_package_path
                else None
            ),
            gold_release_manifest_paths=(
                [Path(path).expanduser().resolve() for path in payload.gold_release_manifest_paths]
                if payload.gold_release_manifest_paths
                else None
            ),
            gold_release_readiness_report_out=(
                Path(payload.gold_release_readiness_report_out).expanduser().resolve()
                if payload.gold_release_readiness_report_out
                else None
            ),
            gold_release_readiness_report_path=(
                Path(payload.gold_release_readiness_report_path).expanduser().resolve()
                if payload.gold_release_readiness_report_path
                else None
            ),
            gold_release_required_splits=payload.gold_release_required_splits,
            gold_release_min_ready_per_split=payload.gold_release_min_ready_per_split,
            gold_release_require_single_goldset_id=payload.gold_release_require_single_goldset_id,
            correction_log_path=(
                Path(payload.correction_log_path).expanduser().resolve() if payload.correction_log_path else None
            ),
            goldset_root=Path(payload.goldset_root).expanduser().resolve() if payload.goldset_root else None,
            run_root=Path(payload.run_root).expanduser().resolve() if payload.run_root else None,
            required_ready_gold_count=payload.required_ready_gold_count,
            required_ready_run_count=payload.required_ready_run_count,
            inventory_required_artifacts=payload.inventory_required_artifacts,
        )
        return _mask_roadmap_completion_response_paths(report)
    except Exception as exc:
        logger.error("Failed to audit evidence-grounding roadmap completion from threshold package: %s", _masked_error_detail(exc))
        raise HTTPException(status_code=500, detail=_masked_error_detail(exc)) from exc
