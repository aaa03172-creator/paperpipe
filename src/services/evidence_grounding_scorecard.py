from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from pydantic import ValidationError

from src.schemas.agent_artifacts import ClaimSet
from src.schemas.claim_evidence_correction import (
    ClaimEvidenceCorrectionCase,
    ClaimEvidenceCorrectionLocator,
    ClaimEvidenceCorrectionReviewedEvalFixture,
)
from src.schemas.claimset_coverage import ClaimsetCoverageSidecar
from src.schemas.deepread_handoff import DeepReadAcceptanceContract, DeepReadQualityGate
from src.schemas.evidence_extraction import EvidenceExtractionBundle
from src.schemas.evidence_grounding_scorecard import (
    EvidenceGroundingCandidateConfig,
    EvidenceGroundingGoldScoredMetrics,
    EvidenceGroundingInputArtifactDiagnostic,
    EvidenceGroundingInputArtifactStatus,
    EvidenceGroundingMetric,
    EvidenceGroundingRuntimeProxyMetrics,
    EvidenceGroundingScorecard,
    EvidenceGroundingScorecardRepairTarget,
    EvidenceGroundingScorecardStatus,
    EvidenceGroundingStageFailureSummary,
    EvidenceGroundingStageMetricSummary,
    KNOWN_EVIDENCE_GROUNDING_FAILURE_CODES,
)
from src.schemas.paper_understanding_gold import PaperUnderstandingGold
from src.schemas.paper_understanding_gold import (
    PaperUnderstandingGoldEvidenceLocator,
    PaperUnderstandingGoldMetadata,
    PaperUnderstandingGoldStatement,
)
from src.schemas.reader_eval import ReaderEvalSidecar
from src.schemas.visual_evidence import VisualEvidenceLedger
from src.services.evidence_grounding_gold_scoring import score_claimset_against_paper_understanding_gold_with_failures
from src.services.claim_evidence_corrections import load_claim_evidence_corrections
from src.skills.storage import atomic_write_text


_GOLD_REQUIRED_METRICS = (
    "claim_precision",
    "claim_recall",
    "evidence_support_precision",
    "locator_precision",
    "unsupported_claim_rate",
    "overstatement_rate",
    "contradiction_rate",
    "limitation_recall",
    "gap_recall",
    "method_result_confusion_rate",
    "figure_reference_precision",
    "table_reference_precision",
    "table_cell_locator_precision",
    "table_cell_value_accuracy",
    "figure_caption_link_accuracy",
    "figure_visual_text_accuracy",
    "metadata_match_rate",
    "parser_section_accuracy",
)

_CORE_INPUT_ARTIFACTS = (
    "reader_eval.json",
    "claimset_coverage.json",
    "evidence_extraction_bundle.json",
    "visual_evidence_ledger.json",
)


def build_evidence_grounding_scorecard(
    *,
    paper_id: str,
    doc_id: str,
    run_id: str,
    reader_eval: ReaderEvalSidecar | None = None,
    claimset_coverage: ClaimsetCoverageSidecar | None = None,
    evidence_extraction_bundle: EvidenceExtractionBundle | None = None,
    visual_evidence_ledger: VisualEvidenceLedger | None = None,
    deepread_acceptance_contract: DeepReadAcceptanceContract | None = None,
    deepread_quality_gate: DeepReadQualityGate | None = None,
    artifact_dir: Path | None = None,
    correction_cases: list[ClaimEvidenceCorrectionCase] | None = None,
    resolved_claimset: ClaimSet | None = None,
    paper_understanding_gold: PaperUnderstandingGold | None = None,
    paper_understanding_gold_source: str = "paper_understanding_gold.json",
    reviewed_eval_fixtures: list[ClaimEvidenceCorrectionReviewedEvalFixture] | None = None,
    document_artifact: Any | None = None,
    candidate_config: EvidenceGroundingCandidateConfig | None = None,
    candidate_config_source: str | None = None,
    source_artifacts: list[str] | None = None,
    input_artifact_diagnostics: list[EvidenceGroundingInputArtifactDiagnostic] | None = None,
    warnings: list[str] | None = None,
) -> EvidenceGroundingScorecard:
    source_artifacts = list(source_artifacts or [])
    warnings = list(warnings or [])
    reason_codes: list[str] = []
    if input_artifact_diagnostics is None:
        input_artifact_diagnostics = _core_input_artifact_diagnostics(
            reader_eval=reader_eval,
            claimset_coverage=claimset_coverage,
            evidence_extraction_bundle=evidence_extraction_bundle,
            visual_evidence_ledger=visual_evidence_ledger,
        )
    else:
        input_artifact_diagnostics = _reconcile_core_input_artifact_diagnostics(
            list(input_artifact_diagnostics),
            reader_eval=reader_eval,
            claimset_coverage=claimset_coverage,
            evidence_extraction_bundle=evidence_extraction_bundle,
            visual_evidence_ledger=visual_evidence_ledger,
        )
    if not _has_loaded_core_scorecard_input(
        reader_eval=reader_eval,
        claimset_coverage=claimset_coverage,
        evidence_extraction_bundle=evidence_extraction_bundle,
        visual_evidence_ledger=visual_evidence_ledger,
    ):
        raise ValueError(
            "scorecard requires at least one loadable core scorecard sidecar: "
            "reader_eval.json, claimset_coverage.json, evidence_extraction_bundle.json, "
            "or visual_evidence_ledger.json"
        )

    if reader_eval is None:
        warnings.append("reader_eval.json is missing; reader proxy metrics are not available")
        reason_codes.append("reader_eval_missing")
    else:
        source_artifacts.append("reader_eval.json")

    if claimset_coverage is None:
        warnings.append("claimset_coverage.json is missing; coverage proxy metrics are not available")
        reason_codes.append("claimset_coverage_missing")
    else:
        source_artifacts.append("claimset_coverage.json")
        reason_codes.extend(f"coverage_{code}" for code in claimset_coverage.reason_codes)

    if evidence_extraction_bundle is None:
        warnings.append("evidence_extraction_bundle.json is missing; extraction proxy metrics are not available")
        reason_codes.append("evidence_extraction_bundle_missing")
    else:
        source_artifacts.append("evidence_extraction_bundle.json")

    if visual_evidence_ledger is None:
        warnings.append("visual_evidence_ledger.json is missing; figure/table proxy metrics are not available")
        reason_codes.append("visual_evidence_ledger_missing")
    else:
        source_artifacts.append("visual_evidence_ledger.json")

    scorecard_candidate_config = candidate_config if candidate_config is not None and candidate_config.has_lineage() else None
    if scorecard_candidate_config is not None and candidate_config_source:
        source_artifacts.append(candidate_config_source)

    if deepread_acceptance_contract is not None:
        source_artifacts.append("acceptance_contract.json")
    if deepread_quality_gate is not None:
        source_artifacts.append("quality_gate.json")

    if resolved_claimset is not None:
        source_artifacts.append("claimset.resolved.json")
    if document_artifact is not None:
        source_artifacts.append("document_artifact.json")

    reviewed_eval_fixtures = _filter_reviewed_eval_fixtures_for_run(
        fixtures=list(reviewed_eval_fixtures or []),
        paper_id=paper_id,
        run_id=run_id,
        warnings=warnings,
        reason_codes=reason_codes,
    )
    runtime_proxy_metrics = _build_runtime_proxy_metrics(
        paper_id=paper_id,
        run_id=run_id,
        reader_eval=reader_eval,
        claimset_coverage=claimset_coverage,
        evidence_extraction_bundle=evidence_extraction_bundle,
        visual_evidence_ledger=visual_evidence_ledger,
        deepread_acceptance_contract=deepread_acceptance_contract,
        deepread_quality_gate=deepread_quality_gate,
        artifact_dir=artifact_dir,
        correction_cases=correction_cases,
        reviewed_eval_fixtures=reviewed_eval_fixtures,
        resolved_claimset=resolved_claimset,
        input_artifact_diagnostics=input_artifact_diagnostics,
        reason_codes=reason_codes,
    )
    failure_counts_by_code = _build_runtime_proxy_failure_counts(
        reader_eval=reader_eval,
        claimset_coverage=claimset_coverage,
        visual_evidence_ledger=visual_evidence_ledger,
        resolved_claimset=resolved_claimset,
    )
    gold_identity_mismatch = False
    scoring_paper_understanding_gold = paper_understanding_gold
    if paper_understanding_gold is not None and paper_understanding_gold.paper_id != paper_id:
        warnings.append(
            "paper_understanding_gold paper_id mismatch: "
            f"expected {paper_id}, got {paper_understanding_gold.paper_id}; gold metrics were not scored"
        )
        reason_codes.append("paper_understanding_gold_paper_id_mismatch")
        scoring_paper_understanding_gold = None
        gold_identity_mismatch = True

    reviewed_eval_gold = None
    if scoring_paper_understanding_gold is None and not gold_identity_mismatch and reviewed_eval_fixtures:
        reviewed_eval_gold = _paper_understanding_gold_from_reviewed_eval_fixtures(
            paper_id=paper_id,
            reviewed_eval_fixtures=reviewed_eval_fixtures,
        )

    scoring_gold = scoring_paper_understanding_gold or reviewed_eval_gold
    if scoring_gold is not None and resolved_claimset is not None:
        if scoring_paper_understanding_gold is not None:
            source_artifacts.append(paper_understanding_gold_source)
        else:
            source_artifacts.append("claim_evidence_reviewed_eval_fixtures.json")
        gold_score = score_claimset_against_paper_understanding_gold_with_failures(
            claimset=resolved_claimset,
            gold=scoring_gold,
        )
        gold_scored_metrics = gold_score.metrics
        table_value_metric, table_value_mismatch_count = _table_cell_value_accuracy(
            gold=scoring_gold,
            visual_evidence_ledger=visual_evidence_ledger,
        )
        figure_visual_metric, figure_visual_mismatch_count = _figure_visual_text_accuracy(
            gold=scoring_gold,
            visual_evidence_ledger=visual_evidence_ledger,
        )
        gold_scored_metrics.table_cell_value_accuracy = table_value_metric
        gold_scored_metrics.figure_visual_text_accuracy = figure_visual_metric
        if scoring_paper_understanding_gold is not None:
            gold_scored_metrics.metadata_match_rate = _metadata_match_rate(
                document_artifact=document_artifact,
                gold=scoring_paper_understanding_gold,
            )
            gold_scored_metrics.parser_section_accuracy = _parser_section_accuracy(
                document_artifact=document_artifact,
                gold=scoring_paper_understanding_gold,
            )
            if reviewed_eval_fixtures:
                _merge_reviewed_eval_consistency_metrics(
                    paper_id=paper_id,
                    resolved_claimset=resolved_claimset,
                    reviewed_eval_fixtures=reviewed_eval_fixtures,
                    gold_scored_metrics=gold_scored_metrics,
                    failure_counts_by_code=failure_counts_by_code,
                    source_artifacts=source_artifacts,
                    warnings=warnings,
                    reason_codes=reason_codes,
                )
        _merge_failure_counts(
            failure_counts_by_code,
            gold_score.failure_counts_by_code,
            replace_codes=set(gold_score.failure_counts_by_code) | {"MISSING_CLAIM", "GAP_MISSED"},
        )
        _increment(failure_counts_by_code, "TABLE_VALUE_MISMATCH", table_value_mismatch_count)
        _increment(failure_counts_by_code, "FIGURE_VISUAL_MISMATCH", figure_visual_mismatch_count)
        if (
            gold_scored_metrics.metadata_match_rate.status == "available"
            and gold_scored_metrics.metadata_match_rate.value < 1
        ):
            _increment(
                failure_counts_by_code,
                _metadata_failure_code(document_artifact=document_artifact, gold=scoring_paper_understanding_gold),
                1,
            )
        warnings.append(
            "gold-scored metrics are eval-only and use bounded matching; review borderline paraphrase cases manually"
        )
        if scoring_paper_understanding_gold is None:
            warnings.append(
                "gold-scored metrics used non-canonical reviewed claim/evidence correction fixtures"
            )
            reason_codes.append("reviewed_eval_fixture_metrics_scored")
        else:
            reason_codes.append("gold_metrics_scored")
    else:
        gold_scored_metrics = _build_missing_gold_metrics()
        if scoring_paper_understanding_gold is None and not reviewed_eval_fixtures and not gold_identity_mismatch:
            warnings.append(
                "gold labels are not attached; gold-scored precision/recall metrics are not_available"
            )
            reason_codes.append("gold_labels_missing")
            reason_codes.append("missing_p0_gold_metrics")
        if scoring_paper_understanding_gold is None and not gold_identity_mismatch and reviewed_eval_fixtures and resolved_claimset is None:
            warnings.append(
                "reviewed claim/evidence eval fixtures are present but claimset.resolved.json is missing"
            )
            reason_codes.append("reviewed_eval_fixture_claimset_missing")
        if scoring_gold is not None and resolved_claimset is None:
            warnings.append("paper_understanding_gold.json or reviewed eval fixtures are present but claimset.resolved.json is missing")
            reason_codes.append("gold_claimset_missing")

    _append_input_identity_diagnostics(
        reader_eval=reader_eval,
        claimset_coverage=claimset_coverage,
        evidence_extraction_bundle=evidence_extraction_bundle,
        visual_evidence_ledger=visual_evidence_ledger,
        warnings=warnings,
        reason_codes=reason_codes,
    )

    readiness_status = _readiness_status(
        reader_eval=reader_eval,
        claimset_coverage=claimset_coverage,
        reason_codes=reason_codes,
    )
    return EvidenceGroundingScorecard(
        generated_at=datetime.now(timezone.utc),
        paper_id=paper_id,
        doc_id=doc_id,
        run_id=run_id,
        source_artifacts=source_artifacts,
        input_artifact_diagnostics=input_artifact_diagnostics,
        readiness_status=readiness_status,
        runtime_proxy_metrics=runtime_proxy_metrics,
        gold_scored_metrics=gold_scored_metrics,
        stage_metric_summary=_build_stage_metric_summary(
            runtime_proxy_metrics=runtime_proxy_metrics,
            gold_scored_metrics=gold_scored_metrics,
        ),
        failure_counts_by_code=failure_counts_by_code,
        stage_failure_summary=_build_stage_failure_summary(failure_counts_by_code),
        warnings=warnings,
        reason_codes=reason_codes,
        repair_targets=_scorecard_repair_targets(resolved_claimset),
        recommended_next_action=_recommended_next_action(readiness_status),
        candidate_config=scorecard_candidate_config,
    )


def build_evidence_grounding_scorecard_from_run_dir(
    run_dir: Path,
    *,
    paper_understanding_gold: PaperUnderstandingGold | None = None,
    paper_understanding_gold_source: str | None = None,
    candidate_config: EvidenceGroundingCandidateConfig | None = None,
    candidate_config_source: str | None = None,
) -> EvidenceGroundingScorecard:
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise ValueError(f"run_dir must be an existing directory: {run_dir}")
    warnings: list[str] = []
    input_artifact_diagnostics: list[EvidenceGroundingInputArtifactDiagnostic] = []

    reader_eval = _load_optional_sidecar(
        run_dir / "reader_eval.json",
        ReaderEvalSidecar,
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
        core_scorecard_input=True,
    )
    claimset_coverage = _load_optional_sidecar(
        run_dir / "claimset_coverage.json",
        ClaimsetCoverageSidecar,
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
        core_scorecard_input=True,
    )
    evidence_extraction_bundle = _load_optional_sidecar(
        run_dir / "evidence_extraction_bundle.json",
        EvidenceExtractionBundle,
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
        core_scorecard_input=True,
    )
    visual_evidence_ledger = _load_optional_sidecar(
        run_dir / "visual_evidence_ledger.json",
        VisualEvidenceLedger,
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
        core_scorecard_input=True,
    )
    if not _has_loaded_core_scorecard_input(
        reader_eval=reader_eval,
        claimset_coverage=claimset_coverage,
        evidence_extraction_bundle=evidence_extraction_bundle,
        visual_evidence_ledger=visual_evidence_ledger,
    ):
        raise ValueError(
            "run_dir must contain at least one loadable core scorecard sidecar "
            f"(reader_eval.json, claimset_coverage.json, evidence_extraction_bundle.json, "
            f"or visual_evidence_ledger.json): {run_dir}"
        )
    deepread_acceptance_contract = _load_optional_sidecar(
        run_dir / "acceptance_contract.json",
        DeepReadAcceptanceContract,
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
    )
    deepread_quality_gate = _load_optional_sidecar(
        run_dir / "quality_gate.json",
        DeepReadQualityGate,
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
    )
    correction_cases = _load_optional_correction_cases(
        run_dir / "claim_evidence_corrections.jsonl",
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
    )
    resolved_claimset = _load_optional_sidecar(
        run_dir / "claimset.resolved.json",
        ClaimSet,
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
    )
    run_dir_paper_understanding_gold = _load_optional_sidecar(
        run_dir / "paper_understanding_gold.json",
        PaperUnderstandingGold,
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
    )
    scoring_paper_understanding_gold = paper_understanding_gold or run_dir_paper_understanding_gold
    scoring_paper_understanding_gold_source = (
        paper_understanding_gold_source
        if paper_understanding_gold is not None and paper_understanding_gold_source is not None
        else "paper_understanding_gold.json"
    )
    reviewed_eval_fixtures = _load_optional_reviewed_eval_fixtures(
        run_dir / "claim_evidence_reviewed_eval_fixtures.json",
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
    )
    run_dir_candidate_config = (
        None
        if candidate_config is not None
        else _load_optional_sidecar(
            run_dir / "candidate_config.json",
            EvidenceGroundingCandidateConfig,
            warnings=warnings,
            input_artifact_diagnostics=input_artifact_diagnostics,
        )
    )
    scoring_candidate_config = candidate_config or run_dir_candidate_config
    scoring_candidate_config_source = (
        candidate_config_source
        if candidate_config is not None and candidate_config_source is not None
        else "candidate_config.json"
        if candidate_config is None and run_dir_candidate_config is not None
        else None
    )
    document_artifact = _load_optional_json_dict(
        run_dir / "document_artifact.json",
        warnings=warnings,
        input_artifact_diagnostics=input_artifact_diagnostics,
    )
    paper_id, doc_id, run_id = _resolve_identity(
        run_dir=run_dir,
        reader_eval=reader_eval,
        claimset_coverage=claimset_coverage,
        evidence_extraction_bundle=evidence_extraction_bundle,
        visual_evidence_ledger=visual_evidence_ledger,
    )
    return build_evidence_grounding_scorecard(
        paper_id=paper_id,
        doc_id=doc_id,
        run_id=run_id,
        reader_eval=reader_eval,
        claimset_coverage=claimset_coverage,
        evidence_extraction_bundle=evidence_extraction_bundle,
        visual_evidence_ledger=visual_evidence_ledger,
        deepread_acceptance_contract=deepread_acceptance_contract,
        deepread_quality_gate=deepread_quality_gate,
        artifact_dir=run_dir,
        correction_cases=correction_cases,
        resolved_claimset=resolved_claimset,
        paper_understanding_gold=scoring_paper_understanding_gold,
        paper_understanding_gold_source=scoring_paper_understanding_gold_source,
        reviewed_eval_fixtures=reviewed_eval_fixtures,
        document_artifact=document_artifact,
        candidate_config=scoring_candidate_config,
        candidate_config_source=scoring_candidate_config_source,
        input_artifact_diagnostics=input_artifact_diagnostics,
        warnings=warnings,
    )


def write_evidence_grounding_scorecard(scorecard: EvidenceGroundingScorecard, artifact_dir: Path) -> Path:
    artifact_dir = Path(artifact_dir)
    if not artifact_dir.is_dir():
        raise ValueError(f"artifact_dir must be an existing directory: {artifact_dir}")
    path = artifact_dir / "evidence_grounding_scorecard.json"
    atomic_write_text(path, scorecard.model_dump_json(indent=2))
    return path


def write_evidence_grounding_scorecard_to_path(
    scorecard: EvidenceGroundingScorecard,
    out: Path,
    *,
    run_dir: Path,
) -> Path:
    out = Path(out)
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise ValueError(f"run_dir must be an existing directory: {run_dir}")
    if out.exists() and out.is_dir():
        raise ValueError(f"scorecard output path must be a file path, not a directory: {out}")
    if _is_nested_run_artifact_output_path(out, run_dir=run_dir):
        raise ValueError(
            "scorecard output path inside a run directory must be the top-level "
            f"evidence_grounding_scorecard.json artifact: {out}"
        )
    if _is_protected_run_artifact_output_path(out, run_dir=run_dir):
        raise ValueError(f"scorecard output path would overwrite a run source artifact: {out}")
    if _is_non_scorecard_run_artifact_output_path(out, run_dir=run_dir):
        raise ValueError(
            "scorecard output path inside a run directory must be "
            f"evidence_grounding_scorecard.json: {out}"
        )
    atomic_write_text(out, scorecard.model_dump_json(indent=2))
    return out


def _is_nested_run_artifact_output_path(out: Path, *, run_dir: Path) -> bool:
    try:
        relative = out.resolve().relative_to(run_dir.resolve())
    except ValueError:
        return False
    return len(relative.parts) != 1


def _is_protected_run_artifact_output_path(out: Path, *, run_dir: Path) -> bool:
    try:
        relative = out.resolve().relative_to(run_dir.resolve())
    except ValueError:
        return False
    if len(relative.parts) != 1:
        return False
    filename = relative.name
    return filename != "evidence_grounding_scorecard.json" and (run_dir / filename).exists()


def _is_non_scorecard_run_artifact_output_path(out: Path, *, run_dir: Path) -> bool:
    try:
        relative = out.resolve().relative_to(run_dir.resolve())
    except ValueError:
        return False
    if len(relative.parts) != 1:
        return False
    return relative.name != "evidence_grounding_scorecard.json"


def _build_runtime_proxy_metrics(
    *,
    paper_id: str,
    run_id: str,
    reader_eval: ReaderEvalSidecar | None,
    claimset_coverage: ClaimsetCoverageSidecar | None,
    evidence_extraction_bundle: EvidenceExtractionBundle | None,
    visual_evidence_ledger: VisualEvidenceLedger | None,
    deepread_acceptance_contract: DeepReadAcceptanceContract | None,
    deepread_quality_gate: DeepReadQualityGate | None,
    artifact_dir: Path | None,
    correction_cases: list[ClaimEvidenceCorrectionCase] | None,
    reviewed_eval_fixtures: list[ClaimEvidenceCorrectionReviewedEvalFixture],
    resolved_claimset: ClaimSet | None,
    input_artifact_diagnostics: list[EvidenceGroundingInputArtifactDiagnostic],
    reason_codes: list[str],
) -> EvidenceGroundingRuntimeProxyMetrics:
    metrics = EvidenceGroundingRuntimeProxyMetrics()
    input_presence = {
        "reader_eval.json": reader_eval is not None,
        "claimset_coverage.json": claimset_coverage is not None,
        "evidence_extraction_bundle.json": evidence_extraction_bundle is not None,
        "visual_evidence_ledger.json": visual_evidence_ledger is not None,
    }
    present_input_count = sum(1 for present in input_presence.values() if present)
    missing_input_count = len(_CORE_INPUT_ARTIFACTS) - present_input_count
    metrics.input_artifact_coverage_rate = _available(
        _ratio(present_input_count, len(_CORE_INPUT_ARTIFACTS)),
        source=" + ".join(_CORE_INPUT_ARTIFACTS),
        detail=(
            "Run-level proxy for whether the scorecard had its core grounding sidecars. "
            "It measures scorecard input completeness, not paper-understanding quality."
        ),
    )
    metrics.missing_input_artifact_count = _available(
        missing_input_count,
        source=" + ".join(_CORE_INPUT_ARTIFACTS),
        detail="Core scorecard sidecars missing from this run; lower is better.",
    )
    metrics.malformed_input_artifact_count = _available(
        sum(
            1
            for diagnostic in input_artifact_diagnostics
            if diagnostic.core_scorecard_input and diagnostic.status == "load_failed"
        ),
        source="input_artifact_diagnostics",
        detail="Core scorecard sidecars that existed but failed JSON/schema loading.",
    )
    if reader_eval is not None:
        reader = reader_eval.metrics
        claim_count = reader.claim_count
        evidence_span_count = reader.evidence_span_count
        metrics.claim_count = _available(claim_count, source="reader_eval.metrics.claim_count")
        metrics.evidence_span_count = _available(evidence_span_count, source="reader_eval.metrics.evidence_span_count")
        metrics.unresolved_grounding_rate = _available(
            _ratio(reader.unresolved_span_count, evidence_span_count),
            source="reader_eval.metrics.unresolved_span_count / evidence_span_count",
        )
        metrics.unsupported_claim_rate_proxy = _available(
            _ratio(reader.unsupported_claim_count, claim_count),
            source="reader_eval.metrics.unsupported_claim_count / claim_count",
            detail="Proxy only; true unsupported_claim_rate requires gold or human labels.",
        )
        metrics.unknown_claim_rate_proxy = _available(
            _ratio(reader.unknown_claim_count, claim_count),
            source="reader_eval.metrics.unknown_claim_count / claim_count",
            detail="Proxy only; unknown may include conservative downgrades.",
        )
        metrics.low_overlap_claim_rate = _available(
            _ratio(reader.low_overlap_claim_count, claim_count),
            source="reader_eval.metrics.low_overlap_claim_count / claim_count",
        )
        metrics.missing_location_claim_count = _available(
            sum(1 for claim in reader_eval.claims if claim.unknown_reason == "EVIDENCE_LOCATION_MISSING"),
            source="reader_eval.claims[].unknown_reason",
        )
        metrics.grounded_limitation_rate_proxy = _available(
            _ratio(reader.grounded_limitation_count, reader.limitation_count),
            source="reader_eval.metrics.grounded_limitation_count / limitation_count",
            detail="Proxy only; true limitation recall requires gold limitations.",
        )

    if claimset_coverage is not None:
        coverage = claimset_coverage.metrics
        metrics.grounded_evidence_ratio = _available(
            coverage.grounded_evidence_ratio,
            source="claimset_coverage.metrics.grounded_evidence_ratio",
        )
        metrics.page_coverage_ratio = _available(
            coverage.page_coverage_ratio,
            source="claimset_coverage.metrics.page_coverage_ratio",
        )
        metrics.missing_topic_signal_count = _available(
            coverage.missing_topic_signal_count,
            source="claimset_coverage.metrics.missing_topic_signal_count",
        )
        metrics.duplicate_cluster_count = _available(
            coverage.duplicate_cluster_count,
            source="claimset_coverage.metrics.duplicate_cluster_count",
        )
        if reader_eval is None:
            metrics.claim_count = _available(coverage.claim_count, source="claimset_coverage.metrics.claim_count")
            metrics.evidence_span_count = _available(
                coverage.evidence_span_count,
                source="claimset_coverage.metrics.evidence_span_count",
            )

    if evidence_extraction_bundle is not None:
        extraction = evidence_extraction_bundle.metrics
        metrics.evidence_extraction_record_count = _available(
            extraction.record_count,
            source="evidence_extraction_bundle.metrics.record_count",
        )
        metrics.evidence_backed_extraction_rate = _available(
            _ratio(extraction.evidence_backed_record_count, extraction.record_count),
            source="evidence_extraction_bundle.metrics.evidence_backed_record_count / record_count",
            detail="Proxy only; derived and artifact-backed records may still be useful but are not evidence-backed.",
        )
        metrics.grounded_extraction_ref_rate = _available(
            _ratio(extraction.grounded_evidence_ref_count, extraction.evidence_ref_count),
            source="evidence_extraction_bundle.metrics.grounded_evidence_ref_count / evidence_ref_count",
            detail="Proxy only; true evidence support precision requires gold or human labels.",
        )
    if visual_evidence_ledger is not None:
        visual = visual_evidence_ledger.metrics
        entry_count = visual.entry_count
        metrics.visual_evidence_entry_count = _available(
            entry_count,
            source="visual_evidence_ledger.metrics.entry_count",
        )
        metrics.visual_evidence_claim_link_rate = _available(
            _ratio(visual.linked_claim_count, entry_count),
            source="visual_evidence_ledger.metrics.linked_claim_count / entry_count",
            detail="Proxy only; linked visual entries may still require human/gold support validation.",
        )
        metrics.visual_evidence_unknown_rate = _available(
            _ratio(visual.unknown_count, entry_count),
            source="visual_evidence_ledger.metrics.unknown_count / entry_count",
        )
        metrics.visual_evidence_unsupported_rate = _available(
            _ratio(visual.unsupported_count, entry_count),
            source="visual_evidence_ledger.metrics.unsupported_count / entry_count",
        )
        metrics.visual_not_allowed_claim_count = _available(
            _visual_not_allowed_claim_count(visual_evidence_ledger),
            source="visual_evidence_ledger.entries[].not_allowed_claims",
            detail=(
                "Proxy only; counts visual evidence entries that explicitly warn against linked claims. "
                "These require review before visual claims are promoted."
            ),
        )
        metrics.visual_direct_contradiction_count = _available(
            _visual_direct_contradiction_count(
                visual_evidence_ledger=visual_evidence_ledger,
                resolved_claimset=resolved_claimset,
            ),
            source="visual_evidence_ledger.entries[].not_allowed_claims + claimset.resolved.json",
            detail=(
                "Bounded proxy only; counts direct polarity conflicts between linked claim text and "
                "visual not_allowed_claims."
            ),
        )
        metrics.caption_only_figure_count = _available(
            sum(
                1
                for entry in visual_evidence_ledger.entries
                if entry.figure_id is not None and entry.failure_reason == "caption_only"
            ),
            source="visual_evidence_ledger.entries[].failure_reason",
            detail="Caption-only figure links require visual review before visual claims are promoted.",
        )
        metrics.ambiguous_visual_panel_count = _available(
            _ambiguous_visual_panel_count(visual_evidence_ledger),
            source="visual_evidence_ledger.entries[].failure_reason",
            detail="Ambiguous visual panels require review before panel-specific claims are promoted.",
        )
        metrics.table_parse_failure_count = _available(
            sum(1 for entry in visual_evidence_ledger.entries if entry.failure_reason == "table_parse_failed"),
            source="visual_evidence_ledger.entries[].failure_reason",
        )
        metrics.table_cell_value_count = _available(
            sum(len(entry.extracted_values) for entry in visual_evidence_ledger.entries if entry.table_id),
            source="visual_evidence_ledger.entries[].extracted_values",
            detail="Parsed table-cell values are reusable locators, not proof of interpretation accuracy.",
        )
        metrics.figure_table_conflict_count = _available(
            _figure_table_conflict_count(visual_evidence_ledger),
            source="visual_evidence_ledger.entries[].failure_reason",
            detail="Figure/table discrepancy signals surfaced as explicit review conflicts.",
        )
    if resolved_claimset is not None:
        metrics.claim_evidence_direct_contradiction_count = _available(
            _claim_evidence_direct_contradiction_count(resolved_claimset),
            source="claimset.resolved.json claims[].statement + evidence_spans[].quote/raw_text/rationale",
            detail=(
                "Bounded proxy only; counts direct polarity conflicts between a claim statement and its linked "
                "evidence quote/raw_text/rationale. Requires review before treating the claim as contradicted."
            ),
        )
    if deepread_acceptance_contract is not None:
        expected_outputs = [
            output
            for output in deepread_acceptance_contract.expected_outputs
            if str(output or "").strip() and Path(str(output).strip()).name != "evidence_grounding_scorecard.json"
        ]
        present_outputs = sum(
            1
            for output in expected_outputs
            if artifact_dir is not None and (Path(artifact_dir) / output).exists()
        )
        traceability_detail = (
            "Proxy only; counts expected handoff outputs present in the run directory, excluding the "
            "scorecard output itself so stale self-output cannot inflate traceability. It does not prove "
            "semantic statement-level traceability."
        )
        metrics.downstream_traceability_rate = (
            _available(
                _ratio(present_outputs, len(expected_outputs)),
                source="acceptance_contract.expected_outputs + run_dir",
                detail=traceability_detail,
            )
            if expected_outputs
            else EvidenceGroundingMetric(
                status="not_available",
                source="acceptance_contract.expected_outputs + run_dir",
                detail=(
                    "No non-scorecard expected outputs remain after excluding evidence_grounding_scorecard.json; "
                    "traceability proxy is not available."
                ),
            )
        )
    if deepread_quality_gate is not None:
        metrics.handoff_review_ready = _available(
            1 if deepread_quality_gate.review_ready else 0,
            source="quality_gate.review_ready",
            detail="Binary proxy for whether deepread handoff is review-ready.",
        )
        checks = list(deepread_quality_gate.checks or [])
        if checks:
            metrics.handoff_check_pass_rate = _available(
                _ratio(sum(1 for check in checks if check.status == "pass"), len(checks)),
                source="quality_gate.checks[].status",
                detail="Proxy only; fraction of handoff quality gate checks with pass status.",
            )
        metrics.handoff_hard_fail_count = _available(
            len(deepread_quality_gate.hard_fail_codes),
            source="quality_gate.hard_fail_codes",
        )
    if correction_cases is not None:
        scoped_corrections = [
            correction
            for correction in correction_cases
            if correction.paper_id == paper_id and correction.run_id == run_id
        ]
        correction_count = len(scoped_corrections)
        accepted_count = sum(1 for correction in scoped_corrections if correction.accepted_for_eval)
        linked_count = sum(
            1
            for correction in scoped_corrections
            if correction.accepted_for_eval and correction.feedback_export_status == "linked"
        )
        if accepted_count > linked_count:
            reason_codes.append("accepted_corrections_not_replayable")
        metrics.review_burden_per_paper = _available(
            correction_count,
            source="claim_evidence_corrections.jsonl",
            detail="Human claim/evidence corrections recorded for this paper/run. Lower is better.",
        )
        metrics.accepted_correction_rate = _available(
            _ratio(accepted_count, correction_count),
            source="claim_evidence_corrections.accepted_for_eval / correction_count",
            detail="Proxy only; accepted corrections are reusable candidates, not accepted gold truth.",
        )
        metrics.correction_reuse_candidate_rate = _available(
            _ratio(accepted_count, correction_count),
            source="claim_evidence_corrections.accepted_for_eval / correction_count",
            detail="Proxy only; measures candidate reuse readiness, not measured downstream quality gain.",
        )
        metrics.correction_feedback_link_rate = _available(
            _ratio(linked_count, accepted_count),
            source="claim_evidence_corrections.feedback_export_status / accepted_for_eval",
            detail="Accepted corrections linked into feedback memory. Missing links can make review memory diverge.",
        )
    if reviewed_eval_fixtures:
        metrics.reviewed_eval_fixture_count = _available(
            len(reviewed_eval_fixtures),
            source="claim_evidence_reviewed_eval_fixtures.json",
            detail="Reviewed non-canonical eval fixtures packaged for scorecard/gold-like scoring.",
        )
    return metrics


def _scorecard_repair_targets(
    resolved_claimset: ClaimSet | None,
    *,
    limit: int = 10,
) -> list[EvidenceGroundingScorecardRepairTarget]:
    if resolved_claimset is None:
        return []
    targets: list[EvidenceGroundingScorecardRepairTarget] = []
    for claim in resolved_claimset.claims:
        for span_index, span in enumerate(claim.evidence_spans):
            resolution = str(span.resolution or "").strip() or None
            page = span.page if isinstance(span.page, int) and span.page >= 0 else None
            needs_repair = span.grounded is not True or page is None or resolution in {"FAILED_MATCH", "AMBIGUOUS_MATCH"}
            if not needs_repair:
                continue
            quote = str(span.quote or "")
            raw_text = str(span.raw_text or "")
            targets.append(
                EvidenceGroundingScorecardRepairTarget(
                    claim_id=claim.claim_id,
                    span_index=span_index,
                    resolution=resolution,
                    grounded=span.grounded,
                    page=page,
                    section=span.section,
                    chunk_id=span.chunk_id,
                    has_quote=bool(quote.strip()),
                    has_raw_text=bool(raw_text.strip()),
                    quote_char_count=len(quote.strip()),
                    raw_text_char_count=len(raw_text.strip()),
                )
            )
            if len(targets) >= limit:
                return targets
    return targets


def _build_runtime_proxy_failure_counts(
    *,
    reader_eval: ReaderEvalSidecar | None,
    claimset_coverage: ClaimsetCoverageSidecar | None,
    visual_evidence_ledger: VisualEvidenceLedger | None,
    resolved_claimset: ClaimSet | None,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    if reader_eval is not None:
        _increment(counts, "UNSUPPORTED_CLAIM", reader_eval.metrics.unsupported_claim_count)
        _increment(counts, "WEAK_OR_AMBIGUOUS_EVIDENCE", reader_eval.metrics.low_overlap_claim_count)
        _increment(
            counts,
            "WRONG_LOCATOR",
            sum(1 for claim in reader_eval.claims if claim.unknown_reason == "EVIDENCE_LOCATION_MISSING"),
        )
    if claimset_coverage is not None:
        _increment(counts, "MISSING_CLAIM", claimset_coverage.metrics.missing_topic_signal_count)
    if visual_evidence_ledger is not None:
        _increment(
            counts,
            "TABLE_PARSE_FAILED",
            sum(1 for entry in visual_evidence_ledger.entries if entry.failure_reason == "table_parse_failed"),
        )
        _increment(
            counts,
            "FIGURE_CAPTION_MISLINKED",
            sum(
                1
                for entry in visual_evidence_ledger.entries
                if entry.figure_id is not None and entry.failure_reason == "caption_only"
            ),
        )
        _increment(
            counts,
            "WEAK_OR_AMBIGUOUS_EVIDENCE",
            _ambiguous_visual_panel_count(visual_evidence_ledger),
        )
        _increment(
            counts,
            "OVERSTATED_RESULT",
            _visual_not_allowed_claim_count(visual_evidence_ledger),
        )
        _increment(
            counts,
            "CONTRADICTED_RESULT",
            _visual_direct_contradiction_count(
                visual_evidence_ledger=visual_evidence_ledger,
                resolved_claimset=resolved_claimset,
            ),
        )
    _increment(counts, "CONTRADICTED_RESULT", _claim_evidence_direct_contradiction_count(resolved_claimset))
    if visual_evidence_ledger is not None:
        _increment(
            counts,
            "FIGURE_TABLE_CONFLICT_MISSED",
            _figure_table_conflict_count(visual_evidence_ledger),
        )
    return counts


_FAILURE_STAGE_MAP: dict[str, tuple[str, str]] = {
    "MISSING_CLAIM": ("extractor", "Important paper content was not represented in the extracted claimset."),
    "UNSUPPORTED_CLAIM": ("grounding_checker", "A promoted claim lacks adequate source support."),
    "WRONG_EVIDENCE": ("grounding_checker", "A claim is linked to evidence that supports a different statement."),
    "WEAK_OR_AMBIGUOUS_EVIDENCE": ("grounding_checker", "Evidence support is weak, partial, or unresolved."),
    "WRONG_LOCATOR": ("grounding_checker", "Evidence locator metadata needs repair."),
    "OVERSTATED_RESULT": ("consistency_checker", "The statement is stronger than the evidence permits."),
    "CONTRADICTED_RESULT": ("consistency_checker", "A claim conflicts with paper-stated result evidence."),
    "METHOD_AS_RESULT": ("classifier", "A method/procedure was classified as a result."),
    "RESULT_AS_METHOD": ("classifier", "A measured result was classified as method context."),
    "LIMITATION_MISSED": ("consistency_checker", "A paper-stated limitation was not retained."),
    "GAP_MISSED": ("consistency_checker", "A stated future-work gap was not retained."),
    "TABLE_PARSE_FAILED": ("parser", "A needed table was not parsed into usable structure."),
    "TABLE_VALUE_MISMATCH": ("parser", "A parsed table cell value does not match gold evidence."),
    "FIGURE_CAPTION_MISLINKED": ("grounding_checker", "Figure/caption evidence was linked ambiguously or incorrectly."),
    "FIGURE_VISUAL_MISMATCH": ("grounding_checker", "Observed figure text or allowed claims do not match gold figure evidence."),
    "FIGURE_TABLE_CONFLICT_MISSED": ("consistency_checker", "A figure/table discrepancy was not surfaced."),
    "DOI_MISMATCH": ("metadata_resolver", "Paper identity metadata is inconsistent."),
    "METADATA_MISMATCH": ("metadata_resolver", "Paper title/author/year/PMID metadata is inconsistent."),
}
if set(_FAILURE_STAGE_MAP) != set(KNOWN_EVIDENCE_GROUNDING_FAILURE_CODES):
    missing = sorted(set(KNOWN_EVIDENCE_GROUNDING_FAILURE_CODES) - set(_FAILURE_STAGE_MAP))
    extra = sorted(set(_FAILURE_STAGE_MAP) - set(KNOWN_EVIDENCE_GROUNDING_FAILURE_CODES))
    raise RuntimeError(f"evidence_grounding_failure_taxonomy_mismatch missing={missing} extra={extra}")


_STAGE_RUNTIME_METRIC_MAP: dict[str, tuple[str, ...]] = {
    "unknown": (
        "input_artifact_coverage_rate",
        "missing_input_artifact_count",
        "malformed_input_artifact_count",
    ),
    "extractor": (
        "claim_count",
        "missing_topic_signal_count",
        "duplicate_cluster_count",
        "evidence_extraction_record_count",
        "evidence_backed_extraction_rate",
    ),
    "classifier": (),
    "grounding_checker": (
        "grounded_evidence_ratio",
        "unresolved_grounding_rate",
        "unsupported_claim_rate_proxy",
        "unknown_claim_rate_proxy",
        "low_overlap_claim_rate",
        "missing_location_claim_count",
        "grounded_extraction_ref_rate",
        "visual_evidence_claim_link_rate",
        "visual_evidence_unknown_rate",
        "visual_evidence_unsupported_rate",
        "ambiguous_visual_panel_count",
        "review_burden_per_paper",
        "accepted_correction_rate",
        "correction_reuse_candidate_rate",
        "correction_feedback_link_rate",
        "reviewed_eval_fixture_count",
    ),
    "consistency_checker": (
        "grounded_limitation_rate_proxy",
        "visual_not_allowed_claim_count",
        "visual_direct_contradiction_count",
        "claim_evidence_direct_contradiction_count",
        "figure_table_conflict_count",
    ),
    "parser": (
        "evidence_span_count",
        "page_coverage_ratio",
        "caption_only_figure_count",
        "table_parse_failure_count",
        "table_cell_value_count",
    ),
    "formatter": (
        "downstream_traceability_rate",
        "handoff_review_ready",
        "handoff_check_pass_rate",
        "handoff_hard_fail_count",
    ),
}

_STAGE_GOLD_METRIC_MAP: dict[str, tuple[str, ...]] = {
    "extractor": (
        "claim_precision",
        "claim_recall",
        "unsupported_claim_rate",
    ),
    "classifier": (
        "method_result_confusion_rate",
    ),
    "grounding_checker": (
        "evidence_support_precision",
        "locator_precision",
        "figure_reference_precision",
        "table_reference_precision",
        "table_cell_locator_precision",
        "table_cell_value_accuracy",
        "figure_caption_link_accuracy",
        "figure_visual_text_accuracy",
    ),
    "consistency_checker": (
        "overstatement_rate",
        "contradiction_rate",
        "limitation_recall",
        "gap_recall",
    ),
    "parser": (
        "table_cell_locator_precision",
        "table_cell_value_accuracy",
        "figure_caption_link_accuracy",
        "figure_visual_text_accuracy",
        "parser_section_accuracy",
    ),
    "metadata_resolver": (
        "metadata_match_rate",
    ),
    "formatter": (),
}

_STAGE_METRIC_DETAILS: dict[str, str] = {
    "unknown": "Run-level scorecard input completeness that is not attributable to one pipeline role.",
    "extractor": "Extraction-stage view of claim presence, duplicate/missing signal, and invention risk.",
    "classifier": "Classifier-stage view of method/result boundary quality when gold labels are available.",
    "grounding_checker": "Grounding-stage view of evidence support, locator, and visual evidence linkage quality.",
    "consistency_checker": "Consistency-stage view of limitation retention, overstatement, and contradiction risk.",
    "parser": "Parser-stage view of page/figure/table evidence availability and locator quality.",
    "metadata_resolver": "Metadata resolver-stage view of paper identity matching against gold labels.",
    "formatter": "Formatter-stage metrics are not available until downstream traceability artifacts are attached.",
}


def _build_stage_metric_summary(
    *,
    runtime_proxy_metrics: EvidenceGroundingRuntimeProxyMetrics,
    gold_scored_metrics: EvidenceGroundingGoldScoredMetrics,
) -> list[EvidenceGroundingStageMetricSummary]:
    summaries: list[EvidenceGroundingStageMetricSummary] = []
    for stage in sorted(set(_STAGE_RUNTIME_METRIC_MAP) | set(_STAGE_GOLD_METRIC_MAP)):
        runtime_metrics = {
            name: getattr(runtime_proxy_metrics, name)
            for name in _STAGE_RUNTIME_METRIC_MAP.get(stage, ())
            if hasattr(runtime_proxy_metrics, name)
        }
        gold_metrics = {
            name: getattr(gold_scored_metrics, name)
            for name in _STAGE_GOLD_METRIC_MAP.get(stage, ())
            if hasattr(gold_scored_metrics, name)
        }
        summary = EvidenceGroundingStageMetricSummary(
            stage=stage,  # type: ignore[arg-type]
            runtime_proxy_metrics=runtime_metrics,
            gold_scored_metrics=gold_metrics,
            detail=_STAGE_METRIC_DETAILS.get(stage),
        )
        if summary.available_metric_count > 0:
            summaries.append(summary)
    return summaries


def _build_stage_failure_summary(failure_counts_by_code: dict[str, int]) -> list[EvidenceGroundingStageFailureSummary]:
    stage_counts: dict[str, int] = {}
    stage_codes: dict[str, list[str]] = {}
    details: dict[str, list[str]] = {}
    for code, count in failure_counts_by_code.items():
        if count <= 0:
            continue
        stage, detail = _FAILURE_STAGE_MAP.get(code, ("unknown", "Failure code is not mapped to a pipeline stage."))
        stage_counts[stage] = stage_counts.get(stage, 0) + int(count)
        stage_codes.setdefault(stage, []).append(code)
        details.setdefault(stage, []).append(detail)
    return [
        EvidenceGroundingStageFailureSummary(
            stage=stage,  # type: ignore[arg-type]
            failure_count=stage_counts[stage],
            failure_codes=stage_codes[stage],
            detail=" ".join(dict.fromkeys(details[stage])),
        )
        for stage in sorted(stage_counts)
    ]


def _increment(counts: dict[str, int], code: str, value: int) -> None:
    if value <= 0:
        return
    counts[code] = int(counts.get(code, 0)) + int(value)


def _figure_table_conflict_count(visual_evidence_ledger: VisualEvidenceLedger) -> int:
    return sum(1 for entry in visual_evidence_ledger.entries if entry.failure_reason == "figure_table_conflict")


def _ambiguous_visual_panel_count(visual_evidence_ledger: VisualEvidenceLedger) -> int:
    return sum(1 for entry in visual_evidence_ledger.entries if entry.failure_reason == "ambiguous_panel")


def _visual_not_allowed_claim_count(visual_evidence_ledger: VisualEvidenceLedger) -> int:
    return sum(
        1
        for entry in visual_evidence_ledger.entries
        if entry.not_allowed_claims and entry.linked_claim_ids
        and entry.failure_reason != "figure_table_conflict"
    )


def _visual_direct_contradiction_count(
    *,
    visual_evidence_ledger: VisualEvidenceLedger,
    resolved_claimset: ClaimSet | None,
) -> int:
    if resolved_claimset is None:
        return 0
    claims_by_id = {claim.claim_id: claim for claim in resolved_claimset.claims}
    contradicted_claim_ids: set[str] = set()
    for entry in visual_evidence_ledger.entries:
        if entry.failure_reason == "figure_table_conflict":
            continue
        for claim_id in entry.linked_claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is None:
                continue
            if any(_direct_text_polarity_conflict(claim.statement, warning) for warning in entry.not_allowed_claims):
                contradicted_claim_ids.add(claim_id)
    return len(contradicted_claim_ids)


def _claim_evidence_direct_contradiction_count(resolved_claimset: ClaimSet | None) -> int:
    if resolved_claimset is None:
        return 0
    contradicted_claim_ids: set[str] = set()
    for claim in resolved_claimset.claims:
        for span in claim.evidence_spans:
            evidence_texts = [
                part.strip()
                for part in (
                    span.quote,
                    span.raw_text,
                    span.rationale,
                )
                if part and part.strip()
            ]
            if any(_direct_text_polarity_conflict(claim.statement, evidence_text) for evidence_text in evidence_texts):
                contradicted_claim_ids.add(claim.claim_id)
                break
    return len(contradicted_claim_ids)


def _direct_text_polarity_conflict(left: str, right: str) -> bool:
    if _core_token_jaccard(left, right) < 0.4:
        return False
    left_negated = _has_negation_signal(left)
    right_negated = _has_negation_signal(right)
    return left_negated != right_negated and (left_negated or right_negated)


def _core_token_jaccard(left: str, right: str) -> float:
    left_tokens = set(_tokens_without_negation(left))
    right_tokens = set(_tokens_without_negation(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _tokens_without_negation(text: str) -> list[str]:
    negation_tokens = {
        "no",
        "not",
        "neither",
        "nor",
        "without",
        "lack",
        "lacked",
        "lacking",
        "lacks",
        "fail",
        "failed",
        "fails",
        "failure",
        "absence",
        "absent",
        "unchanged",
        "insufficient",
        "non",
        "nonsignificant",
        "did",
        "does",
        "figure",
        "fig",
    }
    return [token for token in re.findall(r"[a-z0-9]+", str(text or "").lower()) if token not in negation_tokens]


def _has_negation_signal(text: str) -> bool:
    return bool(
        re.search(
            r"\b(no|not|neither|nor|without|lack(?:ed|ing|s)?|fail(?:ed|s|ure)?|"
            r"absence|absent|unchanged|insufficient)\b"
            r"|non[-\s]?significant",
            str(text or "").lower(),
        )
    )


def _table_cell_value_accuracy(
    *,
    gold: PaperUnderstandingGold,
    visual_evidence_ledger: VisualEvidenceLedger | None,
) -> tuple[EvidenceGroundingMetric, int]:
    gold_refs = [
        ref
        for statement in gold.iter_statements()
        for ref in statement.evidence_refs
        if ref.table_id and ref.cell_id and ref.quote
    ]
    if not gold_refs:
        return (
            EvidenceGroundingMetric(
                status="not_available",
                source="paper_understanding_gold.evidence_refs.table_id/cell_id/quote",
                detail="Requires gold evidence locators with table_id, cell_id, and quote.",
            ),
            0,
        )
    if visual_evidence_ledger is None:
        return (
            EvidenceGroundingMetric(
                status="not_available",
                source="paper_understanding_gold + visual_evidence_ledger",
                detail="Requires visual_evidence_ledger.json extracted table-cell values.",
            ),
            0,
        )

    matched_count = sum(
        1
        for ref in gold_refs
        if any(
            _visual_extracted_value_matches_gold_ref(value, ref)
            for entry in visual_evidence_ledger.entries
            for value in entry.extracted_values
        )
    )
    mismatch_count = len(gold_refs) - matched_count
    return (
        _available(
            _ratio(matched_count, len(gold_refs)),
            source="paper_understanding_gold.evidence_refs + visual_evidence_ledger.entries[].extracted_values",
            detail=(
                "Eval-only semantic table check. Counts exact table/cell matches whose extracted value "
                "covers the gold quote."
            ),
        ),
        mismatch_count,
    )


def _visual_extracted_value_matches_gold_ref(value: Any, ref: PaperUnderstandingGoldEvidenceLocator) -> bool:
    table_id = _clean_identifier(getattr(value, "table_id", None)).lower()
    cell_id = _clean_identifier(getattr(value, "cell_id", None)).lower()
    if table_id != _clean_identifier(ref.table_id).lower():
        return False
    if cell_id != _clean_identifier(ref.cell_id).lower():
        return False
    extracted_value = _clean_text(getattr(value, "value", ""))
    if not extracted_value:
        return False
    return _query_coverage(ref.quote, extracted_value) >= 0.8 or _query_coverage(extracted_value, ref.quote) >= 0.8


def _figure_visual_text_accuracy(
    *,
    gold: PaperUnderstandingGold,
    visual_evidence_ledger: VisualEvidenceLedger | None,
) -> tuple[EvidenceGroundingMetric, int]:
    gold_refs = [
        ref
        for statement in gold.iter_statements()
        for ref in statement.evidence_refs
        if ref.figure_id and ref.quote
    ]
    if not gold_refs:
        return (
            EvidenceGroundingMetric(
                status="not_available",
                source="paper_understanding_gold.evidence_refs.figure_id/quote",
                detail="Requires gold evidence locators with figure_id and quote.",
            ),
            0,
        )
    if visual_evidence_ledger is None:
        return (
            EvidenceGroundingMetric(
                status="not_available",
                source="paper_understanding_gold + visual_evidence_ledger",
                detail="Requires visual_evidence_ledger.json figure observations.",
            ),
            0,
        )

    evaluable_refs = [
        ref
        for ref in gold_refs
        if any(_visual_entry_matches_figure_ref(entry, ref) for entry in visual_evidence_ledger.entries)
    ]
    if not evaluable_refs:
        return (
            EvidenceGroundingMetric(
                status="not_available",
                source="paper_understanding_gold.evidence_refs + visual_evidence_ledger.entries[]",
                detail="Requires a visual evidence entry with the same figure_id as the gold figure locator.",
            ),
            0,
        )

    matched_count = sum(
        1
        for ref in evaluable_refs
        if any(_visual_entry_text_supports_figure_ref(entry, ref) for entry in visual_evidence_ledger.entries)
    )
    mismatch_count = len(evaluable_refs) - matched_count
    return (
        _available(
            _ratio(matched_count, len(evaluable_refs)),
            source="paper_understanding_gold.evidence_refs + visual_evidence_ledger.entries[].caption/observed_text/allowed_claims",
            detail=(
                "Eval-only bounded figure visual text check. Counts matching figure entries whose observed "
                "text or allowed claims cover the gold figure evidence quote."
            ),
        ),
        mismatch_count,
    )


def _visual_entry_matches_figure_ref(entry: Any, ref: PaperUnderstandingGoldEvidenceLocator) -> bool:
    return _normalize_visual_id(getattr(entry, "figure_id", None)) == _normalize_visual_id(ref.figure_id)


def _visual_entry_text_supports_figure_ref(entry: Any, ref: PaperUnderstandingGoldEvidenceLocator) -> bool:
    if not _visual_entry_matches_figure_ref(entry, ref):
        return False
    text_parts: list[str] = []
    text_parts.append(_clean_text(getattr(entry, "caption", "")))
    for field_name in ("observed_text", "allowed_claims", "observed_elements"):
        values = getattr(entry, field_name, []) or []
        text_parts.extend(_clean_text(value) for value in values)
    combined = _clean_text(" ".join(text_parts))
    if not combined:
        return False
    return _query_coverage(ref.quote, combined) >= 0.8


def _normalize_visual_id(value: Any) -> str:
    text = _clean_identifier(value).lower()
    text = re.sub(r"\b(fig|figure)\b", "", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _merge_failure_counts(target: dict[str, int], source: dict[str, int], *, replace_codes: set[str] | None = None) -> None:
    replace_codes = replace_codes or set()
    for code in replace_codes:
        target.pop(code, None)
    for code, count in source.items():
        _increment(target, code, int(count))


def _merge_reviewed_eval_consistency_metrics(
    *,
    paper_id: str,
    resolved_claimset: ClaimSet,
    reviewed_eval_fixtures: list[ClaimEvidenceCorrectionReviewedEvalFixture],
    gold_scored_metrics: EvidenceGroundingGoldScoredMetrics,
    failure_counts_by_code: dict[str, int],
    source_artifacts: list[str],
    warnings: list[str],
    reason_codes: list[str],
) -> None:
    reviewed_eval_gold = _paper_understanding_gold_from_reviewed_eval_fixtures(
        paper_id=paper_id,
        reviewed_eval_fixtures=reviewed_eval_fixtures,
    )
    if reviewed_eval_gold is None:
        return
    reviewed_score = score_claimset_against_paper_understanding_gold_with_failures(
        claimset=resolved_claimset,
        gold=reviewed_eval_gold,
    )
    merged_metrics: list[str] = []
    for metric_name, failure_code in (
        ("overstatement_rate", "OVERSTATED_RESULT"),
        ("contradiction_rate", "CONTRADICTED_RESULT"),
    ):
        current_metric = getattr(gold_scored_metrics, metric_name)
        reviewed_metric = getattr(reviewed_score.metrics, metric_name)
        if current_metric.status == "available" or reviewed_metric.status != "available":
            continue
        setattr(
            gold_scored_metrics,
            metric_name,
            reviewed_metric.model_copy(
                update={
                    "source": "paper_understanding_gold + claim_evidence_reviewed_eval_fixtures.json + claimset.resolved",
                    "detail": (
                        "Filled from non-canonical reviewed claim/evidence correction fixtures because "
                        f"paper_understanding_gold lacked explicit {failure_code} review labels."
                    ),
                }
            ),
        )
        reviewed_count = reviewed_score.failure_counts_by_code.get(failure_code, 0)
        if reviewed_count > failure_counts_by_code.get(failure_code, 0):
            failure_counts_by_code[failure_code] = reviewed_count
        merged_metrics.append(metric_name)
    if not merged_metrics:
        return
    source_artifacts.append("claim_evidence_reviewed_eval_fixtures.json")
    warnings.append(
        "consistency metrics used non-canonical reviewed claim/evidence correction fixtures"
    )
    reason_codes.append("reviewed_eval_fixture_consistency_metrics_scored")


def _metadata_match_rate(*, document_artifact: Any | None, gold: PaperUnderstandingGold) -> EvidenceGroundingMetric:
    if document_artifact is None:
        return EvidenceGroundingMetric(
            status="not_available",
            source="document_artifact.metadata + paper_understanding_gold.citation",
            detail="Requires document_artifact.json and paper_understanding_gold.json.",
        )
    document_metadata = _extract_document_metadata(document_artifact)
    if not document_metadata:
        return EvidenceGroundingMetric(
            status="not_available",
            source="document_artifact.metadata + paper_understanding_gold.citation",
            detail="document_artifact.json did not contain recognizable metadata/meta fields.",
        )

    comparable: list[bool] = []
    comparable.append(
        _title_matches(
            _clean_text(document_metadata.get("title")),
            _clean_text(gold.citation.title),
        )
    )
    if gold.citation.doi:
        comparable.append(_normalize_doi(document_metadata.get("doi")) == _normalize_doi(gold.citation.doi))
    if gold.citation.pmid:
        comparable.append(_clean_identifier(document_metadata.get("pmid")) == _clean_identifier(gold.citation.pmid))
    if gold.citation.year is not None:
        comparable.append(_coerce_year(document_metadata.get("year")) == gold.citation.year)
    if gold.citation.authors:
        comparable.append(_authors_match(document_metadata.get("authors"), gold.citation.authors))

    return _available(
        _ratio(sum(1 for value in comparable if value), len(comparable)),
        source="document_artifact.metadata + paper_understanding_gold.citation",
        detail="Gold-scored paper identity match over title plus available DOI, PMID, year, and authors.",
    )


def _metadata_failure_code(*, document_artifact: Any | None, gold: PaperUnderstandingGold | None) -> str:
    if document_artifact is None or gold is None:
        return "METADATA_MISMATCH"
    document_metadata = _extract_document_metadata(document_artifact)
    if gold.citation.doi and document_metadata.get("doi"):
        if _normalize_doi(document_metadata.get("doi")) != _normalize_doi(gold.citation.doi):
            return "DOI_MISMATCH"
    return "METADATA_MISMATCH"


def _parser_section_accuracy(*, document_artifact: Any | None, gold: PaperUnderstandingGold) -> EvidenceGroundingMetric:
    if document_artifact is None:
        return EvidenceGroundingMetric(
            status="not_available",
            source="document_artifact.sections + paper_understanding_gold.evidence_refs.section",
            detail="Requires document_artifact.json and gold evidence section labels.",
        )
    sections = _extract_document_sections(document_artifact)
    if not sections:
        return EvidenceGroundingMetric(
            status="not_available",
            source="document_artifact.sections + paper_understanding_gold.evidence_refs.section",
            detail="document_artifact.json did not contain section text.",
        )
    section_refs = [
        ref
        for statement in gold.iter_statements()
        for ref in statement.evidence_refs
        if _clean_text(ref.section)
    ]
    if not section_refs:
        return EvidenceGroundingMetric(
            status="not_available",
            source="document_artifact.sections + paper_understanding_gold.evidence_refs.section",
            detail="Requires gold evidence locators with section labels.",
        )
    correct = sum(1 for ref in section_refs if _section_ref_matches_document(ref, sections))
    return _available(
        _ratio(correct, len(section_refs)),
        source="document_artifact.sections + paper_understanding_gold.evidence_refs.section",
        detail="Gold-scored section accuracy for evidence locators with explicit section labels.",
    )


def _extract_document_metadata(document_artifact: Any) -> dict[str, Any]:
    if hasattr(document_artifact, "model_dump"):
        try:
            document_artifact = document_artifact.model_dump()
        except (TypeError, ValueError):
            return {}
    if not isinstance(document_artifact, dict):
        return {}
    for field_name in ("metadata", "meta"):
        metadata = document_artifact.get(field_name)
        if isinstance(metadata, dict):
            return metadata
    return {}


def _extract_document_sections(document_artifact: Any) -> list[dict[str, Any]]:
    if hasattr(document_artifact, "model_dump"):
        try:
            document_artifact = document_artifact.model_dump()
        except (TypeError, ValueError):
            return []
    if not isinstance(document_artifact, dict):
        return []
    sections = document_artifact.get("sections")
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, dict) and _clean_text(section.get("text"))]


def _section_ref_matches_document(
    ref: PaperUnderstandingGoldEvidenceLocator,
    sections: list[dict[str, Any]],
) -> bool:
    expected_label = _normalize_section_label(ref.section)
    if not expected_label:
        return False
    candidates = [
        section
        for section in sections
        if _normalize_section_label(section.get("name") or section.get("section") or section.get("title"))
        == expected_label
    ]
    if not candidates:
        return False
    for section in candidates:
        section_text = _clean_text(section.get("text"))
        if ref.quote:
            if _query_coverage(ref.quote, section_text) >= 0.8:
                return True
            continue
        if ref.page is not None and _section_contains_page(section, ref.page):
            return True
    return False


def _section_contains_page(section: dict[str, Any], page: int) -> bool:
    page_start = _coerce_int(section.get("page_start"))
    page_end = _coerce_int(section.get("page_end"))
    if page_start is None and page_end is None:
        return False
    if page_start is None:
        page_start = page_end
    if page_end is None:
        page_end = page_start
    return page_start <= page <= page_end


def _normalize_section_label(value: Any) -> str:
    text = _clean_text(value).lower()
    if not text:
        return ""
    tokens = re.findall(r"[a-z0-9]+", text)
    normalized = " ".join(tokens)
    aliases = {
        "materials and methods": "methods",
        "method": "methods",
        "methods": "methods",
        "results": "results",
        "result": "results",
        "discussion": "discussion",
        "limitations": "discussion",
        "limitation": "discussion",
        "conclusion": "discussion",
        "conclusions": "discussion",
        "abstract": "abstract",
        "introduction": "introduction",
        "background": "introduction",
    }
    return aliases.get(normalized, normalized)


def _title_matches(system_title: str, gold_title: str) -> bool:
    if not system_title or not gold_title:
        return False
    return _text_overlap(system_title, gold_title) >= 0.85


def _authors_match(system_authors: Any, gold_authors: list[str]) -> bool:
    system_names = _normalized_author_names(system_authors)
    gold_names = _normalized_author_names(gold_authors)
    if not system_names or not gold_names:
        return False
    return bool(set(system_names) & set(gold_names))


def _normalized_author_names(raw_authors: Any) -> list[str]:
    if not isinstance(raw_authors, list):
        return []
    names: list[str] = []
    for raw in raw_authors:
        if isinstance(raw, dict):
            raw = raw.get("name")
        name = _clean_text(raw)
        if not name:
            continue
        names.append(" ".join(re.findall(r"[a-z0-9]+", name.lower())))
    return [name for name in names if name]


def _normalize_doi(value: Any) -> str:
    text = _clean_identifier(value).lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.strip()


def _clean_identifier(value: Any) -> str:
    return str(value or "").strip()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _coerce_year(value: Any) -> int | None:
    year = _coerce_int(value)
    return year if year is not None and year > 0 else None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text_overlap(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"[a-z0-9]+", left.lower()))
    right_tokens = set(re.findall(r"[a-z0-9]+", right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _query_coverage(query: str, target: str) -> float:
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    target_tokens = set(re.findall(r"[a-z0-9]+", target.lower()))
    if not query_tokens or not target_tokens:
        return 0.0
    return len(query_tokens & target_tokens) / len(query_tokens)


def _build_missing_gold_metrics() -> EvidenceGroundingGoldScoredMetrics:
    metrics = EvidenceGroundingGoldScoredMetrics()
    for name in _GOLD_REQUIRED_METRICS:
        setattr(
            metrics,
            name,
            EvidenceGroundingMetric(
                status="not_available",
                source="gold_labels",
                detail="Requires gold or structured human review labels.",
            ),
        )
    return metrics


def _core_input_artifact_diagnostics(
    *,
    reader_eval: ReaderEvalSidecar | None,
    claimset_coverage: ClaimsetCoverageSidecar | None,
    evidence_extraction_bundle: EvidenceExtractionBundle | None,
    visual_evidence_ledger: VisualEvidenceLedger | None,
) -> list[EvidenceGroundingInputArtifactDiagnostic]:
    inputs = {
        "reader_eval.json": reader_eval,
        "claimset_coverage.json": claimset_coverage,
        "evidence_extraction_bundle.json": evidence_extraction_bundle,
        "visual_evidence_ledger.json": visual_evidence_ledger,
    }
    return [
        EvidenceGroundingInputArtifactDiagnostic(
            artifact=artifact,
            status="loaded" if value is not None else "missing",
            core_scorecard_input=True,
        )
        for artifact, value in inputs.items()
    ]


def _reconcile_core_input_artifact_diagnostics(
    diagnostics: list[EvidenceGroundingInputArtifactDiagnostic],
    *,
    reader_eval: ReaderEvalSidecar | None,
    claimset_coverage: ClaimsetCoverageSidecar | None,
    evidence_extraction_bundle: EvidenceExtractionBundle | None,
    visual_evidence_ledger: VisualEvidenceLedger | None,
) -> list[EvidenceGroundingInputArtifactDiagnostic]:
    core_diagnostics = {
        diagnostic.artifact: diagnostic
        for diagnostic in _core_input_artifact_diagnostics(
            reader_eval=reader_eval,
            claimset_coverage=claimset_coverage,
            evidence_extraction_bundle=evidence_extraction_bundle,
            visual_evidence_ledger=visual_evidence_ledger,
        )
    }
    existing_core_diagnostics = {
        diagnostic.artifact: diagnostic
        for diagnostic in diagnostics
        if diagnostic.artifact in _CORE_INPUT_ARTIFACTS
    }
    for artifact, existing in existing_core_diagnostics.items():
        if core_diagnostics[artifact].status != "loaded" and existing.status == "load_failed":
            core_diagnostics[artifact] = existing
    non_core_diagnostics = [
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.artifact not in _CORE_INPUT_ARTIFACTS
    ]
    return [core_diagnostics[artifact] for artifact in _CORE_INPUT_ARTIFACTS] + non_core_diagnostics


def _has_loaded_core_scorecard_input(
    *,
    reader_eval: ReaderEvalSidecar | None,
    claimset_coverage: ClaimsetCoverageSidecar | None,
    evidence_extraction_bundle: EvidenceExtractionBundle | None,
    visual_evidence_ledger: VisualEvidenceLedger | None,
) -> bool:
    return any(
        value is not None
        for value in (
            reader_eval,
            claimset_coverage,
            evidence_extraction_bundle,
            visual_evidence_ledger,
        )
    )


def _append_input_artifact_diagnostic(
    diagnostics: list[EvidenceGroundingInputArtifactDiagnostic] | None,
    *,
    path: Path,
    status: EvidenceGroundingInputArtifactStatus,
    core_scorecard_input: bool,
    detail: str | None = None,
) -> None:
    if diagnostics is None:
        return
    diagnostics.append(
        EvidenceGroundingInputArtifactDiagnostic(
            artifact=path.name,
            status=status,
            core_scorecard_input=core_scorecard_input,
            detail=detail,
        )
    )


def _diagnostic_error_detail(exc: Exception) -> str:
    return exc.__class__.__name__


def _load_optional_reviewed_eval_fixtures(
    path: Path,
    *,
    warnings: list[str],
    input_artifact_diagnostics: list[EvidenceGroundingInputArtifactDiagnostic] | None = None,
) -> list[ClaimEvidenceCorrectionReviewedEvalFixture]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            raw_items = payload
        elif isinstance(payload, dict) and isinstance(payload.get("fixtures"), list):
            raw_items = payload["fixtures"]
        elif isinstance(payload, dict):
            raw_items = [payload]
        else:
            warnings.append(f"{path.name} could not be loaded: expected object, list, or fixtures list")
            _append_input_artifact_diagnostic(
                input_artifact_diagnostics,
                path=path,
                status="load_failed",
                core_scorecard_input=False,
                detail="TypeError",
            )
            return []
        fixtures = [
            item
            for item in (
                ClaimEvidenceCorrectionReviewedEvalFixture.model_validate(raw_item)
                for raw_item in raw_items
            )
            if item.canonical_status == "non_canonical"
        ]
        if len(fixtures) != len(raw_items):
            warnings.append(f"{path.name} skipped reviewed fixtures without non_canonical status")
        _append_input_artifact_diagnostic(
            input_artifact_diagnostics,
            path=path,
            status="loaded",
            core_scorecard_input=False,
        )
        return fixtures
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        warnings.append(f"{path.name} could not be loaded: {exc}")
        _append_input_artifact_diagnostic(
            input_artifact_diagnostics,
            path=path,
            status="load_failed",
            core_scorecard_input=False,
            detail=_diagnostic_error_detail(exc),
        )
        return []


def _load_optional_correction_cases(
    path: Path,
    *,
    warnings: list[str],
    input_artifact_diagnostics: list[EvidenceGroundingInputArtifactDiagnostic] | None = None,
) -> list[ClaimEvidenceCorrectionCase] | None:
    if not path.exists():
        return None
    try:
        cases = load_claim_evidence_corrections(log_path=path)
        _append_input_artifact_diagnostic(
            input_artifact_diagnostics,
            path=path,
            status="loaded",
            core_scorecard_input=False,
        )
        return cases
    except (OSError, ValueError) as exc:
        warnings.append(f"{path.name} could not be loaded: {exc}")
        _append_input_artifact_diagnostic(
            input_artifact_diagnostics,
            path=path,
            status="load_failed",
            core_scorecard_input=False,
            detail=_diagnostic_error_detail(exc),
        )
        return None


def _paper_understanding_gold_from_reviewed_eval_fixtures(
    *,
    paper_id: str,
    reviewed_eval_fixtures: list[ClaimEvidenceCorrectionReviewedEvalFixture],
) -> PaperUnderstandingGold | None:
    statements: list[PaperUnderstandingGoldStatement] = []
    for fixture in reviewed_eval_fixtures:
        candidate = fixture.source_candidate
        evidence_refs = [
            _gold_locator_from_correction_locator(locator)
            for locator in candidate.after_evidence_refs
            if _correction_locator_has_signal(locator)
        ]
        if not evidence_refs:
            continue
        statements.append(
            PaperUnderstandingGoldStatement(
                statement_id=f"reviewed-{candidate.source_correction_id}",
                kind="claim",
                text=candidate.after_claim_text,
                evidence_refs=evidence_refs,
                review_failure_codes=candidate.reason_codes,
            )
        )
    if not statements:
        return None
    return PaperUnderstandingGold(
        paper_id=paper_id,
        citation=PaperUnderstandingGoldMetadata(title="Reviewed claim/evidence correction eval fixtures"),
        paper_type="other",
        domain_tags=["claim_evidence_correction_review"],
        gold_claims=statements,
    )


def _filter_reviewed_eval_fixtures_for_run(
    *,
    fixtures: list[ClaimEvidenceCorrectionReviewedEvalFixture],
    paper_id: str,
    run_id: str,
    warnings: list[str],
    reason_codes: list[str],
) -> list[ClaimEvidenceCorrectionReviewedEvalFixture]:
    if not fixtures:
        return []
    scoped: list[ClaimEvidenceCorrectionReviewedEvalFixture] = []
    skipped = 0
    skipped_paper_ids: set[str] = set()
    skipped_run_ids: set[str] = set()
    for fixture in fixtures:
        candidate = fixture.source_candidate
        if candidate.paper_id == paper_id and candidate.run_id == run_id:
            scoped.append(fixture)
            continue
        skipped += 1
        skipped_paper_ids.add(candidate.paper_id)
        skipped_run_ids.add(candidate.run_id)
    if skipped:
        warnings.append(
            "reviewed eval fixtures skipped outside run scope: "
            f"{skipped}; expected paper_id={paper_id},run_id={run_id}; "
            f"got paper_ids={','.join(sorted(skipped_paper_ids))},run_ids={','.join(sorted(skipped_run_ids))}"
        )
        reason_codes.append("reviewed_eval_fixture_scope_mismatch")
    return scoped


def _gold_locator_from_correction_locator(
    locator: ClaimEvidenceCorrectionLocator,
) -> PaperUnderstandingGoldEvidenceLocator:
    return PaperUnderstandingGoldEvidenceLocator(
        page=locator.page,
        chunk_id=locator.chunk_id,
        char_start=locator.char_start,
        char_end=locator.char_end,
        quote=locator.quote or locator.rationale or "reviewed correction evidence",
        section=locator.section,
        figure_id=locator.figure_id,
        table_id=locator.table_id,
        cell_id=locator.cell_id,
        bbox_pdf=locator.bbox_pdf,
        bbox_pct=locator.bbox_pct,
    )


def _correction_locator_has_signal(locator: ClaimEvidenceCorrectionLocator) -> bool:
    return bool(
        locator.page is not None
        or locator.chunk_id
        or locator.quote
        or locator.figure_id
        or locator.table_id
        or locator.cell_id
        or locator.bbox_pdf
        or locator.bbox_pct
    )


def _load_optional_sidecar(
    path: Path,
    model: type[Any],
    *,
    warnings: list[str],
    input_artifact_diagnostics: list[EvidenceGroundingInputArtifactDiagnostic] | None = None,
    core_scorecard_input: bool = False,
) -> Any | None:
    if not path.exists():
        if core_scorecard_input:
            _append_input_artifact_diagnostic(
                input_artifact_diagnostics,
                path=path,
                status="missing",
                core_scorecard_input=True,
            )
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        sidecar = model.model_validate(payload)
        _append_input_artifact_diagnostic(
            input_artifact_diagnostics,
            path=path,
            status="loaded",
            core_scorecard_input=core_scorecard_input,
        )
        return sidecar
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        warnings.append(f"{path.name} could not be loaded: {exc}")
        _append_input_artifact_diagnostic(
            input_artifact_diagnostics,
            path=path,
            status="load_failed",
            core_scorecard_input=core_scorecard_input,
            detail=_diagnostic_error_detail(exc),
        )
        return None


def _load_optional_json_dict(
    path: Path,
    *,
    warnings: list[str],
    input_artifact_diagnostics: list[EvidenceGroundingInputArtifactDiagnostic] | None = None,
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"{path.name} could not be loaded: {exc}")
        _append_input_artifact_diagnostic(
            input_artifact_diagnostics,
            path=path,
            status="load_failed",
            core_scorecard_input=False,
            detail=_diagnostic_error_detail(exc),
        )
        return None
    if not isinstance(payload, dict):
        warnings.append(f"{path.name} could not be loaded: expected JSON object")
        _append_input_artifact_diagnostic(
            input_artifact_diagnostics,
            path=path,
            status="load_failed",
            core_scorecard_input=False,
            detail="TypeError",
        )
        return None
    _append_input_artifact_diagnostic(
        input_artifact_diagnostics,
        path=path,
        status="loaded",
        core_scorecard_input=False,
    )
    return payload


def _resolve_identity(
    *,
    run_dir: Path,
    reader_eval: ReaderEvalSidecar | None,
    claimset_coverage: ClaimsetCoverageSidecar | None,
    evidence_extraction_bundle: EvidenceExtractionBundle | None,
    visual_evidence_ledger: VisualEvidenceLedger | None,
) -> tuple[str, str, str]:
    for sidecar in (reader_eval, claimset_coverage, evidence_extraction_bundle):
        if sidecar is not None:
            return sidecar.paper_id, sidecar.doc_id, sidecar.run_id
    if visual_evidence_ledger is not None:
        return visual_evidence_ledger.paper_id, "unknown_doc", visual_evidence_ledger.run_id
    return run_dir.parent.name or "unknown_paper", "unknown_doc", run_dir.name or "unknown_run"


def _append_input_identity_diagnostics(
    *,
    reader_eval: ReaderEvalSidecar | None,
    claimset_coverage: ClaimsetCoverageSidecar | None,
    evidence_extraction_bundle: EvidenceExtractionBundle | None,
    visual_evidence_ledger: VisualEvidenceLedger | None,
    warnings: list[str],
    reason_codes: list[str],
) -> None:
    identity_sources = _input_identity_sources(
        reader_eval=reader_eval,
        claimset_coverage=claimset_coverage,
        evidence_extraction_bundle=evidence_extraction_bundle,
        visual_evidence_ledger=visual_evidence_ledger,
    )
    paper_ids = {value for _, field_name, value in identity_sources if field_name == "paper_id"}
    run_ids = {value for _, field_name, value in identity_sources if field_name == "run_id"}
    doc_ids = {value for _, field_name, value in identity_sources if field_name == "doc_id"}
    if len(paper_ids) > 1:
        warnings.append(f"input sidecar paper_id mismatch: {','.join(sorted(paper_ids))}")
        warnings.append(
            "input sidecar paper_id mismatch sources: "
            f"{_format_identity_source_details(identity_sources, field_name='paper_id')}"
        )
        reason_codes.append("input_paper_id_mismatch")
    if len(run_ids) > 1:
        warnings.append(f"input sidecar run_id mismatch: {','.join(sorted(run_ids))}")
        warnings.append(
            "input sidecar run_id mismatch sources: "
            f"{_format_identity_source_details(identity_sources, field_name='run_id')}"
        )
        reason_codes.append("input_run_id_mismatch")
    if len(doc_ids) > 1:
        warnings.append(f"input sidecar doc_id mismatch: {','.join(sorted(doc_ids))}")
        warnings.append(
            "input sidecar doc_id mismatch sources: "
            f"{_format_identity_source_details(identity_sources, field_name='doc_id')}"
        )
        reason_codes.append("input_doc_id_mismatch")


def _input_identity_sources(
    *,
    reader_eval: ReaderEvalSidecar | None,
    claimset_coverage: ClaimsetCoverageSidecar | None,
    evidence_extraction_bundle: EvidenceExtractionBundle | None,
    visual_evidence_ledger: VisualEvidenceLedger | None,
) -> list[tuple[str, str, str]]:
    sources: list[tuple[str, str, str]] = []
    for artifact_name, sidecar, field_names in (
        ("reader_eval.json", reader_eval, ("paper_id", "run_id", "doc_id")),
        ("claimset_coverage.json", claimset_coverage, ("paper_id", "run_id", "doc_id")),
        ("evidence_extraction_bundle.json", evidence_extraction_bundle, ("paper_id", "run_id", "doc_id")),
        ("visual_evidence_ledger.json", visual_evidence_ledger, ("paper_id", "run_id")),
    ):
        if sidecar is None:
            continue
        for field_name in field_names:
            value = str(getattr(sidecar, field_name, "") or "").strip()
            if value:
                sources.append((artifact_name, field_name, value))
    return sources


def _format_identity_source_details(
    identity_sources: list[tuple[str, str, str]],
    *,
    field_name: str,
) -> str:
    details = [
        f"{artifact_name}={value}"
        for artifact_name, source_field_name, value in identity_sources
        if source_field_name == field_name
    ]
    return ";".join(details) if details else "-"


def _available(value: float | int, *, source: str, detail: str | None = None) -> EvidenceGroundingMetric:
    return EvidenceGroundingMetric(value=value, status="available", source=source, detail=detail)


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _readiness_status(
    *,
    reader_eval: ReaderEvalSidecar | None,
    claimset_coverage: ClaimsetCoverageSidecar | None,
    reason_codes: list[str],
) -> EvidenceGroundingScorecardStatus:
    if any(
        code in reason_codes
        for code in (
            "input_paper_id_mismatch",
            "input_run_id_mismatch",
            "input_doc_id_mismatch",
            "paper_understanding_gold_paper_id_mismatch",
            "reviewed_eval_fixture_scope_mismatch",
        )
    ):
        return "fail"
    if reader_eval is None and claimset_coverage is None:
        return "fail"
    if claimset_coverage is not None and claimset_coverage.coverage_status == "fail":
        return "fail"
    if any(
        code in reason_codes
        for code in (
            "reader_eval_missing",
            "claimset_coverage_missing",
            "evidence_extraction_bundle_missing",
            "visual_evidence_ledger_missing",
            "missing_p0_gold_metrics",
            "accepted_corrections_not_replayable",
        )
    ):
        return "warn"
    if claimset_coverage is not None and claimset_coverage.coverage_status == "warn":
        return "warn"
    if reader_eval is not None and (
        reader_eval.metrics.unresolved_span_count > 0
        or reader_eval.metrics.ambiguous_span_count > 0
        or reader_eval.metrics.failed_grounding_span_count > 0
    ):
        return "warn"
    return "pass"


def _recommended_next_action(status: EvidenceGroundingScorecardStatus) -> str:
    if status == "pass":
        return "none"
    if status == "warn":
        return "review_proxy_warnings_before_promotion"
    return "rerun_or_review_deepread_artifacts"
