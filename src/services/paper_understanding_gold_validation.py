from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal
from datetime import datetime, timezone

from pydantic import ValidationError

from src.schemas.paper_understanding_gold import (
    PaperUnderstandingGold,
    PaperUnderstandingGoldCurationBucket,
    PaperUnderstandingGoldCurationReport,
    PaperUnderstandingGoldCurationTarget,
    PaperUnderstandingGoldCurationTargetResult,
    PaperUnderstandingGoldManifest,
    PaperUnderstandingGoldManifestItem,
    PaperUnderstandingGoldReleaseManifestBuildItem,
    PaperUnderstandingGoldReleasePackageReport,
    PaperUnderstandingGoldReleaseSplitPlanItem,
    PaperUnderstandingGoldReleaseSplitPlanReport,
    PaperUnderstandingGoldReadinessCheck,
    PaperUnderstandingGoldReadinessReport,
    PaperUnderstandingGoldReadinessStatus,
    PaperUnderstandingGoldReleaseReadinessReport,
    PaperUnderstandingGoldReleaseSplitSummary,
    PaperUnderstandingGoldStagingManifest,
)
from src.skills.storage import atomic_write_text


def iter_gold_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for path in paths:
        path = path.expanduser()
        if path.is_dir():
            out.extend(
                sorted(
                    item
                    for item in path.rglob("*.json")
                    if item.is_file() and item.name != "staging_manifest.json"
                )
            )
        elif path.is_file():
            out.extend(_expand_staging_manifest_path(path))
    return out


def _expand_staging_manifest_path(path: Path) -> list[Path]:
    payload, _error = _load_json_path(path)
    if payload is None or payload.get("schema_version") != "paper_understanding_gold_staging_manifest.v1":
        return [path]
    try:
        manifest = PaperUnderstandingGoldStagingManifest.model_validate(payload)
    except (ValidationError, ValueError):
        return [path]
    return [Path(staged_path).expanduser() for staged_path in manifest.staged_paths]


def validate_gold_path(path: Path) -> tuple[PaperUnderstandingGold | None, str | None]:
    payload, error = _load_json_path(path)
    if payload is None:
        return None, error
    try:
        return PaperUnderstandingGold.model_validate(payload), None
    except (ValidationError, ValueError) as exc:
        return None, str(exc)


def validate_gold_paths(paths: list[Path], *, require_ready: bool = False) -> dict[str, Any]:
    files = iter_gold_paths(paths)
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    manifests: list[dict[str, Any]] = []
    seen_paper_ids: set[str] = set()
    checked_gold_count = 0

    for path in files:
        payload, error = _load_json_path(path)
        if payload is None:
            invalid.append(_invalid_summary(path, error or "unknown validation error"))
            continue

        if payload.get("schema_version") == "paper_understanding_gold_manifest.v1":
            try:
                manifest = PaperUnderstandingGoldManifest.model_validate(payload)
            except (ValidationError, ValueError) as exc:
                invalid.append(_invalid_summary(path, str(exc)))
                continue

            manifests.append(
                {
                    "path": str(path),
                    "goldset_id": manifest.goldset_id,
                    "goldset_split": manifest.goldset_split,
                    "item_count": len(manifest.items),
                }
            )
            for item in manifest.items:
                checked_gold_count += 1
                gold_path = _resolve_manifest_gold_path(path, item.gold_path)
                record, item_error = validate_gold_path(gold_path)
                if record is None:
                    invalid.append(
                        _invalid_summary(
                            gold_path,
                            item_error or "unknown validation error",
                            manifest_path=path,
                        )
                    )
                    continue
                if record.paper_id != item.paper_id:
                    invalid.append(
                        _invalid_summary(
                            gold_path,
                            f"manifest paper_id={item.paper_id} does not match gold paper_id={record.paper_id}",
                            manifest_path=path,
                        )
                    )
                    continue
                if record.paper_id in seen_paper_ids:
                    invalid.append(
                        _invalid_summary(
                            gold_path,
                            f"duplicate paper_id={record.paper_id}",
                            manifest_path=path,
                        )
                    )
                    continue
                readiness = assess_paper_understanding_gold_readiness(record)
                if require_ready and readiness.status != "pass":
                    invalid.append(
                        _invalid_summary(
                            gold_path,
                            _readiness_error(readiness),
                            manifest_path=path,
                        )
                    )
                    continue
                seen_paper_ids.add(record.paper_id)
                valid.append(
                    _gold_summary(
                        path=gold_path,
                        record=record,
                        manifest_path=path,
                        goldset_id=manifest.goldset_id,
                        goldset_split=manifest.goldset_split,
                    )
                )
            continue

        try:
            record = PaperUnderstandingGold.model_validate(payload)
        except (ValidationError, ValueError) as exc:
            invalid.append(_invalid_summary(path, str(exc)))
            continue

        checked_gold_count += 1
        if record.paper_id in seen_paper_ids:
            invalid.append(_invalid_summary(path, f"duplicate paper_id={record.paper_id}"))
            continue
        readiness = assess_paper_understanding_gold_readiness(record)
        if require_ready and readiness.status != "pass":
            invalid.append(_invalid_summary(path, _readiness_error(readiness)))
            continue
        seen_paper_ids.add(record.paper_id)
        valid.append(_gold_summary(path=path, record=record))

    readiness_counts = _readiness_counts(valid)

    return {
        "schema_version": "paper_understanding_gold_validation.v1",
        "checked_count": len(files),
        "checked_gold_count": checked_gold_count,
        "manifest_count": len(manifests),
        "require_ready": require_ready,
        "valid_count": len(valid),
        "invalid_count": len(invalid),
        "readiness": readiness_counts,
        "manifests": manifests,
        "valid": valid,
        "invalid": invalid,
    }


def build_paper_understanding_gold_manifest(
    paths: list[Path],
    *,
    goldset_id: str,
    goldset_split: str,
    manifest_path: Path | None = None,
    require_ready: bool = False,
) -> PaperUnderstandingGoldManifest:
    files = iter_gold_paths(paths)
    items: list[PaperUnderstandingGoldManifestItem] = []
    errors: list[str] = []

    for path in files:
        record, error = validate_gold_path(path)
        if record is None:
            errors.append(f"path={path} error={error or 'unknown validation error'}")
            continue
        readiness = assess_paper_understanding_gold_readiness(record)
        if require_ready and readiness.status != "pass":
            errors.append(f"path={path} error={_readiness_error(readiness)}")
            continue
        items.append(
            PaperUnderstandingGoldManifestItem(
                paper_id=record.paper_id,
                gold_path=_manifest_relative_path(path, manifest_path=manifest_path),
                paper_type=record.paper_type,
                domain_tags=record.domain_tags,
                metadata={
                    "title": record.citation.title,
                    "doi": record.citation.doi,
                    "pmid": record.citation.pmid,
                    "year": record.citation.year,
                    "claim_count": len(record.gold_claims),
                    "method_count": len(record.gold_methods),
                    "result_count": len(record.gold_results),
                    "limitation_count": len(record.gold_limitations),
                    "gap_count": len(record.gold_gaps),
                    "figure_count": len(record.important_figures),
                    "table_count": len(record.important_tables),
                    "readiness_status": readiness.status,
                    "readiness_reason_codes": readiness.reason_codes,
                },
            )
        )

    if errors:
        raise ValueError("cannot build paper understanding gold manifest from invalid inputs: " + "; ".join(errors))

    return PaperUnderstandingGoldManifest(
        goldset_id=goldset_id,
        goldset_split=goldset_split,
        items=items,
        notes=[
            "Generated from validated paper_understanding_gold.v1 records.",
            "Manifest is an eval/reference artifact and does not promote records into canonical runtime truth.",
        ],
    )


def build_paper_understanding_gold_curation_report(
    paths: list[Path],
    *,
    report_id: str = "paper-understanding-gold-curation",
    targets: list[PaperUnderstandingGoldCurationTarget] | None = None,
    out: Path | None = None,
) -> PaperUnderstandingGoldCurationReport:
    validation = validate_gold_paths(paths)
    valid_records = list(validation["valid"])
    target_list = list(targets or [])
    buckets = _curation_buckets(valid_records)
    target_results = [_curation_target_result(valid_records, target) for target in target_list]
    warnings: list[str] = []
    if validation["invalid_count"]:
        warnings.append("invalid_gold_records_present")
    if not validation["manifest_count"]:
        warnings.append("no_goldset_manifest_checked")
    if not target_list:
        warnings.append("no_curation_targets_declared")
    if any(result.status == "fail" for result in target_results):
        warnings.append("curation_targets_not_met")

    report = PaperUnderstandingGoldCurationReport(
        generated_at=datetime.now(timezone.utc),
        report_id=report_id,
        manifest_count=validation["manifest_count"],
        paper_count=validation["valid_count"],
        ready_paper_count=sum(1 for record in valid_records if record.get("readiness_status") == "pass"),
        invalid_count=validation["invalid_count"],
        curation_ready=(
            validation["invalid_count"] == 0
            and bool(target_results)
            and all(result.status == "pass" for result in target_results)
        ),
        buckets=buckets,
        target_results=target_results,
        warnings=warnings,
    )
    if out is not None:
        atomic_write_text(Path(out), report.model_dump_json(indent=2))
    return report


def build_paper_understanding_gold_release_readiness_report(
    manifest_paths: list[Path],
    *,
    readiness_id: str = "paper-understanding-gold-release-readiness",
    required_splits: list[str] | None = None,
    min_ready_per_split: int = 1,
    require_single_goldset_id: bool = True,
    out: Path | None = None,
) -> PaperUnderstandingGoldReleaseReadinessReport:
    required = _dedupe_strings(required_splits or ["seed", "eval", "holdout"])
    split_summaries: list[PaperUnderstandingGoldReleaseSplitSummary] = []
    paper_id_counts: dict[str, int] = {}
    goldset_ids: set[str] = set()
    observed_splits: set[str] = set()
    blockers: list[str] = []
    warnings: list[str] = []

    for raw_path in manifest_paths:
        path = Path(raw_path).expanduser().resolve()
        validation = validate_gold_paths([path])
        manifest_info = validation["manifests"][0] if validation["manifests"] else None
        valid_records = list(validation["valid"])
        ready_count = sum(1 for record in valid_records if record.get("readiness_status") == "pass")
        warn_count = sum(1 for record in valid_records if record.get("readiness_status") == "warn")
        fail_count = sum(1 for record in valid_records if record.get("readiness_status") == "fail")
        paper_ids = sorted(str(record["paper_id"]) for record in valid_records)
        for paper_id in paper_ids:
            paper_id_counts[paper_id] = paper_id_counts.get(paper_id, 0) + 1

        goldset_id = str(manifest_info["goldset_id"]) if manifest_info else None
        goldset_split = str(manifest_info["goldset_split"]) if manifest_info else None
        if goldset_id:
            goldset_ids.add(goldset_id)
        if goldset_split:
            observed_splits.add(goldset_split)

        status = "pass"
        detail = "Manifest is loadable, contains ready records, and has no invalid referenced gold records."
        if manifest_info is None:
            status = "fail"
            detail = "Path did not load as a paper_understanding_gold_manifest.v1 manifest."
        elif validation["invalid_count"]:
            status = "fail"
            detail = "Manifest has invalid referenced gold records."
        elif ready_count < min_ready_per_split:
            status = "fail"
            detail = f"Manifest has fewer than {min_ready_per_split} ready records."

        split_summaries.append(
            PaperUnderstandingGoldReleaseSplitSummary(
                manifest_path=str(path),
                goldset_id=goldset_id,
                goldset_split=goldset_split,
                item_count=len(valid_records) + int(validation["invalid_count"]),
                ready_count=ready_count,
                warn_count=warn_count,
                fail_count=fail_count,
                invalid_count=validation["invalid_count"],
                paper_ids=paper_ids,
                status=status,
                detail=detail,
            )
        )

    missing_splits = sorted(split for split in required if split not in observed_splits)
    ready_by_split: dict[str, int] = {}
    for summary in split_summaries:
        if summary.goldset_split is None:
            continue
        ready_by_split[summary.goldset_split] = ready_by_split.get(summary.goldset_split, 0) + summary.ready_count
    underfilled_splits = sorted(
        split
        for split in required
        if split in observed_splits and ready_by_split.get(split, 0) < min_ready_per_split
    )
    duplicate_paper_ids = sorted(paper_id for paper_id, count in paper_id_counts.items() if count > 1)
    invalid_count = sum(summary.invalid_count for summary in split_summaries)
    if not split_summaries:
        blockers.append("manifest_paths_missing")
    if any(summary.goldset_split is None for summary in split_summaries):
        blockers.append("manifest_contract_missing")
    if missing_splits:
        blockers.append("required_splits_missing")
    if underfilled_splits:
        blockers.append("required_splits_underfilled")
    if invalid_count:
        blockers.append("invalid_gold_records_present")
    if duplicate_paper_ids:
        blockers.append("duplicate_paper_ids_across_splits")
    if require_single_goldset_id and len(goldset_ids) > 1:
        blockers.append("multiple_goldset_ids")
    if any(summary.status == "fail" for summary in split_summaries):
        warnings.append("split_readiness_failures_present")
    if blockers:
        warnings.append("gold_release_readiness_blocked")

    report = PaperUnderstandingGoldReleaseReadinessReport(
        generated_at=datetime.now(timezone.utc),
        readiness_id=readiness_id,
        required_splits=required,
        min_ready_per_split=min_ready_per_split,
        manifest_count=len(split_summaries),
        goldset_ids=sorted(goldset_ids),
        item_count=sum(summary.item_count for summary in split_summaries),
        ready_count=sum(summary.ready_count for summary in split_summaries),
        invalid_count=invalid_count,
        missing_splits=missing_splits,
        underfilled_splits=underfilled_splits,
        duplicate_paper_ids=duplicate_paper_ids,
        split_summaries=split_summaries,
        blockers=blockers,
        release_ready=not blockers,
        warnings=warnings,
    )
    if out is not None:
        atomic_write_text(Path(out), report.model_dump_json(indent=2))
    return report


def build_paper_understanding_gold_release_split_plan_from_staging_manifest(
    *,
    staging_manifest_path: Path,
    out_dir: Path,
    manifest_out_dir: Path | None = None,
    plan_id: str = "paper-understanding-gold-release-split-plan",
    split_names: list[str] | None = None,
    min_ready_per_split: int = 1,
    require_ready: bool = True,
    out: Path | None = None,
) -> PaperUnderstandingGoldReleaseSplitPlanReport:
    source_path = Path(staging_manifest_path).expanduser().resolve()
    out_dir = Path(out_dir).expanduser().resolve()
    manifest_out_dir = Path(manifest_out_dir).expanduser().resolve() if manifest_out_dir is not None else out_dir / "manifests"
    splits = _dedupe_strings(split_names or ["seed", "eval", "holdout"])
    if not splits:
        raise ValueError("split_names is required")

    source_manifest = PaperUnderstandingGoldStagingManifest.model_validate_json(source_path.read_text(encoding="utf-8"))
    ready_records: list[tuple[str, Path]] = []
    invalid_errors: list[str] = []
    for raw_path in source_manifest.staged_paths:
        gold_path = Path(raw_path).expanduser().resolve()
        record, error = validate_gold_path(gold_path)
        if record is None:
            invalid_errors.append(f"path={gold_path} error={error or 'unknown validation error'}")
            continue
        readiness = assess_paper_understanding_gold_readiness(record)
        if require_ready and readiness.status != "pass":
            invalid_errors.append(
                f"path={gold_path} paper_id={record.paper_id} readiness={readiness.status} "
                f"reason_codes={','.join(readiness.reason_codes)}"
            )
            continue
        ready_records.append((record.paper_id, gold_path))

    if invalid_errors and require_ready:
        raise ValueError("cannot build release split plan from invalid or not-ready staged gold: " + "; ".join(invalid_errors))

    ready_records = sorted(ready_records, key=lambda item: item[0])
    assignments: dict[str, list[tuple[str, Path]]] = {split: [] for split in splits}
    for index, record in enumerate(ready_records):
        assignments[splits[index % len(splits)]].append(record)

    split_items: list[PaperUnderstandingGoldReleaseSplitPlanItem] = []
    split_manifests: list[PaperUnderstandingGoldReleaseManifestBuildItem] = []
    warnings: list[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_out_dir.mkdir(parents=True, exist_ok=True)
    for split in splits:
        split_dir = out_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        staged_paths = [str(path) for _paper_id, path in assignments[split]]
        split_staging_manifest = PaperUnderstandingGoldStagingManifest(
            generated_at=datetime.now(timezone.utc),
            source_draft_paths=list(source_manifest.source_draft_paths),
            out_dir=str(split_dir),
            require_ready=require_ready,
            staged_count=len(staged_paths),
            staged_paths=staged_paths,
            readiness_summary={
                "pass_count": len(staged_paths),
                "warn_count": 0,
                "fail_count": 0,
            },
        )
        split_staging_manifest_path = split_dir / "staging_manifest.json"
        atomic_write_text(split_staging_manifest_path, split_staging_manifest.model_dump_json(indent=2))
        manifest_out = manifest_out_dir / f"{_safe_path_segment(split)}.json"
        split_manifests.append(
            PaperUnderstandingGoldReleaseManifestBuildItem(
                staging_manifest_path=str(split_staging_manifest_path),
                goldset_split=split,
                manifest_out=str(manifest_out),
            )
        )
        split_items.append(
            PaperUnderstandingGoldReleaseSplitPlanItem(
                goldset_split=split,
                staging_manifest_path=str(split_staging_manifest_path),
                manifest_out=str(manifest_out),
                staged_count=len(staged_paths),
                paper_ids=[paper_id for paper_id, _path in assignments[split]],
            )
        )

    underfilled_splits = sorted(split for split, records in assignments.items() if len(records) < min_ready_per_split)
    if underfilled_splits:
        warnings.append(f"underfilled_splits={','.join(underfilled_splits)}")
    if invalid_errors:
        warnings.append(f"invalid_or_not_ready_input_count={len(invalid_errors)}")
    report = PaperUnderstandingGoldReleaseSplitPlanReport(
        generated_at=datetime.now(timezone.utc),
        plan_id=plan_id,
        source_staging_manifest_path=str(source_path),
        out_dir=str(out_dir),
        manifest_out_dir=str(manifest_out_dir),
        split_names=splits,
        min_ready_per_split=min_ready_per_split,
        ready_input_count=len(ready_records),
        invalid_input_count=len(invalid_errors),
        release_ready_candidate=not underfilled_splits and not invalid_errors,
        split_manifests=split_manifests,
        split_items=split_items,
        warnings=warnings,
    )
    if out is not None:
        atomic_write_text(Path(out).expanduser().resolve(), report.model_dump_json(indent=2))
    return report


def build_paper_understanding_gold_release_package_from_staged_gold(
    *,
    goldset_id: str,
    split_manifests: list[PaperUnderstandingGoldReleaseManifestBuildItem],
    release_readiness_out: Path,
    package_id: str = "paper-understanding-gold-release-package",
    package_out: Path | None = None,
    require_ready: bool = True,
    required_splits: list[str] | None = None,
    min_ready_per_split: int = 1,
    require_single_goldset_id: bool = True,
) -> PaperUnderstandingGoldReleasePackageReport:
    manifest_paths: list[Path] = []
    for item in split_manifests:
        manifest_out = Path(item.manifest_out).expanduser().resolve()
        manifest = build_paper_understanding_gold_manifest(
            [Path(item.staging_manifest_path).expanduser().resolve()],
            goldset_id=goldset_id,
            goldset_split=item.goldset_split,
            manifest_path=manifest_out,
            require_ready=require_ready,
        )
        atomic_write_text(manifest_out, manifest.model_dump_json(indent=2))
        validation = validate_gold_paths([manifest_out], require_ready=require_ready)
        if validation["invalid_count"]:
            raise ValueError(f"built manifest did not validate: path={manifest_out} invalid={validation['invalid']}")
        manifest_paths.append(manifest_out)

    release_readiness_out = Path(release_readiness_out).expanduser().resolve()
    release_readiness = build_paper_understanding_gold_release_readiness_report(
        manifest_paths,
        required_splits=required_splits,
        min_ready_per_split=min_ready_per_split,
        require_single_goldset_id=require_single_goldset_id,
        out=release_readiness_out,
    )
    report = PaperUnderstandingGoldReleasePackageReport(
        generated_at=datetime.now(timezone.utc),
        package_id=package_id,
        goldset_id=goldset_id,
        source_split_manifests=split_manifests,
        manifest_paths=[str(path) for path in manifest_paths],
        release_readiness_report_path=str(release_readiness_out),
        release_readiness=release_readiness,
    )
    if package_out is not None:
        atomic_write_text(Path(package_out).expanduser().resolve(), report.model_dump_json(indent=2))
    return report


def build_paper_understanding_gold_release_package_from_split_plan(
    *,
    goldset_id: str,
    split_plan_path: Path,
    release_readiness_out: Path,
    package_id: str = "paper-understanding-gold-release-package",
    package_out: Path | None = None,
    require_ready: bool = True,
    required_splits: list[str] | None = None,
    min_ready_per_split: int = 1,
    require_single_goldset_id: bool = True,
) -> PaperUnderstandingGoldReleasePackageReport:
    split_plan_path = Path(split_plan_path).expanduser().resolve()
    split_plan = PaperUnderstandingGoldReleaseSplitPlanReport.model_validate_json(
        split_plan_path.read_text(encoding="utf-8")
    )
    if require_ready and not split_plan.release_ready_candidate:
        raise ValueError(
            "split plan is not release-ready candidate: "
            f"path={split_plan_path} warnings={split_plan.warnings}"
        )
    if not split_plan.split_manifests:
        raise ValueError(f"split plan has no split manifests: path={split_plan_path}")

    return build_paper_understanding_gold_release_package_from_staged_gold(
        goldset_id=goldset_id,
        split_manifests=split_plan.split_manifests,
        release_readiness_out=release_readiness_out,
        package_id=package_id,
        package_out=package_out,
        require_ready=require_ready,
        required_splits=required_splits,
        min_ready_per_split=min_ready_per_split,
        require_single_goldset_id=require_single_goldset_id,
    )


def assess_paper_understanding_gold_readiness(
    record: PaperUnderstandingGold,
) -> PaperUnderstandingGoldReadinessReport:
    checks = [
        _readiness_check(
            code="CLAIM_COUNT_OUT_OF_RANGE",
            ok=3 <= len(record.gold_claims) <= 7,
            status_if_missing="warn",
            detail=f"Gold records should carry 3-7 core claims; found {len(record.gold_claims)}.",
        ),
        _readiness_check(
            code="METHOD_MISSING",
            ok=bool(record.gold_methods),
            status_if_missing="fail",
            detail="At least one grounded method statement is required for paper-understanding eval readiness.",
        ),
        _readiness_check(
            code="RESULT_MISSING",
            ok=bool(record.gold_results),
            status_if_missing="fail",
            detail="At least one grounded result statement is required for paper-understanding eval readiness.",
        ),
        _readiness_check(
            code="LIMITATION_MISSING",
            ok=bool(record.gold_limitations),
            status_if_missing="fail",
            detail="At least one grounded limitation is required so limitation recall can be evaluated.",
        ),
        _readiness_check(
            code="DOMAIN_TAGS_MISSING",
            ok=bool(record.domain_tags),
            status_if_missing="fail",
            detail="At least one domain tag is required for representative fixed-goldset slicing.",
        ),
        _readiness_check(
            code="PAPER_TYPE_OTHER",
            ok=record.paper_type != "other",
            status_if_missing="warn",
            detail="A specific paper_type is recommended for domain and method/result comparisons.",
        ),
        _readiness_check(
            code="IMPORTANT_VISUALS_MISSING",
            ok=bool(record.important_figures or record.important_tables),
            status_if_missing="warn",
            detail="Important figures or tables should be listed when the paper has reusable visual evidence.",
        ),
        _readiness_check(
            code="EXTERNAL_ID_MISSING",
            ok=bool(record.citation.doi or record.citation.pmid),
            status_if_missing="warn",
            detail="DOI or PMID is recommended for metadata matching and duplicate detection.",
        ),
    ]
    reason_codes = [check.code for check in checks if check.status != "pass"]
    if any(check.status == "fail" for check in checks):
        status: PaperUnderstandingGoldReadinessStatus = "fail"
    elif any(check.status == "warn" for check in checks):
        status = "warn"
    else:
        status = "pass"
    return PaperUnderstandingGoldReadinessReport(
        paper_id=record.paper_id,
        status=status,
        checks=checks,
        reason_codes=reason_codes,
    )


def _load_json_path(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None, "gold JSON root must be an object"
        return payload, None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def _resolve_manifest_gold_path(manifest_path: Path, gold_path: str) -> Path:
    path = Path(gold_path).expanduser()
    if path.is_absolute():
        return path
    return manifest_path.parent / path


def _manifest_relative_path(path: Path, *, manifest_path: Path | None) -> str:
    path = path.expanduser()
    if manifest_path is None:
        return str(path)
    base_dir = manifest_path.expanduser().parent
    return os.path.relpath(path.resolve(), start=base_dir.resolve())


def _gold_summary(
    *,
    path: Path,
    record: PaperUnderstandingGold,
    manifest_path: Path | None = None,
    goldset_id: str | None = None,
    goldset_split: str | None = None,
) -> dict[str, Any]:
    readiness = assess_paper_understanding_gold_readiness(record)
    summary: dict[str, Any] = {
        "path": str(path),
        "paper_id": record.paper_id,
        "paper_type": record.paper_type,
        "domain_tags": record.domain_tags,
        "claim_count": len(record.gold_claims),
        "method_count": len(record.gold_methods),
        "result_count": len(record.gold_results),
        "limitation_count": len(record.gold_limitations),
        "gap_count": len(record.gold_gaps),
        "figure_count": len(record.important_figures),
        "table_count": len(record.important_tables),
        "readiness_status": readiness.status,
        "readiness_reason_codes": readiness.reason_codes,
    }
    if manifest_path is not None:
        summary["manifest_path"] = str(manifest_path)
    if goldset_id is not None:
        summary["goldset_id"] = goldset_id
    if goldset_split is not None:
        summary["goldset_split"] = goldset_split
    return summary


def _curation_buckets(valid_records: list[dict[str, Any]]) -> list[PaperUnderstandingGoldCurationBucket]:
    raw_buckets: dict[tuple[str | None, str | None, str | None], dict[str, Any]] = {}
    for record in valid_records:
        split = record.get("goldset_split") or "unassigned"
        paper_type = record.get("paper_type") or "other"
        domain_tags = record.get("domain_tags") or ["unassigned"]
        for key in (
            (split, None, None),
            (split, None, paper_type),
            *[(split, domain_tag, None) for domain_tag in domain_tags],
            *[(split, domain_tag, paper_type) for domain_tag in domain_tags],
        ):
            bucket = raw_buckets.setdefault(
                key,
                {
                    "goldset_split": key[0],
                    "domain_tag": key[1],
                    "paper_type": key[2],
                    "total_count": 0,
                    "ready_count": 0,
                    "warn_count": 0,
                    "fail_count": 0,
                    "paper_ids": [],
                },
            )
            bucket["total_count"] += 1
            if record.get("readiness_status") == "pass":
                bucket["ready_count"] += 1
            elif record.get("readiness_status") == "warn":
                bucket["warn_count"] += 1
            else:
                bucket["fail_count"] += 1
            bucket["paper_ids"].append(record["paper_id"])
    return [
        PaperUnderstandingGoldCurationBucket(**raw_buckets[key])
        for key in sorted(raw_buckets, key=lambda value: tuple("" if part is None else str(part) for part in value))
    ]


def _curation_target_result(
    valid_records: list[dict[str, Any]],
    target: PaperUnderstandingGoldCurationTarget,
) -> PaperUnderstandingGoldCurationTargetResult:
    matching_records = [record for record in valid_records if _record_matches_curation_target(record, target)]
    ready_paper_ids = sorted(
        str(record["paper_id"])
        for record in matching_records
        if record.get("readiness_status") == "pass"
    )
    missing = max(int(target.min_ready_count) - len(ready_paper_ids), 0)
    return PaperUnderstandingGoldCurationTargetResult(
        target=target,
        status="pass" if missing == 0 else "fail",
        ready_count=len(ready_paper_ids),
        missing_ready_count=missing,
        matching_paper_ids=ready_paper_ids,
    )


def _record_matches_curation_target(
    record: dict[str, Any],
    target: PaperUnderstandingGoldCurationTarget,
) -> bool:
    if target.goldset_split is not None and record.get("goldset_split") != target.goldset_split:
        return False
    if target.paper_type is not None and record.get("paper_type") != target.paper_type:
        return False
    if target.domain_tag is not None and target.domain_tag not in set(record.get("domain_tags") or []):
        return False
    return True


def _dedupe_strings(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _safe_path_segment(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip())
    return cleaned.strip("-") or "split"


def _readiness_check(
    *,
    code: str,
    ok: bool,
    status_if_missing: Literal["warn", "fail"],
    detail: str,
) -> PaperUnderstandingGoldReadinessCheck:
    return PaperUnderstandingGoldReadinessCheck(
        code=code,
        status="pass" if ok else status_if_missing,
        detail=detail,
    )


def _readiness_counts(valid: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"pass": 0, "warn": 0, "fail": 0}
    reason_counts: dict[str, int] = {}
    for item in valid:
        status = item.get("readiness_status")
        if status in counts:
            counts[status] += 1
        for code in item.get("readiness_reason_codes", []):
            reason_counts[code] = reason_counts.get(code, 0) + 1
    return {
        "schema_version": "paper_understanding_gold_readiness_summary.v1",
        "pass_count": counts["pass"],
        "warn_count": counts["warn"],
        "fail_count": counts["fail"],
        "reason_counts": {code: reason_counts[code] for code in sorted(reason_counts)},
    }


def _readiness_error(readiness: PaperUnderstandingGoldReadinessReport) -> str:
    return (
        "gold readiness not pass: "
        f"status={readiness.status} reason_codes={','.join(readiness.reason_codes)}"
    )


def _invalid_summary(path: Path, error: str, *, manifest_path: Path | None = None) -> dict[str, str]:
    summary = {"path": str(path), "error": error}
    if manifest_path is not None:
        summary["manifest_path"] = str(manifest_path)
    return summary
