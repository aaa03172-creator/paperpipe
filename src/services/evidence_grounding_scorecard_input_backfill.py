from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.schemas.agent_artifacts import ClaimSet, DocumentArtifact, IndexArtifact
from src.schemas.evidence_grounding_benchmark import (
    EvidenceGroundingBenchmarkManifest,
    EvidenceGroundingBenchmarkManifestItem,
    EvidenceGroundingBenchmarkManifestPackage,
)
from src.schemas.evidence_grounding_scorecard import (
    EvidenceGroundingMetric,
    EvidenceGroundingScorecard,
    EvidenceGroundingScorecardInputBackfillItem,
    EvidenceGroundingScorecardInputBackfillItemRequest,
    EvidenceGroundingScorecardInputBackfillReport,
)
from src.schemas.paper_understanding_gold import PaperUnderstandingGold
from src.services.citation_grounding import resolve_claimset_grounding
from src.services.claim_evidence_corrections import (
    load_claim_evidence_reviewed_eval_fixtures,
    write_claim_evidence_reviewed_eval_fixtures_sidecar,
)
from src.services.claimset_coverage_sidecar import build_claimset_coverage_sidecar, write_claimset_coverage_sidecar
from src.services.evidence_extraction_sidecar import build_evidence_extraction_bundle, write_evidence_extraction_bundle
from src.services.evidence_grounding_scorecard import (
    build_evidence_grounding_scorecard_from_run_dir,
    write_evidence_grounding_scorecard,
)
from src.services.reader_eval_sidecar import build_reader_eval_sidecar, write_reader_eval_sidecar
from src.services.visual_evidence_ledger import build_visual_evidence_ledger, write_visual_evidence_ledger
from src.skills.storage import atomic_write_text


def build_evidence_grounding_scorecard_input_backfill_report(
    *,
    items: list[EvidenceGroundingScorecardInputBackfillItemRequest],
    out_run_root: Path,
    reviewed_fixtures_dir: Path | None = None,
    require_reviewed_fixtures: bool = False,
    overwrite: bool = False,
    write_scorecards: bool = True,
    out: Path | None = None,
    run_dir_map_out: Path | None = None,
) -> EvidenceGroundingScorecardInputBackfillReport:
    out_run_root = Path(out_run_root).expanduser().resolve()
    reviewed_fixtures_dir = Path(reviewed_fixtures_dir).expanduser().resolve() if reviewed_fixtures_dir else None
    run_dir_map_out = Path(run_dir_map_out).expanduser().resolve() if run_dir_map_out else None
    out_run_root.mkdir(parents=True, exist_ok=True)
    report_items: list[EvidenceGroundingScorecardInputBackfillItem] = []
    warnings: list[str] = []
    seen_outputs: set[Path] = set()
    for item in items:
        source_run_dir = Path(item.source_run_dir).expanduser().resolve()
        output_run_dir = (out_run_root / (item.output_name or item.paper_id)).resolve()
        if not _is_relative_to(output_run_dir, out_run_root) or output_run_dir == out_run_root:
            report_items.append(
                _failed_item(
                    item,
                    source_run_dir=source_run_dir,
                    output_run_dir=output_run_dir,
                    error="output_run_dir_outside_out_run_root",
                )
            )
            continue
        if output_run_dir in seen_outputs:
            report_items.append(
                _failed_item(
                    item,
                    source_run_dir=source_run_dir,
                    output_run_dir=output_run_dir,
                    error="duplicate_output_run_dir",
                )
            )
            continue
        seen_outputs.add(output_run_dir)
        try:
            report_items.append(
                _backfill_one_item(
                    item,
                    source_run_dir=source_run_dir,
                    output_run_dir=output_run_dir,
                    reviewed_fixtures_dir=reviewed_fixtures_dir,
                    require_reviewed_fixtures=require_reviewed_fixtures,
                    overwrite=overwrite,
                    write_scorecards=write_scorecards,
                )
            )
        except Exception as exc:
            report_items.append(
                _failed_item(
                    item,
                    source_run_dir=source_run_dir,
                    output_run_dir=output_run_dir,
                    error=str(exc),
                )
            )
    if any(item.status == "fail" for item in report_items):
        warnings.append("scorecard_input_backfill_failures_present")
    if any(item.scorecard_readiness_status == "fail" for item in report_items):
        warnings.append("scorecard_input_backfill_scorecard_failures_present")
    report = EvidenceGroundingScorecardInputBackfillReport(
        generated_at=datetime.now(timezone.utc),
        out_run_root=str(out_run_root),
        run_dir_map_path=str(run_dir_map_out) if run_dir_map_out else None,
        reviewed_fixtures_dir=str(reviewed_fixtures_dir) if reviewed_fixtures_dir else None,
        items=report_items,
        warnings=warnings,
    )
    if run_dir_map_out is not None:
        write_scorecard_input_backfill_run_dir_map(report, run_dir_map_out)
    if out is not None:
        atomic_write_text(Path(out).expanduser().resolve(), report.model_dump_json(indent=2))
    return report


def write_scorecard_input_backfill_run_dir_map(
    report: EvidenceGroundingScorecardInputBackfillReport,
    out: Path,
) -> Path:
    out = Path(out).expanduser().resolve()
    run_dir_map: dict[str, str] = {}
    for item in report.items:
        if item.status != "pass":
            continue
        if item.paper_id in run_dir_map:
            raise ValueError(f"duplicate_paper_id_in_scorecard_input_backfill_run_dir_map: {item.paper_id}")
        run_dir_map[item.paper_id] = item.output_run_dir
    atomic_write_text(out, json.dumps(run_dir_map, indent=2, sort_keys=True))
    return out


def load_scorecard_input_backfill_items_from_benchmark_artifacts(
    *,
    benchmark_manifest_paths: list[Path] | None = None,
    benchmark_manifest_package_paths: list[Path] | None = None,
) -> list[EvidenceGroundingScorecardInputBackfillItemRequest]:
    items: list[EvidenceGroundingScorecardInputBackfillItemRequest] = []
    for manifest_path in benchmark_manifest_paths or []:
        path = Path(manifest_path).expanduser().resolve()
        manifest = EvidenceGroundingBenchmarkManifest.model_validate_json(path.read_text(encoding="utf-8"))
        items.extend(_backfill_items_from_benchmark_manifest(manifest, base_dir=path.parent))
    for package_path in benchmark_manifest_package_paths or []:
        path = Path(package_path).expanduser().resolve()
        package = EvidenceGroundingBenchmarkManifestPackage.model_validate_json(path.read_text(encoding="utf-8"))
        manifest_base_dirs = _manifest_base_dirs_from_package(package, package_path=path)
        package_out_dir = _package_out_dir_from_package(package, package_path=path)
        if package.benchmark_manifests:
            for index, manifest in enumerate(package.benchmark_manifests):
                base_dir = manifest_base_dirs[index] if index < len(manifest_base_dirs) else package_out_dir
                items.extend(_backfill_items_from_benchmark_manifest(manifest, base_dir=base_dir))
            continue
        for raw_manifest_path in package.benchmark_manifest_paths:
            manifest_path = Path(raw_manifest_path).expanduser()
            if not manifest_path.is_absolute():
                manifest_path = path.parent / manifest_path
            manifest_path = manifest_path.resolve()
            manifest = EvidenceGroundingBenchmarkManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
            items.extend(_backfill_items_from_benchmark_manifest(manifest, base_dir=manifest_path.parent))
    return items


def _manifest_base_dirs_from_package(
    package: EvidenceGroundingBenchmarkManifestPackage,
    *,
    package_path: Path,
) -> list[Path]:
    base_dirs: list[Path] = []
    for raw_manifest_path in package.benchmark_manifest_paths:
        manifest_path = Path(raw_manifest_path).expanduser()
        if not manifest_path.is_absolute():
            manifest_path = package_path.parent / manifest_path
        base_dirs.append(manifest_path.resolve().parent)
    return base_dirs


def _package_out_dir_from_package(
    package: EvidenceGroundingBenchmarkManifestPackage,
    *,
    package_path: Path,
) -> Path:
    out_dir = Path(package.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = package_path.parent / out_dir
    return out_dir.resolve()


def _backfill_items_from_benchmark_manifest(
    manifest: EvidenceGroundingBenchmarkManifest,
    *,
    base_dir: Path,
) -> list[EvidenceGroundingScorecardInputBackfillItemRequest]:
    return [
        _backfill_item_from_benchmark_manifest_item(item, base_dir=base_dir)
        for item in manifest.items
    ]


def _backfill_item_from_benchmark_manifest_item(
    item: EvidenceGroundingBenchmarkManifestItem,
    *,
    base_dir: Path,
) -> EvidenceGroundingScorecardInputBackfillItemRequest:
    run_dir = Path(item.run_dir).expanduser()
    if not run_dir.is_absolute():
        run_dir = base_dir / run_dir
    paper_understanding_gold_path = _metadata_source_gold_path(item.metadata, base_dir=base_dir)
    return EvidenceGroundingScorecardInputBackfillItemRequest(
        paper_id=item.paper_id or item.candidate_id,
        source_run_dir=str(run_dir.resolve()),
        paper_understanding_gold_path=str(paper_understanding_gold_path) if paper_understanding_gold_path else None,
        run_id=item.run_id,
        output_name=item.candidate_id,
    )


def _metadata_source_gold_path(metadata: dict, *, base_dir: Path) -> Path | None:
    raw_path = metadata.get("source_gold_path")
    if not isinstance(raw_path, str):
        return None
    raw_path = raw_path.strip()
    if not raw_path:
        return None
    gold_path = Path(raw_path).expanduser()
    if not gold_path.is_absolute():
        gold_path = base_dir / gold_path
    return gold_path.resolve()


def _backfill_one_item(
    item: EvidenceGroundingScorecardInputBackfillItemRequest,
    *,
    source_run_dir: Path,
    output_run_dir: Path,
    reviewed_fixtures_dir: Path | None,
    require_reviewed_fixtures: bool,
    overwrite: bool,
    write_scorecards: bool,
) -> EvidenceGroundingScorecardInputBackfillItem:
    if not source_run_dir.is_dir():
        raise ValueError(f"source_run_dir_not_found: {source_run_dir}")
    if reviewed_fixtures_dir is not None and not reviewed_fixtures_dir.is_dir():
        raise ValueError(f"reviewed_fixtures_dir_not_found: {reviewed_fixtures_dir}")
    if source_run_dir == output_run_dir:
        raise ValueError("in_place_backfill_is_not_supported")
    if output_run_dir.exists():
        if not overwrite:
            raise ValueError(f"output_run_dir_exists: {output_run_dir}")
        shutil.rmtree(output_run_dir)
    output_run_dir.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copytree(source_run_dir, output_run_dir)
        run_id = item.run_id or source_run_dir.name
        document_artifact = _load_document_artifact(output_run_dir / "document_artifact.json")
        index_artifact = IndexArtifact.model_validate_json(
            (output_run_dir / "index_artifact.json").read_text(encoding="utf-8")
        )
        claimset = _load_claimset_for_scorecard_input_backfill(output_run_dir / "claimset.json")
        resolved_claimset = resolve_claimset_grounding(
            claimset,
            index_artifact,
            document_artifact=document_artifact if isinstance(document_artifact, DocumentArtifactV2) else None,
        )
        generated_artifacts: list[str] = []
        if item.paper_understanding_gold_path:
            _copy_paper_understanding_gold_input(
                Path(item.paper_understanding_gold_path).expanduser().resolve(),
                output_run_dir=output_run_dir,
            )
            generated_artifacts.append("paper_understanding_gold.json")
        (output_run_dir / "claimset.resolved.json").write_text(
            resolved_claimset.model_dump_json(indent=2),
            encoding="utf-8",
        )
        generated_artifacts.append("claimset.resolved.json")
        visual_evidence = build_visual_evidence_ledger(
            paper_id=item.paper_id,
            run_id=run_id,
            document_artifact=document_artifact,
            resolved_claimset=resolved_claimset,
        )
        write_visual_evidence_ledger(visual_evidence, output_run_dir)
        generated_artifacts.append("visual_evidence_ledger.json")
        claimset_coverage = build_claimset_coverage_sidecar(
            paper_id=item.paper_id,
            run_id=run_id,
            document_artifact=document_artifact,
            index_artifact=index_artifact,
            resolved_claimset=resolved_claimset,
            doc_id=resolved_claimset.doc_id,
        )
        write_claimset_coverage_sidecar(claimset_coverage, output_run_dir)
        generated_artifacts.append("claimset_coverage.json")
        reader_eval = build_reader_eval_sidecar(
            paper_id=item.paper_id,
            run_id=run_id,
            claimset=claimset,
            resolved_claimset=resolved_claimset,
            index_artifact=index_artifact,
        )
        write_reader_eval_sidecar(reader_eval, output_run_dir)
        generated_artifacts.append("reader_eval.json")
        evidence_extraction = build_evidence_extraction_bundle(
            paper_id=item.paper_id,
            run_id=run_id,
            resolved_claimset=resolved_claimset,
        )
        write_evidence_extraction_bundle(evidence_extraction, output_run_dir)
        generated_artifacts.append("evidence_extraction_bundle.json")

        reviewed_eval_fixture_count: int | None = None
        if reviewed_fixtures_dir is not None:
            reviewed_fixtures = load_claim_evidence_reviewed_eval_fixtures(
                reviewed_fixtures_dir,
                paper_id=item.paper_id,
                run_id=run_id,
            )
            reviewed_eval_fixture_count = len(reviewed_fixtures)
            if require_reviewed_fixtures and reviewed_eval_fixture_count == 0:
                raise ValueError(
                    f"reviewed_fixtures_required_but_missing: paper_id={item.paper_id} run_id={run_id}"
                )
            if reviewed_fixtures:
                write_claim_evidence_reviewed_eval_fixtures_sidecar(
                    reviewed_dir=reviewed_fixtures_dir,
                    run_dir=output_run_dir,
                    paper_id=item.paper_id,
                    run_id=run_id,
                )
                generated_artifacts.append("claim_evidence_reviewed_eval_fixtures.json")

        scorecard_status = None
        scorecard_reason_codes: list[str] = []
        scorecard_readiness_metrics: dict[str, EvidenceGroundingMetric] = {}
        scorecard_repair_targets: list[EvidenceGroundingScorecardRepairTarget] = []
        if write_scorecards:
            scorecard = build_evidence_grounding_scorecard_from_run_dir(output_run_dir)
            write_evidence_grounding_scorecard(scorecard, output_run_dir)
            generated_artifacts.append("evidence_grounding_scorecard.json")
            scorecard_status = scorecard.readiness_status
            scorecard_reason_codes = list(scorecard.reason_codes)
            scorecard_readiness_metrics = _scorecard_readiness_metrics(scorecard)
            if scorecard_status == "fail":
                scorecard_repair_targets = [target.model_copy(deep=True) for target in scorecard.repair_targets]
    except Exception:
        if output_run_dir.exists():
            shutil.rmtree(output_run_dir)
        raise

    return EvidenceGroundingScorecardInputBackfillItem(
        paper_id=item.paper_id,
        source_run_dir=str(source_run_dir),
        output_run_dir=str(output_run_dir),
        status="pass",
        generated_artifacts=generated_artifacts,
        scorecard_readiness_status=scorecard_status,
        scorecard_reason_codes=scorecard_reason_codes,
        scorecard_readiness_metrics=scorecard_readiness_metrics,
        scorecard_repair_targets=scorecard_repair_targets,
        reviewed_eval_fixture_count=reviewed_eval_fixture_count,
    )


def _scorecard_readiness_metrics(scorecard: EvidenceGroundingScorecard) -> dict[str, EvidenceGroundingMetric]:
    selected_metric_names = (
        "grounded_evidence_ratio",
        "page_coverage_ratio",
        "missing_topic_signal_count",
        "low_overlap_claim_rate",
        "grounded_extraction_ref_rate",
        "duplicate_cluster_count",
    )
    metrics: dict[str, EvidenceGroundingMetric] = {}
    for metric_name in selected_metric_names:
        metric = getattr(scorecard.runtime_proxy_metrics, metric_name)
        if metric.status == "available":
            metrics[metric_name] = metric.model_copy(deep=True)
    return metrics


def _copy_paper_understanding_gold_input(gold_path: Path, *, output_run_dir: Path) -> None:
    if not gold_path.is_file():
        raise ValueError("paper_understanding_gold_path_not_found")
    gold = PaperUnderstandingGold.model_validate_json(gold_path.read_text(encoding="utf-8"))
    (output_run_dir / "paper_understanding_gold.json").write_text(
        gold.model_dump_json(indent=2),
        encoding="utf-8",
    )


def _load_claimset_for_scorecard_input_backfill(path: Path) -> ClaimSet:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sanitized_payload = _drop_legacy_empty_evidence_spans(payload)
    return ClaimSet.model_validate(sanitized_payload)


def _drop_legacy_empty_evidence_spans(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    claims = payload.get("claims")
    if not isinstance(claims, list):
        return payload
    sanitized = dict(payload)
    sanitized_claims: list[Any] = []
    for claim in claims:
        if not isinstance(claim, dict):
            sanitized_claims.append(claim)
            continue
        evidence_spans = claim.get("evidence_spans")
        if not isinstance(evidence_spans, list):
            sanitized_claims.append(claim)
            continue
        kept_spans = [
            span
            for span in evidence_spans
            if not _is_legacy_empty_evidence_span(span)
        ]
        if len(kept_spans) == len(evidence_spans):
            sanitized_claims.append(claim)
            continue
        sanitized_claim = dict(claim)
        sanitized_claim["evidence_spans"] = kept_spans
        sanitized_claims.append(sanitized_claim)
    sanitized["claims"] = sanitized_claims
    return sanitized


def _is_legacy_empty_evidence_span(span: Any) -> bool:
    if not isinstance(span, dict):
        return False
    raw_text = str(span.get("raw_text") or "").strip()
    table_id = str(span.get("table_id") or "").strip()
    cell_id = str(span.get("cell_id") or "").strip()
    quote = str(span.get("quote") or "").strip()
    has_bbox = span.get("bbox_pdf") is not None or span.get("bbox_pct") is not None
    return not raw_text and not table_id and not cell_id and not quote and not has_bbox


def _failed_item(
    item: EvidenceGroundingScorecardInputBackfillItemRequest,
    *,
    source_run_dir: Path,
    output_run_dir: Path,
    error: str,
) -> EvidenceGroundingScorecardInputBackfillItem:
    return EvidenceGroundingScorecardInputBackfillItem(
        paper_id=item.paper_id,
        source_run_dir=str(source_run_dir),
        output_run_dir=str(output_run_dir),
        status="fail",
        error=error,
    )


def _load_document_artifact(path: Path) -> DocumentArtifact | DocumentArtifactV2:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("schema_version") or "") == "2.0" or "document_id" in payload:
        return DocumentArtifactV2.model_validate(payload)
    return DocumentArtifact.model_validate(payload)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
