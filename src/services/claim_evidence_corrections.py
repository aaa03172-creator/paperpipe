from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from pydantic import ValidationError

from src.schemas.claim_evidence_correction import (
    ClaimEvidenceCorrectionCase,
    ClaimEvidenceCorrectionEvalCandidate,
    ClaimEvidenceCorrectionEvalCandidateExport,
    ClaimEvidenceCorrectionEvalReviewDecision,
    ClaimEvidenceCorrectionEvalReviewManifest,
    ClaimEvidenceCorrectionEvalReviewRecord,
    ClaimEvidenceCorrectionFeedbackExportStatus,
    ClaimEvidenceCorrectionRepairPlan,
    ClaimEvidenceCorrectionRepairPlanTarget,
    ClaimEvidenceCorrectionRepairPatchTemplate,
    ClaimEvidenceCorrectionRepairPatchTemplateRecord,
    ClaimEvidenceCorrectionRepairedLogDraft,
    ClaimEvidenceCorrectionReviewedEvalFixture,
    ClaimEvidenceCorrectionReviewedEvalFixturesBundle,
    ClaimEvidenceCorrectionSourceRecordDiagnostic,
    ClaimEvidenceEvalReviewResolution,
)
from src.services.event_log import sanitize_event_payload_for_log, sanitize_event_text_for_log
from src.services.runtime_paths import claim_evidence_correction_log_path


CLAIM_EVIDENCE_REPLAY_LINEAGE_FIELDS = (
    "parser_version",
    "llm_provider",
    "llm_model",
    "llm_model_version",
    "prompt_version",
    "reader_profile_version",
)

CLAIM_EVIDENCE_REPLAY_CONTEXT_METADATA_KEYS = (
    "source",
    "readiness_status",
    "link_health",
    "eval_lineage_available",
)


def _sanitize_correction(correction: ClaimEvidenceCorrectionCase) -> ClaimEvidenceCorrectionCase:
    updates = {}
    for field_name in (
        "correction_id",
        "paper_id",
        "run_id",
        "claim_id",
        "field_path",
        "before_claim_text",
        "after_claim_text",
        "reviewer_id",
        "parser_version",
        "llm_provider",
        "llm_model",
        "llm_model_version",
        "prompt_version",
        "reader_profile_version",
        "related_feedback_id",
    ):
        value = getattr(correction, field_name)
        sanitized = sanitize_event_text_for_log(value)
        if sanitized != value:
            updates[field_name] = sanitized

    sanitized_before = sanitize_event_payload_for_log(
        [item.model_dump(mode="json") for item in correction.before_evidence_refs]
    )
    if sanitized_before != [item.model_dump(mode="json") for item in correction.before_evidence_refs]:
        updates["before_evidence_refs"] = sanitized_before

    sanitized_after = sanitize_event_payload_for_log(
        [item.model_dump(mode="json") for item in correction.after_evidence_refs]
    )
    if sanitized_after != [item.model_dump(mode="json") for item in correction.after_evidence_refs]:
        updates["after_evidence_refs"] = sanitized_after

    sanitized_metadata = sanitize_event_payload_for_log(correction.metadata)
    if sanitized_metadata != correction.metadata:
        updates["metadata"] = sanitized_metadata

    if not updates:
        return correction
    return ClaimEvidenceCorrectionCase.model_validate(correction.model_dump(mode="json") | updates)


def append_claim_evidence_correction(
    correction: ClaimEvidenceCorrectionCase,
    *,
    log_path: Path | None = None,
) -> ClaimEvidenceCorrectionCase:
    if correction.created_at is None:
        correction.created_at = datetime.now(timezone.utc)
    correction = _sanitize_correction(correction)

    path = log_path or claim_evidence_correction_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(correction.model_dump_json())
        handle.write("\n")
    return correction


def load_claim_evidence_corrections(*, log_path: Path | None = None) -> list[ClaimEvidenceCorrectionCase]:
    corrections, _, _, _ = load_claim_evidence_corrections_with_diagnostics(log_path=log_path)
    return corrections


def load_claim_evidence_corrections_with_diagnostics(
    *,
    log_path: Path | None = None,
    diagnostic_limit: int = 20,
) -> tuple[list[ClaimEvidenceCorrectionCase], int, int, list[ClaimEvidenceCorrectionSourceRecordDiagnostic]]:
    path = log_path or claim_evidence_correction_log_path()
    if not path.exists():
        return [], 0, 0, []

    out: list[ClaimEvidenceCorrectionCase] = []
    source_record_count = 0
    invalid_record_count = 0
    diagnostics: list[ClaimEvidenceCorrectionSourceRecordDiagnostic] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        source_record_count += 1
        try:
            out.append(_sanitize_correction(ClaimEvidenceCorrectionCase.model_validate_json(line)))
        except Exception as exc:
            invalid_record_count += 1
            if len(diagnostics) < diagnostic_limit:
                diagnostics.append(
                    ClaimEvidenceCorrectionSourceRecordDiagnostic(
                        line_number=line_number,
                        error_type=type(exc).__name__,
                        detail=_diagnostic_detail(exc),
                        **_source_record_identity_fields(line),
                        reason_codes=_source_record_reason_codes(line),
                        available_replay_context=_source_record_available_replay_context(
                            line,
                            log_path=Path(path),
                        ),
                        missing_replay_fields=_missing_replay_fields(line),
                    )
                )
            continue
    return out, source_record_count, invalid_record_count, diagnostics


def build_claim_evidence_correction_repair_plan(
    *,
    log_path: Path | None = None,
    diagnostic_limit: int = 100,
) -> ClaimEvidenceCorrectionRepairPlan:
    path = Path(log_path or claim_evidence_correction_log_path()).expanduser().resolve()
    corrections, source_record_count, invalid_record_count, diagnostics = (
        load_claim_evidence_corrections_with_diagnostics(
            log_path=path,
            diagnostic_limit=diagnostic_limit,
        )
    )
    targets = [
        ClaimEvidenceCorrectionRepairPlanTarget(
            line_number=diagnostic.line_number,
            source_correction_id=diagnostic.source_correction_id,
            paper_id=diagnostic.paper_id,
            run_id=diagnostic.run_id,
            claim_id=diagnostic.claim_id,
            detail=diagnostic.detail or diagnostic.error_type,
            reason_codes=diagnostic.reason_codes,
            available_replay_context=diagnostic.available_replay_context,
            missing_replay_fields=diagnostic.missing_replay_fields,
        )
        for diagnostic in diagnostics
    ]
    warnings: list[str] = []
    if invalid_record_count > len(diagnostics):
        warnings.append("repair_plan_diagnostic_limit_reached")
    if invalid_record_count and not targets:
        warnings.append("repair_plan_has_invalid_records_without_targets")
    return ClaimEvidenceCorrectionRepairPlan(
        generated_at=datetime.now(timezone.utc),
        source_correction_log_path=str(path),
        source_record_count=source_record_count,
        source_valid_record_count=len(corrections),
        source_invalid_record_count=invalid_record_count,
        targets=targets,
        warnings=warnings,
    )


def write_claim_evidence_correction_repair_plan(
    plan: ClaimEvidenceCorrectionRepairPlan,
    out: Path,
) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return out


def build_claim_evidence_correction_repair_patch_template(
    *,
    repair_plan_path: Path,
) -> ClaimEvidenceCorrectionRepairPatchTemplate:
    repair_plan_path = Path(repair_plan_path).expanduser().resolve()
    plan = ClaimEvidenceCorrectionRepairPlan.model_validate_json(
        repair_plan_path.read_text(encoding="utf-8")
    )
    source_log_path = Path(plan.source_correction_log_path).expanduser().resolve()
    source_records = _source_records_by_line(source_log_path)
    records: list[ClaimEvidenceCorrectionRepairPatchTemplateRecord] = []
    warnings: list[str] = list(plan.warnings)

    for target in plan.targets:
        source_record = source_records.get(target.line_number, {})
        if not source_record:
            warnings.append(f"missing_source_record_for_line_{target.line_number}")
        patch_fields = {field: "" for field in target.missing_replay_fields}
        patch_record = dict(source_record)
        patch_record.update(patch_fields)
        records.append(
            ClaimEvidenceCorrectionRepairPatchTemplateRecord(
                line_number=target.line_number,
                source_correction_id=target.source_correction_id,
                paper_id=target.paper_id,
                run_id=target.run_id,
                claim_id=target.claim_id,
                missing_replay_fields=target.missing_replay_fields,
                available_replay_context=target.available_replay_context,
                suggested_lineage_values=_suggested_lineage_values_from_context(
                    target.available_replay_context
                ),
                patch_fields=patch_fields,
                source_record=source_record,
                patch_record=patch_record,
            )
        )

    return ClaimEvidenceCorrectionRepairPatchTemplate(
        generated_at=datetime.now(timezone.utc),
        source_repair_plan_path=str(repair_plan_path),
        source_correction_log_path=str(source_log_path),
        records=records,
        warnings=warnings,
    )


def write_claim_evidence_correction_repair_patch_template(
    template: ClaimEvidenceCorrectionRepairPatchTemplate,
    out: Path,
) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(template.model_dump_json(indent=2), encoding="utf-8")
    return out


def build_claim_evidence_correction_repaired_log_draft(
    *,
    patch_template_path: Path,
    out_log_path: Path | None = None,
    summary_out: Path | None = None,
) -> ClaimEvidenceCorrectionRepairedLogDraft:
    patch_template_path = Path(patch_template_path).expanduser().resolve()
    template = ClaimEvidenceCorrectionRepairPatchTemplate.model_validate_json(
        patch_template_path.read_text(encoding="utf-8")
    )
    repaired_records: dict[int, ClaimEvidenceCorrectionCase] = {}
    for record in template.records:
        patch_record = _completed_patch_record(record)
        repaired = ClaimEvidenceCorrectionCase.model_validate(patch_record)
        if not repaired.accepted_for_eval:
            raise ValueError(f"repair_patch_record_not_accepted_for_eval: line_{record.line_number}")
        repaired_records[record.line_number] = repaired

    out_log: Path | None = None
    if out_log_path is not None:
        out_log = Path(out_log_path).expanduser().resolve()
        out_log.parent.mkdir(parents=True, exist_ok=True)
        lines = [repaired_records[line].model_dump_json() for line in sorted(repaired_records)]
        out_log.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    draft = ClaimEvidenceCorrectionRepairedLogDraft(
        generated_at=datetime.now(timezone.utc),
        source_patch_template_path=str(patch_template_path),
        source_correction_log_path=template.source_correction_log_path,
        repaired_log_path=str(out_log) if out_log is not None else None,
        record_count=template.target_count,
        repaired_record_count=len(repaired_records),
        warnings=list(template.warnings),
    )
    if summary_out is not None:
        write_claim_evidence_correction_repaired_log_draft(draft, summary_out)
    return draft


def write_claim_evidence_correction_repaired_log_draft(
    draft: ClaimEvidenceCorrectionRepairedLogDraft,
    out: Path,
) -> Path:
    out = Path(out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    return out


def _completed_patch_record(record: ClaimEvidenceCorrectionRepairPatchTemplateRecord) -> dict[str, Any]:
    missing_fields = set(record.missing_replay_fields)
    patch_fields = {str(key): str(value or "").strip() for key, value in record.patch_fields.items()}
    missing_patch_keys = sorted(missing_fields - set(patch_fields))
    if missing_patch_keys:
        raise ValueError(
            f"repair_patch_fields_missing: line_{record.line_number}:{','.join(missing_patch_keys)}"
        )
    blank_patch_keys = sorted(key for key in missing_fields if not patch_fields.get(key))
    if blank_patch_keys:
        raise ValueError(
            f"repair_patch_fields_blank: line_{record.line_number}:{','.join(blank_patch_keys)}"
        )
    patch_record = dict(record.source_record or record.patch_record)
    patch_record.update({key: patch_fields[key] for key in sorted(missing_fields)})
    return patch_record


def _source_records_by_line(path: Path) -> dict[int, dict[str, Any]]:
    records: dict[int, dict[str, Any]] = {}
    if not path.exists():
        return records
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            records[line_number] = payload
    return records


def _suggested_lineage_values_from_context(context: dict[str, str]) -> dict[str, str]:
    suggestions: dict[str, str] = {}
    provider_names = _unique_context_values(context, ".provider_name")
    provider_models = _unique_context_values(context, ".provider_model")
    model_versions = _unique_context_values_for_suffixes(
        context,
        (".model_version", ".llm_model_version"),
    )
    if len(provider_names) == 1:
        suggestions["llm_provider"] = provider_names[0]
    if len(provider_models) == 1:
        suggestions["llm_model"] = provider_models[0]
    if len(model_versions) == 1:
        suggestions["llm_model_version"] = model_versions[0]
    if "run_meta.reader_profile_version" in context:
        suggestions["reader_profile_version"] = context["run_meta.reader_profile_version"]
    return suggestions


def _unique_context_values_for_suffixes(context: dict[str, str], suffixes: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for suffix in suffixes:
        for value in _unique_context_values(context, suffix):
            if value in seen:
                continue
            seen.add(value)
            values.append(value)
    return values


def _unique_context_values(context: dict[str, str], suffix: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for key, value in sorted(context.items()):
        if not key.endswith(suffix):
            continue
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return values


def _diagnostic_detail(exc: Exception) -> str | None:
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(item) for item in first.get("loc", ()) if str(item))
            msg = str(first.get("msg") or "").strip()
            if loc and msg:
                return f"{loc}: {msg}"
            return msg or loc or None
    text = str(exc).strip().splitlines()
    return text[0] if text else None


def _missing_replay_fields(line: str) -> list[str]:
    try:
        payload = json.loads(line)
    except Exception:
        return []
    if not isinstance(payload, dict) or not payload.get("accepted_for_eval"):
        return []
    missing: list[str] = []
    if not payload.get("before_evidence_refs"):
        missing.append("before_evidence_refs")
    if not payload.get("after_evidence_refs"):
        missing.append("after_evidence_refs")
    for field_name in CLAIM_EVIDENCE_REPLAY_LINEAGE_FIELDS:
        if not str(payload.get(field_name) or "").strip():
            missing.append(field_name)
    return missing


def _source_record_reason_codes(line: str) -> list[str]:
    try:
        payload = json.loads(line)
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    raw_codes = payload.get("reason_codes")
    if isinstance(raw_codes, str):
        raw_values = [raw_codes]
    elif isinstance(raw_codes, list):
        raw_values = raw_codes
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw_code in raw_values:
        code = str(raw_code or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _source_record_available_replay_context(line: str, *, log_path: Path) -> dict[str, str]:
    try:
        payload = json.loads(line)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}

    out: dict[str, str] = {}
    for field_name in CLAIM_EVIDENCE_REPLAY_LINEAGE_FIELDS:
        _add_context_value(out, f"source_record.{field_name}", payload.get(field_name))
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in CLAIM_EVIDENCE_REPLAY_CONTEXT_METADATA_KEYS:
            _add_context_value(out, f"source_record.metadata.{key}", metadata.get(key))

    paper_id = str(payload.get("paper_id") or "").strip()
    run_id = str(payload.get("run_id") or "").strip()
    if paper_id and run_id:
        run_meta = _load_source_record_run_meta(log_path=log_path, paper_id=paper_id, run_id=run_id)
        if isinstance(run_meta, dict):
            for field_name in CLAIM_EVIDENCE_REPLAY_LINEAGE_FIELDS:
                _add_context_value(out, f"run_meta.{field_name}", run_meta.get(field_name))
            _add_context_value(out, "run_meta.status", run_meta.get("status"))
            _add_context_value(out, "run_meta.selected_backend", run_meta.get("selected_backend"))
            _add_context_value(out, "run_meta.payload_class", run_meta.get("payload_class"))
            _add_context_value(out, "run_meta.redaction_applied", run_meta.get("redaction_applied"))
            lanes = run_meta.get("inference_lanes")
            if isinstance(lanes, dict):
                for lane_name in sorted(lanes):
                    lane = lanes.get(lane_name)
                    if not isinstance(lane, dict):
                        continue
                    prefix = f"run_meta.inference_lanes.{lane_name}"
                    for key in (
                        "selected_backend",
                        "payload_class",
                        "redaction_applied",
                        "provider_name",
                        "provider_model",
                    ):
                        _add_context_value(out, f"{prefix}.{key}", lane.get(key))
    return dict(sorted(out.items()))


def _load_source_record_run_meta(*, log_path: Path, paper_id: str, run_id: str) -> dict[str, Any] | None:
    run_meta_path = Path(log_path).expanduser().resolve().parent / "artifacts" / paper_id / run_id / "run_meta.json"
    try:
        payload = json.loads(run_meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _add_context_value(out: dict[str, str], key: str, value: object) -> None:
    if isinstance(value, bool):
        raw_text = "true" if value else "false"
    else:
        raw_text = str(value or "").strip()
    text = sanitize_event_text_for_log(raw_text)
    if text:
        out[key] = text


def _source_record_identity_fields(line: str) -> dict[str, str]:
    try:
        payload = json.loads(line)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, str] = {}
    for source_key, diagnostic_key in (
        ("correction_id", "source_correction_id"),
        ("paper_id", "paper_id"),
        ("run_id", "run_id"),
        ("claim_id", "claim_id"),
    ):
        value = str(payload.get(source_key) or "").strip()
        if value:
            out[diagnostic_key] = value
    return out


def build_claim_evidence_eval_candidate(correction: ClaimEvidenceCorrectionCase) -> ClaimEvidenceCorrectionEvalCandidate:
    return ClaimEvidenceCorrectionEvalCandidate(
        source_correction_id=correction.correction_id,
        source_feedback_id=correction.related_feedback_id,
        paper_id=correction.paper_id,
        run_id=correction.run_id,
        claim_id=correction.claim_id,
        field_path=correction.field_path,
        before_claim_text=correction.before_claim_text,
        after_claim_text=correction.after_claim_text,
        before_evidence_refs=correction.before_evidence_refs,
        after_evidence_refs=correction.after_evidence_refs,
        reason_codes=correction.reason_codes,
        parser_version=correction.parser_version,
        llm_provider=correction.llm_provider,
        llm_model=correction.llm_model,
        llm_model_version=correction.llm_model_version,
        prompt_version=correction.prompt_version,
        reader_profile_version=correction.reader_profile_version,
        reviewer_id=correction.reviewer_id,
        correction_created_at=correction.created_at,
        feedback_export_status=correction.feedback_export_status,
        metadata=correction.metadata,
    )


def _normalized_optional_path(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    return str(Path(text).expanduser().resolve())


def build_claim_evidence_eval_candidate_export(
    corrections: list[ClaimEvidenceCorrectionCase],
    *,
    paper_id: str | None = None,
    run_id: str | None = None,
    claim_id: str | None = None,
    reason_code: str | None = None,
    feedback_export_status: ClaimEvidenceCorrectionFeedbackExportStatus | None = None,
    limit: int = 500,
    source_correction_log_path: str | None = None,
    source_record_count: int | None = None,
    source_invalid_record_count: int = 0,
    source_invalid_record_diagnostics: list[ClaimEvidenceCorrectionSourceRecordDiagnostic] | None = None,
) -> ClaimEvidenceCorrectionEvalCandidateExport:
    candidates: list[ClaimEvidenceCorrectionEvalCandidate] = []
    skipped_not_accepted_count = 0
    skipped_filter_count = 0
    skipped_limit_count = 0
    for correction in reversed(corrections):
        if not correction.accepted_for_eval:
            skipped_not_accepted_count += 1
            continue
        if paper_id and correction.paper_id != paper_id:
            skipped_filter_count += 1
            continue
        if run_id and correction.run_id != run_id:
            skipped_filter_count += 1
            continue
        if claim_id and correction.claim_id != claim_id:
            skipped_filter_count += 1
            continue
        if reason_code and reason_code not in correction.reason_codes:
            skipped_filter_count += 1
            continue
        if feedback_export_status and correction.feedback_export_status != feedback_export_status:
            skipped_filter_count += 1
            continue

        if len(candidates) >= limit:
            skipped_limit_count += 1
            continue
        candidates.append(build_claim_evidence_eval_candidate(correction))

    filters = {
        "accepted_for_eval": True,
        "paper_id": paper_id,
        "run_id": run_id,
        "claim_id": claim_id,
        "reason_code": reason_code,
        "feedback_export_status": feedback_export_status,
        "limit": limit,
    }
    return ClaimEvidenceCorrectionEvalCandidateExport(
        generated_at=datetime.now(timezone.utc),
        candidate_count=len(candidates),
        source_correction_log_path=_normalized_optional_path(source_correction_log_path),
        source_record_count=source_record_count if source_record_count is not None else len(corrections),
        source_valid_record_count=len(corrections),
        source_invalid_record_count=source_invalid_record_count,
        skipped_not_accepted_count=skipped_not_accepted_count,
        skipped_filter_count=skipped_filter_count,
        skipped_limit_count=skipped_limit_count,
        source_invalid_record_diagnostics=list(source_invalid_record_diagnostics or []),
        filters={key: value for key, value in filters.items() if value is not None},
        candidates=candidates,
    )


def write_claim_evidence_eval_candidate_export(
    export: ClaimEvidenceCorrectionEvalCandidateExport,
    out: Path,
    *,
    jsonl: bool = False,
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if jsonl:
        with out.open("w", encoding="utf-8") as handle:
            for candidate in export.candidates:
                handle.write(candidate.model_dump_json())
                handle.write("\n")
    else:
        out.write_text(export.model_dump_json(indent=2), encoding="utf-8")
    return out


def claim_evidence_eval_candidate_export_replayability_findings(
    export: ClaimEvidenceCorrectionEvalCandidateExport,
) -> list[str]:
    findings: list[str] = []
    if export.candidate_count != len(export.candidates):
        findings.append("candidate_count_mismatch")
    if export.source_invalid_record_count:
        findings.append("source_invalid_records")

    replayable_count = 0
    nonreplayable_count = 0
    for candidate in export.candidates:
        if _claim_evidence_eval_candidate_is_replayable(candidate):
            replayable_count += 1
        else:
            nonreplayable_count += 1

    if export.candidates and nonreplayable_count:
        findings.append("nonreplayable_candidates")
    if replayable_count == 0:
        findings.append("no_replayable_candidates")
    return findings


def _claim_evidence_eval_candidate_is_replayable(candidate: ClaimEvidenceCorrectionEvalCandidate) -> bool:
    if not str(candidate.source_correction_id or "").strip():
        return False
    if not candidate.before_evidence_refs or not candidate.after_evidence_refs:
        return False
    if not candidate.reason_codes:
        return False
    for field_name in CLAIM_EVIDENCE_REPLAY_LINEAGE_FIELDS:
        if not str(getattr(candidate, field_name) or "").strip():
            return False
    return True


def load_claim_evidence_eval_candidate_export_from_path(
    path: Path,
) -> ClaimEvidenceCorrectionEvalCandidateExport:
    path = Path(path).expanduser().resolve()
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return ClaimEvidenceCorrectionEvalCandidateExport(
            generated_at=datetime.now(timezone.utc),
            candidate_count=0,
            candidates=[],
        )
    if path.suffix == ".jsonl":
        candidates = [
            ClaimEvidenceCorrectionEvalCandidate.model_validate_json(line)
            for line in text.splitlines()
            if line.strip()
        ]
        return ClaimEvidenceCorrectionEvalCandidateExport(
            generated_at=datetime.now(timezone.utc),
            candidate_count=len(candidates),
            filters={"source_format": "jsonl"},
            candidates=candidates,
        )
    return ClaimEvidenceCorrectionEvalCandidateExport.model_validate(json.loads(text))


def _safe_intake_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "candidate"


def build_claim_evidence_eval_review_record(
    candidate: ClaimEvidenceCorrectionEvalCandidate,
) -> ClaimEvidenceCorrectionEvalReviewRecord:
    return ClaimEvidenceCorrectionEvalReviewRecord(
        intake_id=_safe_intake_segment(
            f"{candidate.paper_id}_{candidate.run_id}_{candidate.claim_id}_{candidate.source_correction_id}"
        ),
        created_at=datetime.now(timezone.utc),
        source_candidate=candidate,
    )


def write_claim_evidence_eval_review_intake(
    export: ClaimEvidenceCorrectionEvalCandidateExport,
    *,
    records_dir: Path,
    source_export_path: Path | None = None,
    overwrite: bool = False,
) -> ClaimEvidenceCorrectionEvalReviewManifest:
    records_dir.mkdir(parents=True, exist_ok=True)
    record_paths: list[str] = []
    skipped_existing_count = 0

    for candidate in export.candidates:
        record = build_claim_evidence_eval_review_record(candidate)
        path = records_dir / f"{record.intake_id}.json"
        if path.exists() and not overwrite:
            skipped_existing_count += 1
            continue
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        record_paths.append(str(path))

    manifest = ClaimEvidenceCorrectionEvalReviewManifest(
        generated_at=datetime.now(timezone.utc),
        source_export_path=str(source_export_path) if source_export_path else None,
        records_dir=str(records_dir),
        record_count=len(record_paths),
        skipped_existing_count=skipped_existing_count,
        record_paths=record_paths,
    )
    (records_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def load_claim_evidence_eval_review_records(
    records_dir: Path,
    *,
    include_decision_files: bool = False,
) -> list[tuple[Path, ClaimEvidenceCorrectionEvalReviewRecord]]:
    if not records_dir.exists():
        return []

    records: list[tuple[Path, ClaimEvidenceCorrectionEvalReviewRecord]] = []
    for path in sorted(records_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        if not include_decision_files and path.parent.name in {"decisions", "reviewed"}:
            continue
        try:
            records.append((path, ClaimEvidenceCorrectionEvalReviewRecord.model_validate_json(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return records


def _latest_review_decisions_by_intake(
    decisions_dir: Path,
) -> dict[str, ClaimEvidenceCorrectionEvalReviewDecision]:
    out: dict[str, ClaimEvidenceCorrectionEvalReviewDecision] = {}
    if not decisions_dir.exists():
        return out
    for path in sorted(decisions_dir.glob("*.json")):
        try:
            decision = ClaimEvidenceCorrectionEvalReviewDecision.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        current = out.get(decision.intake_id)
        if current is None or decision.reviewed_at >= current.reviewed_at:
            out[decision.intake_id] = decision
    return out


def list_claim_evidence_eval_review_queue(
    records_dir: Path,
    *,
    include_resolved: bool = False,
) -> list[dict[str, object]]:
    decisions = _latest_review_decisions_by_intake(records_dir / "decisions")
    rows: list[dict[str, object]] = []
    for path, record in load_claim_evidence_eval_review_records(records_dir):
        decision = decisions.get(record.intake_id)
        if decision is not None and not include_resolved:
            continue
        candidate = record.source_candidate
        rows.append(
            {
                "intake_id": record.intake_id,
                "paper_id": candidate.paper_id,
                "run_id": candidate.run_id,
                "claim_id": candidate.claim_id,
                "reason_codes": candidate.reason_codes,
                "record_path": str(path),
                "reviewed": decision is not None,
                "review_resolution": decision.resolution if decision else None,
                "approved_for_eval": decision.approved_for_eval if decision else False,
                "reviewed_at": decision.reviewed_at.isoformat() if decision else None,
                "reviewed_fixture_path": decision.reviewed_fixture_path if decision else None,
            }
        )
    return rows


def _load_review_record_by_intake_id(
    records_dir: Path,
    intake_id: str,
) -> tuple[Path, ClaimEvidenceCorrectionEvalReviewRecord]:
    for path, record in load_claim_evidence_eval_review_records(records_dir):
        if record.intake_id == intake_id:
            return path, record
    raise FileNotFoundError(f"claim_evidence_eval_intake_missing={intake_id}")


def resolve_claim_evidence_eval_review_record(
    *,
    records_dir: Path,
    intake_id: str,
    resolution: ClaimEvidenceEvalReviewResolution,
    reviewer_id: str,
    notes: str = "",
) -> ClaimEvidenceCorrectionEvalReviewDecision:
    source_path, record = _load_review_record_by_intake_id(records_dir, intake_id)
    reviewed_at = datetime.now(timezone.utc)
    reviewer = reviewer_id.strip() or "human"
    normalized_notes = notes.strip()
    approved_for_eval = resolution == "APPROVE_FOR_EVAL"

    decisions_dir = records_dir / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    reviewed_dir = records_dir / "reviewed"
    decision_id = _safe_intake_segment(
        f"{intake_id}_{resolution}_{reviewed_at.isoformat().replace(':', '').replace('-', '')}"
    )
    reviewed_fixture_path: str | None = None

    decision = ClaimEvidenceCorrectionEvalReviewDecision(
        decision_id=decision_id,
        intake_id=intake_id,
        reviewed_at=reviewed_at,
        reviewer_id=reviewer,
        resolution=resolution,
        approved_for_eval=approved_for_eval,
        notes=normalized_notes,
        source_record_path=str(source_path),
        source_record=record,
    )

    if approved_for_eval:
        reviewed_dir.mkdir(parents=True, exist_ok=True)
        fixture = ClaimEvidenceCorrectionReviewedEvalFixture(
            source_decision_id=decision_id,
            intake_id=intake_id,
            reviewed_at=reviewed_at,
            reviewer_id=reviewer,
            source_candidate=record.source_candidate,
            review_notes=normalized_notes,
        )
        fixture_path = reviewed_dir / f"{intake_id}.json"
        fixture_path.write_text(fixture.model_dump_json(indent=2), encoding="utf-8")
        reviewed_fixture_path = str(fixture_path)
        decision = decision.model_copy(update={"reviewed_fixture_path": reviewed_fixture_path})

    decision_path = decisions_dir / f"{decision_id}.json"
    decision_path.write_text(decision.model_dump_json(indent=2), encoding="utf-8")
    with (decisions_dir / "decisions.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(decision.model_dump_json())
        handle.write("\n")
    return decision


def load_claim_evidence_reviewed_eval_fixtures(
    reviewed_dir: Path,
    *,
    paper_id: str | None = None,
    run_id: str | None = None,
    claim_id: str | None = None,
) -> list[ClaimEvidenceCorrectionReviewedEvalFixture]:
    if not reviewed_dir.exists():
        return []
    fixtures: list[ClaimEvidenceCorrectionReviewedEvalFixture] = []
    for path in sorted(reviewed_dir.glob("*.json")):
        try:
            fixture = ClaimEvidenceCorrectionReviewedEvalFixture.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        candidate = fixture.source_candidate
        if paper_id and candidate.paper_id != paper_id:
            continue
        if run_id and candidate.run_id != run_id:
            continue
        if claim_id and candidate.claim_id != claim_id:
            continue
        fixtures.append(fixture)
    return fixtures


def write_claim_evidence_reviewed_eval_fixtures_sidecar(
    *,
    reviewed_dir: Path,
    run_dir: Path,
    paper_id: str | None = None,
    run_id: str | None = None,
    claim_id: str | None = None,
) -> tuple[Path, int]:
    fixtures = load_claim_evidence_reviewed_eval_fixtures(
        reviewed_dir,
        paper_id=paper_id,
        run_id=run_id,
        claim_id=claim_id,
    )
    path = run_dir / "claim_evidence_reviewed_eval_fixtures.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle = ClaimEvidenceCorrectionReviewedEvalFixturesBundle(
        generated_at=datetime.now(timezone.utc),
        source_reviewed_dir=str(reviewed_dir),
        paper_id=paper_id,
        run_id=run_id,
        claim_id=claim_id,
        fixture_count=len(fixtures),
        fixtures=fixtures,
    )
    path.write_text(json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return path, len(fixtures)
