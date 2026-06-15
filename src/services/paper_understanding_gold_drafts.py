from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from src.schemas.claim_evidence_correction import (
    ClaimEvidenceCorrectionLocator,
    ClaimEvidenceCorrectionReviewedEvalFixture,
)
from src.schemas.paper_understanding_gold import (
    PaperUnderstandingGold,
    PaperUnderstandingGoldCandidateDraft,
    PaperUnderstandingGoldCandidateDraftCurationItem,
    PaperUnderstandingGoldCandidateDraftCurationProgressItem,
    PaperUnderstandingGoldCandidateDraftCurationProgressReport,
    PaperUnderstandingGoldCandidateDraftCurationReport,
    PaperUnderstandingGoldCandidateDraftCurationTask,
    PaperUnderstandingGoldCurationTaskExportItem,
    PaperUnderstandingGoldCurationTaskExportReport,
    PaperUnderstandingGoldCandidateDraftManifest,
    PaperUnderstandingGoldCandidateDraftPatchRequest,
    PaperUnderstandingGoldCandidateDraftPatchResult,
    PaperUnderstandingGoldCandidateDraftPatchResultManifest,
    PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest,
    PaperUnderstandingGoldCandidateDraftPatchTemplate,
    PaperUnderstandingGoldCandidateDraftPatchTemplateManifest,
    PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest,
    PaperUnderstandingGoldCandidateDraftPatchTemplateRequest,
    PaperUnderstandingGoldEvidenceLocator,
    PaperUnderstandingGoldMetadata,
    PaperUnderstandingGoldReviewerHandoffApplyPackage,
    PaperUnderstandingGoldReviewerHandoffApplyRequest,
    PaperUnderstandingGoldReviewerHandoffPackage,
    PaperUnderstandingGoldReviewerHandoffReleasePrepPackage,
    PaperUnderstandingGoldReviewerHandoffReleasePrepRequest,
    PaperUnderstandingGoldReviewerHandoffStagePackage,
    PaperUnderstandingGoldReviewerHandoffStageRequest,
    PaperUnderstandingGoldStagingManifest,
    PaperUnderstandingGoldStatement,
    PaperUnderstandingGoldTeacherVerificationCurationPackage,
)
from src.services.claim_evidence_corrections import load_claim_evidence_reviewed_eval_fixtures
from src.services.paper_understanding_gold_validation import (
    assess_paper_understanding_gold_readiness,
    build_paper_understanding_gold_release_package_from_split_plan,
    build_paper_understanding_gold_release_split_plan_from_staging_manifest,
)
from src.skills.storage import atomic_write_text


_PATCHABLE_GOLD_FIELDS = (
    "citation",
    "paper_type",
    "domain_tags",
    "gold_claims",
    "gold_methods",
    "gold_results",
    "gold_limitations",
    "gold_gaps",
    "important_figures",
    "important_tables",
    "notes",
)


class ReviewerHandoffApplyRequiresEditedError(ValueError):
    def __init__(self, findings: list[str]):
        self.findings = list(findings)
        super().__init__(
            "reviewer handoff apply requires edited patch templates: "
            + ",".join(self.findings)
        )


def build_paper_understanding_gold_candidate_drafts_from_reviewed_fixtures(
    *,
    reviewed_dir: Path,
    paper_id: str | None = None,
    run_id: str | None = None,
    claim_id: str | None = None,
) -> list[PaperUnderstandingGoldCandidateDraft]:
    fixtures = load_claim_evidence_reviewed_eval_fixtures(
        reviewed_dir,
        paper_id=paper_id,
        run_id=run_id,
        claim_id=claim_id,
    )
    grouped: dict[str, list[ClaimEvidenceCorrectionReviewedEvalFixture]] = {}
    for fixture in fixtures:
        candidate = fixture.source_candidate
        grouped.setdefault(candidate.paper_id, []).append(fixture)

    drafts: list[PaperUnderstandingGoldCandidateDraft] = []
    for grouped_paper_id, paper_fixtures in sorted(grouped.items()):
        draft = _paper_understanding_gold_from_reviewed_fixtures(
            paper_id=grouped_paper_id,
            fixtures=paper_fixtures,
        )
        if draft is None:
            continue
        readiness = assess_paper_understanding_gold_readiness(draft)
        drafts.append(
            PaperUnderstandingGoldCandidateDraft(
                generated_at=datetime.now(timezone.utc),
                source_reviewed_dir=str(reviewed_dir),
                paper_id=grouped_paper_id,
                fixture_count=len(paper_fixtures),
                readiness=readiness,
                draft=draft,
            )
        )
    return drafts


def write_paper_understanding_gold_candidate_drafts(
    *,
    reviewed_dir: Path,
    out_dir: Path,
    paper_id: str | None = None,
    run_id: str | None = None,
    claim_id: str | None = None,
) -> PaperUnderstandingGoldCandidateDraftManifest:
    drafts = build_paper_understanding_gold_candidate_drafts_from_reviewed_fixtures(
        reviewed_dir=reviewed_dir,
        paper_id=paper_id,
        run_id=run_id,
        claim_id=claim_id,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    draft_paths: list[str] = []
    readiness_counts = {"pass": 0, "warn": 0, "fail": 0}
    for draft in drafts:
        readiness_counts[draft.readiness.status] += 1
        path = out_dir / f"{_safe_path_segment(draft.paper_id)}.candidate_draft.json"
        atomic_write_text(path, draft.model_dump_json(indent=2))
        draft_paths.append(str(path))

    manifest = PaperUnderstandingGoldCandidateDraftManifest(
        generated_at=datetime.now(timezone.utc),
        source_reviewed_dir=str(reviewed_dir),
        out_dir=str(out_dir),
        draft_count=len(drafts),
        draft_paths=draft_paths,
        readiness_summary={
            "pass_count": readiness_counts["pass"],
            "warn_count": readiness_counts["warn"],
            "fail_count": readiness_counts["fail"],
        },
    )
    atomic_write_text(out_dir / "manifest.json", manifest.model_dump_json(indent=2))
    return manifest


def build_paper_understanding_gold_candidate_drafts_from_teacher_verification(
    *,
    paths: list[Path],
    require_accepted: bool = True,
) -> list[PaperUnderstandingGoldCandidateDraft]:
    drafts: list[PaperUnderstandingGoldCandidateDraft] = []
    for path in _iter_teacher_verification_paths(paths):
        payload = _load_teacher_verification_payload(path)
        if payload is None:
            continue
        if require_accepted and payload.get("accepted") is not True:
            continue
        draft = _paper_understanding_gold_from_teacher_verification(payload)
        if draft is None:
            continue
        readiness = assess_paper_understanding_gold_readiness(draft)
        teacher_claim_count = len(payload.get("teacher_output", {}).get("claims", []) or [])
        drafts.append(
            PaperUnderstandingGoldCandidateDraft(
                generated_at=datetime.now(timezone.utc),
                source_kind="teacher_verification",
                source_reviewed_dir=str(path),
                paper_id=draft.paper_id,
                fixture_count=teacher_claim_count,
                readiness=readiness,
                draft=draft,
            )
        )
    return drafts


def write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
    *,
    paths: list[Path],
    out_dir: Path,
    require_accepted: bool = True,
) -> PaperUnderstandingGoldCandidateDraftManifest:
    drafts = build_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=paths,
        require_accepted=require_accepted,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    draft_paths: list[str] = []
    readiness_counts = {"pass": 0, "warn": 0, "fail": 0}
    for draft in drafts:
        readiness_counts[draft.readiness.status] += 1
        path = out_dir / f"{_safe_path_segment(draft.paper_id)}.teacher_candidate_draft.json"
        atomic_write_text(path, draft.model_dump_json(indent=2))
        draft_paths.append(str(path))

    manifest = PaperUnderstandingGoldCandidateDraftManifest(
        generated_at=datetime.now(timezone.utc),
        source_reviewed_dir=";".join(str(path) for path in paths),
        out_dir=str(out_dir),
        draft_count=len(drafts),
        draft_paths=draft_paths,
        readiness_summary={
            "pass_count": readiness_counts["pass"],
            "warn_count": readiness_counts["warn"],
            "fail_count": readiness_counts["fail"],
        },
    )
    atomic_write_text(out_dir / "manifest.json", manifest.model_dump_json(indent=2))
    return manifest


def write_paper_understanding_gold_teacher_verification_curation_package(
    *,
    paths: list[Path],
    out_dir: Path,
    require_accepted: bool = True,
    report_id: str = "paper-understanding-gold-teacher-verification-curation",
    curation_report_out: Path | None = None,
    package_out: Path | None = None,
) -> PaperUnderstandingGoldTeacherVerificationCurationPackage:
    manifest = write_paper_understanding_gold_candidate_drafts_from_teacher_verification(
        paths=paths,
        out_dir=out_dir,
        require_accepted=require_accepted,
    )
    report_path = curation_report_out or out_dir / "curation_report.json"
    report = build_paper_understanding_gold_candidate_draft_curation_report(
        draft_paths=[out_dir],
        report_id=report_id,
        out=report_path,
    )
    warnings = list(report.warnings)
    if manifest.draft_count == 0:
        warnings.append("no_teacher_verification_drafts_written")
    package = PaperUnderstandingGoldTeacherVerificationCurationPackage(
        generated_at=datetime.now(timezone.utc),
        source_paths=[str(path) for path in paths],
        draft_manifest_path=str(out_dir / "manifest.json"),
        curation_report_path=str(report_path),
        draft_manifest=manifest,
        curation_report=report,
        curation_ready=report.curation_ready,
        warnings=warnings,
    )
    if package_out is not None:
        atomic_write_text(package_out, package.model_dump_json(indent=2))
    return package


def write_paper_understanding_gold_reviewer_handoff_package(
    *,
    paths: list[Path],
    out_dir: Path,
    require_accepted: bool = True,
    package_id: str = "paper-understanding-gold-reviewer-handoff",
    report_id: str = "paper-understanding-gold-teacher-verification-curation",
    reviewer_id: str | None = None,
    review_notes: str | None = None,
    reviewer_guide_out: Path | None = None,
    package_out: Path | None = None,
) -> PaperUnderstandingGoldReviewerHandoffPackage:
    out_dir = Path(out_dir).expanduser().resolve()
    drafts_dir = out_dir / "candidate_drafts"
    patch_templates_dir = out_dir / "patch_templates"
    patched_drafts_dir = out_dir / "patched_drafts"
    curation_package_path = out_dir / "curation_package.json"
    progress_report_path = out_dir / "curation_progress.json"
    task_export_path = out_dir / "curation_tasks.json"
    task_export_csv_path = out_dir / "curation_tasks.csv"
    reviewer_guide_path = (
        Path(reviewer_guide_out).expanduser().resolve()
        if reviewer_guide_out is not None
        else out_dir / "reviewer_guide.md"
    )

    curation_package = write_paper_understanding_gold_teacher_verification_curation_package(
        paths=paths,
        out_dir=drafts_dir,
        require_accepted=require_accepted,
        report_id=report_id,
        package_out=curation_package_path,
    )
    patch_template_manifest = write_paper_understanding_gold_candidate_draft_patch_template_manifest(
        PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest(
            curation_package_path=str(curation_package_path),
            out_dir=str(patch_templates_dir),
            patched_draft_out_dir=str(patched_drafts_dir),
            reviewer_id=reviewer_id,
            review_notes=review_notes,
        )
    )
    progress_report = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=curation_package_path,
        patch_template_paths=[patch_templates_dir / "manifest.json"],
        out=progress_report_path,
    )
    task_export = build_paper_understanding_gold_curation_task_export_report(
        curation_package_path=curation_package_path,
        patch_template_paths=[patch_templates_dir / "manifest.json"],
        progress_report_out=progress_report_path,
        csv_out=task_export_csv_path,
        out=task_export_path,
    )
    _write_paper_understanding_gold_reviewer_handoff_guide(
        out=reviewer_guide_path,
        handoff_package_path=Path(package_out).expanduser().resolve() if package_out is not None else None,
        curation_package_path=curation_package_path,
        patch_template_manifest_path=patch_templates_dir / "manifest.json",
        curation_progress_report_path=progress_report_path,
        curation_task_export_path=task_export_path,
        curation_task_export_csv_path=task_export_csv_path,
        task_export=task_export,
        base_dir=out_dir,
    )
    warnings = list(dict.fromkeys(
        list(curation_package.warnings)
        + list(patch_template_manifest.warnings)
        + list(progress_report.warnings)
        + list(task_export.warnings)
    ))
    handoff = PaperUnderstandingGoldReviewerHandoffPackage(
        generated_at=datetime.now(timezone.utc),
        package_id=package_id,
        source_paths=[str(path) for path in paths],
        curation_package_path=str(curation_package_path),
        patch_template_manifest_path=str(patch_templates_dir / "manifest.json"),
        curation_progress_report_path=str(progress_report_path),
        curation_task_export_path=str(task_export_path),
        curation_task_export_csv_path=str(task_export_csv_path),
        reviewer_guide_path=str(reviewer_guide_path),
        curation_package=curation_package,
        patch_template_manifest=patch_template_manifest,
        curation_progress_report=progress_report,
        curation_task_export=task_export,
        draft_count=curation_package.draft_manifest.draft_count,
        open_task_count=task_export.open_task_count,
        curation_ready=curation_package.curation_ready and task_export.open_task_count == 0,
        warnings=warnings,
    )
    if package_out is not None:
        atomic_write_text(Path(package_out).expanduser().resolve(), handoff.model_dump_json(indent=2))
    return handoff


def _write_paper_understanding_gold_reviewer_handoff_guide(
    *,
    out: Path,
    handoff_package_path: Path | None,
    curation_package_path: Path,
    patch_template_manifest_path: Path,
    curation_progress_report_path: Path,
    curation_task_export_path: Path,
    curation_task_export_csv_path: Path | None,
    task_export: PaperUnderstandingGoldCurationTaskExportReport,
    base_dir: Path,
) -> None:
    out = Path(out).expanduser().resolve()
    base_dir = Path(base_dir).expanduser().resolve()
    package_arg = _reviewer_guide_path(handoff_package_path, base_dir=base_dir) if handoff_package_path else "<reviewer_handoff_package.json>"
    apply_out_dir = base_dir.parent / f"{base_dir.name}_apply"
    command_base_dir = Path.cwd().expanduser().resolve()
    command_package_arg = (
        _reviewer_guide_path(handoff_package_path, base_dir=command_base_dir)
        if handoff_package_path
        else "<reviewer_handoff_package.json>"
    )
    lines = [
        "# Paper Understanding Gold Reviewer Handoff",
        "",
        "This is a non-canonical review aid. Do not treat candidate drafts or patch results as accepted fixed gold until they pass the ready-only staging and release gates.",
        "",
        "## Summary",
        "",
        f"- Paper count: {task_export.paper_count}",
        f"- Open task count: {task_export.open_task_count}",
        f"- Curation stage counts: {_format_count_map_for_guide(task_export.curation_stage_counts)}",
        f"- Review priority counts: {_format_count_map_for_guide(task_export.review_priority_counts)}",
        "",
        "## Files",
        "",
        f"- Handoff package: {package_arg}",
        f"- Curation package: {_reviewer_guide_path(curation_package_path, base_dir=base_dir)}",
        f"- Patch template manifest: {_reviewer_guide_path(patch_template_manifest_path, base_dir=base_dir)}",
        f"- Progress report: {_reviewer_guide_path(curation_progress_report_path, base_dir=base_dir)}",
        f"- Task export JSON: {_reviewer_guide_path(curation_task_export_path, base_dir=base_dir)}",
    ]
    if curation_task_export_csv_path is not None:
        lines.append(f"- Task export CSV: {_reviewer_guide_path(curation_task_export_csv_path, base_dir=base_dir)}")
    lines.extend(
        [
            "",
            "## Review Loop",
            "",
            "1. Open the highest-priority patch templates listed below.",
            "2. Edit only evidence-backed fields in each template's `patch_request`.",
            "3. Keep every claim, method, result, limitation, figure, and table locator grounded to source evidence.",
            "4. From the repository root, apply the handoff package and inspect edited/unedited counts before staging.",
            "",
            "```bash",
            ".venv/bin/python scripts/eval/apply_paper_understanding_gold_reviewer_handoff.py \\",
            f"  {command_package_arg} \\",
            f"  --out-dir {_reviewer_guide_path(apply_out_dir, base_dir=command_base_dir)} \\",
            f"  --out {_reviewer_guide_path(apply_out_dir / 'package.json', base_dir=command_base_dir)} \\",
            "  --require-edited",
            "```",
            "",
            "Expected before staging: `edited_result_count > 0`, `unedited_result_count = 0`, `not_ready_count = 0`, and `remaining_task_count = 0`.",
            "",
            "## Highest Priority Tasks",
            "",
        ]
    )
    if not task_export.items:
        lines.append("No open curation tasks remain.")
    else:
        _append_reviewer_guide_task_table(lines, task_export.items[:20], base_dir=base_dir)
        lines.extend(
            [
                "",
                "## Tasks By Stage",
                "",
            ]
        )
        for stage in sorted({item.curation_stage or "unspecified" for item in task_export.items}):
            stage_items = [item for item in task_export.items if (item.curation_stage or "unspecified") == stage]
            lines.extend(
                [
                    f"### {stage}",
                    "",
                    f"Open tasks: {len(stage_items)}",
                    "",
                ]
            )
            _append_reviewer_guide_task_table(lines, stage_items, base_dir=base_dir, include_guidance=True)
            lines.append("")
    lines.extend(
        [
            "## Notes",
            "",
            "- Evidence-free claims should remain unsupported/low-confidence until grounded evidence is added.",
            "- Limitation, method, result, and visual inventory tasks should be resolved separately rather than merged into one generic summary.",
            "- This guide is regenerated with the handoff package and is not canonical state.",
            "",
        ]
    )
    atomic_write_text(out, "\n".join(lines))


def _append_reviewer_guide_task_table(
    lines: list[str],
    items: list[PaperUnderstandingGoldCurationTaskExportItem],
    *,
    base_dir: Path,
    include_guidance: bool = False,
) -> None:
    if include_guidance:
        lines.extend(
            [
                "| Priority | Paper | Reason | Target | Count | Instruction | Evidence hint | Patch template |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
    else:
        lines.extend(
            [
                "| Priority | Stage | Paper | Reason | Target | Count | Patch template |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
    for item in items:
        count_summary = _reviewer_guide_count_summary(item.current_count, item.minimum_required)
        template_path = item.latest_patch_template_path or "-"
        if include_guidance:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(item.review_priority),
                        _markdown_table_cell(item.paper_id),
                        _markdown_table_cell(item.reason_code),
                        _markdown_table_cell(item.target_field),
                        _markdown_table_cell(count_summary),
                        _markdown_table_cell(item.instruction),
                        _markdown_table_cell(item.evidence_hint or "-"),
                        _markdown_table_cell(_reviewer_guide_path(Path(template_path), base_dir=base_dir) if template_path != "-" else "-"),
                    ]
                )
                + " |"
            )
        else:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(item.review_priority),
                        _markdown_table_cell(item.curation_stage or "-"),
                        _markdown_table_cell(item.paper_id),
                        _markdown_table_cell(item.reason_code),
                        _markdown_table_cell(item.target_field),
                        _markdown_table_cell(count_summary),
                        _markdown_table_cell(_reviewer_guide_path(Path(template_path), base_dir=base_dir) if template_path != "-" else "-"),
                    ]
                )
                + " |"
            )


def _format_count_map_for_guide(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _reviewer_guide_count_summary(current_count: int | None, minimum_required: int | None) -> str:
    if current_count is None and minimum_required is None:
        return "-"
    if minimum_required is None:
        return str(current_count if current_count is not None else "-")
    return f"{current_count if current_count is not None else '-'} / {minimum_required}"


def _reviewer_guide_path(path: Path, *, base_dir: Path) -> str:
    path = Path(path)
    if not str(path) or str(path) == ".":
        return "-"
    if not path.is_absolute():
        return str(path)
    resolved_path = path.expanduser().resolve()
    resolved_base = base_dir.expanduser().resolve()
    try:
        return str(resolved_path.relative_to(resolved_base))
    except ValueError:
        return os.path.relpath(resolved_path, resolved_base)


def _markdown_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def apply_paper_understanding_gold_reviewer_handoff_package(
    request: PaperUnderstandingGoldReviewerHandoffApplyRequest,
) -> PaperUnderstandingGoldReviewerHandoffApplyPackage:
    handoff_path = Path(request.reviewer_handoff_package_path).expanduser().resolve()
    handoff = PaperUnderstandingGoldReviewerHandoffPackage.model_validate_json(
        handoff_path.read_text(encoding="utf-8")
    )
    out_dir = Path(request.out_dir).expanduser().resolve()

    patch_template_manifest_path = _resolve_related_path(
        handoff.patch_template_manifest_path,
        base_path=handoff_path,
    )
    curation_package_path = _resolve_related_path(
        handoff.curation_package_path,
        base_path=handoff_path,
    )
    patch_results_dir = (
        Path(request.patch_results_dir).expanduser().resolve()
        if request.patch_results_dir
        else out_dir / "patch_results"
    )
    progress_report_path = (
        Path(request.curation_progress_report_out).expanduser().resolve()
        if request.curation_progress_report_out
        else out_dir / "curation_progress.json"
    )
    task_export_path = (
        Path(request.curation_task_export_out).expanduser().resolve()
        if request.curation_task_export_out
        else out_dir / "curation_tasks.json"
    )
    task_export_csv_path = (
        Path(request.curation_task_export_csv_out).expanduser().resolve()
        if request.curation_task_export_csv_out
        else out_dir / "curation_tasks.csv"
    )

    if request.require_edited:
        edit_findings = _reviewer_handoff_patch_template_edit_findings(patch_template_manifest_path)
        if edit_findings:
            raise ReviewerHandoffApplyRequiresEditedError(edit_findings)

    out_dir.mkdir(parents=True, exist_ok=True)
    patch_result_manifest = write_paper_understanding_gold_candidate_draft_patch_result_manifest(
        PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest(
            patch_template_paths=[str(patch_template_manifest_path)],
            out_dir=str(patch_results_dir),
        )
    )
    patch_result_manifest_path = patch_results_dir / "manifest.json"
    progress_report = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=curation_package_path,
        patch_template_paths=[patch_template_manifest_path],
        patch_result_paths=[patch_results_dir],
        out=progress_report_path,
    )
    task_export = build_paper_understanding_gold_curation_task_export_report(
        curation_package_path=curation_package_path,
        patch_template_paths=[patch_template_manifest_path],
        patch_result_paths=[patch_results_dir],
        progress_report_out=progress_report_path,
        csv_out=task_export_csv_path,
        out=task_export_path,
    )
    warnings = list(dict.fromkeys(
        list(handoff.warnings)
        + list(patch_result_manifest.warnings)
        + list(progress_report.warnings)
        + list(task_export.warnings)
    ))
    package = PaperUnderstandingGoldReviewerHandoffApplyPackage(
        generated_at=datetime.now(timezone.utc),
        apply_id=request.apply_id,
        reviewer_handoff_package_path=str(handoff_path),
        patch_result_manifest_path=str(patch_result_manifest_path),
        curation_progress_report_path=str(progress_report_path),
        curation_task_export_path=str(task_export_path),
        curation_task_export_csv_path=str(task_export_csv_path),
        patch_result_manifest=patch_result_manifest,
        curation_progress_report=progress_report,
        curation_task_export=task_export,
        result_count=patch_result_manifest.result_count,
        curation_ready_count=patch_result_manifest.curation_ready_count,
        not_ready_count=patch_result_manifest.not_ready_count,
        ready_to_stage_count=progress_report.ready_to_stage_count,
        remaining_task_count=task_export.open_task_count,
        warnings=warnings,
    )
    if request.out is not None:
        atomic_write_text(Path(request.out).expanduser().resolve(), package.model_dump_json(indent=2))
    return package


def _reviewer_handoff_patch_template_edit_findings(
    patch_template_manifest_path: Path,
) -> list[str]:
    template_paths = _iter_patch_template_paths([patch_template_manifest_path])
    edited_count = 0
    unedited_count = 0
    unedited_paths: list[Path] = []
    findings: list[str] = []

    for template_path in template_paths:
        try:
            template = _load_candidate_draft_patch_template(template_path)
            source_draft = _load_candidate_draft(Path(template.source_draft_path).expanduser().resolve())
        except (OSError, ValueError) as exc:
            findings.append(f"patch_edit_detection_failed={template_path}:{type(exc).__name__}")
            continue
        if _patch_request_fields_changed_from_source(template.patch_request, source_draft.draft):
            edited_count += 1
        else:
            unedited_count += 1
            unedited_paths.append(template_path)

    if not template_paths:
        findings.append("no_patch_templates_found")
    if edited_count <= 0:
        findings.append("no_edited_patch_results")
    if unedited_count > 0:
        findings.append(f"unedited_patch_result_count={unedited_count}")
        findings.append(f"unedited_patch_template_path_count={len(unedited_paths)}")
        sample = ",".join(str(path) for path in unedited_paths[:5])
        if sample:
            findings.append(f"unedited_patch_template_paths_sample={sample}")
    return findings


def stage_paper_understanding_gold_reviewer_handoff_apply_package(
    request: PaperUnderstandingGoldReviewerHandoffStageRequest,
) -> PaperUnderstandingGoldReviewerHandoffStagePackage:
    apply_package_path = Path(request.reviewer_handoff_apply_package_path).expanduser().resolve()
    apply_package = PaperUnderstandingGoldReviewerHandoffApplyPackage.model_validate_json(
        apply_package_path.read_text(encoding="utf-8")
    )
    handoff_path = _resolve_related_path(
        apply_package.reviewer_handoff_package_path,
        base_path=apply_package_path,
    )
    handoff = PaperUnderstandingGoldReviewerHandoffPackage.model_validate_json(
        handoff_path.read_text(encoding="utf-8")
    )
    patch_template_manifest_path = _resolve_related_path(
        handoff.patch_template_manifest_path,
        base_path=handoff_path,
    )
    curation_package_path = _resolve_related_path(
        handoff.curation_package_path,
        base_path=handoff_path,
    )
    patch_result_manifest_path = _resolve_related_path(
        apply_package.patch_result_manifest_path,
        base_path=apply_package_path,
    )
    patch_results_dir = patch_result_manifest_path.parent
    out_dir = Path(request.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    staged_gold_dir = (
        Path(request.staged_gold_out_dir).expanduser().resolve()
        if request.staged_gold_out_dir
        else out_dir / "staged_gold"
    )
    progress_report_path = (
        Path(request.curation_progress_report_out).expanduser().resolve()
        if request.curation_progress_report_out
        else out_dir / "curation_progress.json"
    )
    task_export_path = (
        Path(request.curation_task_export_out).expanduser().resolve()
        if request.curation_task_export_out
        else out_dir / "curation_tasks.json"
    )
    task_export_csv_path = (
        Path(request.curation_task_export_csv_out).expanduser().resolve()
        if request.curation_task_export_csv_out
        else out_dir / "curation_tasks.csv"
    )

    staging_manifest = stage_paper_understanding_gold_from_patch_results(
        patch_result_paths=[patch_result_manifest_path],
        out_dir=staged_gold_dir,
        require_ready=request.require_ready,
    )
    staging_manifest_path = staged_gold_dir / "staging_manifest.json"
    progress_report = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=curation_package_path,
        patch_template_paths=[patch_template_manifest_path],
        patch_result_paths=[patch_results_dir],
        staged_paths=[staged_gold_dir],
        out=progress_report_path,
    )
    task_export = build_paper_understanding_gold_curation_task_export_report(
        curation_package_path=curation_package_path,
        patch_template_paths=[patch_template_manifest_path],
        patch_result_paths=[patch_results_dir],
        staged_paths=[staged_gold_dir],
        progress_report_out=progress_report_path,
        csv_out=task_export_csv_path,
        out=task_export_path,
    )
    warnings = list(dict.fromkeys(
        list(apply_package.warnings)
        + list(staging_manifest.readiness_summary.get("warnings", []) or [])
        + list(progress_report.warnings)
        + list(task_export.warnings)
    ))
    package = PaperUnderstandingGoldReviewerHandoffStagePackage(
        generated_at=datetime.now(timezone.utc),
        stage_id=request.stage_id,
        reviewer_handoff_apply_package_path=str(apply_package_path),
        reviewer_handoff_package_path=str(handoff_path),
        staging_manifest_path=str(staging_manifest_path),
        curation_progress_report_path=str(progress_report_path),
        curation_task_export_path=str(task_export_path),
        curation_task_export_csv_path=str(task_export_csv_path),
        staging_manifest=staging_manifest,
        curation_progress_report=progress_report,
        curation_task_export=task_export,
        staged_count=staging_manifest.staged_count,
        curation_complete=progress_report.curation_complete,
        remaining_task_count=task_export.open_task_count,
        warnings=warnings,
    )
    if request.out is not None:
        atomic_write_text(Path(request.out).expanduser().resolve(), package.model_dump_json(indent=2))
    return package


def build_paper_understanding_gold_reviewer_handoff_release_prep_package(
    request: PaperUnderstandingGoldReviewerHandoffReleasePrepRequest,
) -> PaperUnderstandingGoldReviewerHandoffReleasePrepPackage:
    stage_package_path = Path(request.reviewer_handoff_stage_package_path).expanduser().resolve()
    stage_package = PaperUnderstandingGoldReviewerHandoffStagePackage.model_validate_json(
        stage_package_path.read_text(encoding="utf-8")
    )
    staging_manifest_path = _resolve_related_path(
        stage_package.staging_manifest_path,
        base_path=stage_package_path,
    )
    out_dir = Path(request.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    split_staging_out_dir = (
        Path(request.split_staging_out_dir).expanduser().resolve()
        if request.split_staging_out_dir
        else out_dir / "split_staging"
    )
    manifest_out_dir = (
        Path(request.manifest_out_dir).expanduser().resolve()
        if request.manifest_out_dir
        else out_dir / "manifests"
    )
    split_plan_path = (
        Path(request.split_plan_out).expanduser().resolve()
        if request.split_plan_out
        else out_dir / "release_split_plan.json"
    )
    release_readiness_path = (
        Path(request.release_readiness_out).expanduser().resolve()
        if request.release_readiness_out
        else out_dir / "release_readiness.json"
    )
    release_package_path = (
        Path(request.release_package_out).expanduser().resolve()
        if request.release_package_out
        else out_dir / "release_package.json"
    )

    split_plan = build_paper_understanding_gold_release_split_plan_from_staging_manifest(
        staging_manifest_path=staging_manifest_path,
        out_dir=split_staging_out_dir,
        manifest_out_dir=manifest_out_dir,
        plan_id=f"{request.release_prep_id}-split-plan",
        split_names=request.split_names,
        min_ready_per_split=request.min_ready_per_split,
        require_ready=request.require_ready,
        out=split_plan_path,
    )
    warnings = list(stage_package.warnings) + list(split_plan.warnings)
    release_package = None
    effective_release_package_path: Path | None = None
    effective_release_readiness_path: Path | None = None
    should_build_release_package = request.build_release_package and (
        split_plan.release_ready_candidate or not request.require_ready
    )
    if should_build_release_package:
        release_package = build_paper_understanding_gold_release_package_from_split_plan(
            goldset_id=request.goldset_id,
            split_plan_path=split_plan_path,
            release_readiness_out=release_readiness_path,
            package_id=f"{request.release_prep_id}-release-package",
            package_out=release_package_path,
            require_ready=request.require_ready,
            required_splits=request.required_splits,
            min_ready_per_split=request.min_ready_per_split,
            require_single_goldset_id=request.require_single_goldset_id,
        )
        effective_release_package_path = release_package_path
        effective_release_readiness_path = release_readiness_path
    elif request.build_release_package:
        warnings.append("release_package_skipped_split_plan_not_ready")
    else:
        warnings.append("release_package_skipped_by_request")

    package = PaperUnderstandingGoldReviewerHandoffReleasePrepPackage(
        generated_at=datetime.now(timezone.utc),
        release_prep_id=request.release_prep_id,
        reviewer_handoff_stage_package_path=str(stage_package_path),
        staging_manifest_path=str(staging_manifest_path),
        split_plan_path=str(split_plan_path),
        release_package_path=str(effective_release_package_path) if effective_release_package_path else None,
        release_readiness_report_path=str(effective_release_readiness_path) if effective_release_readiness_path else None,
        split_plan=split_plan,
        release_package=release_package,
        release_ready_candidate=split_plan.release_ready_candidate,
        release_ready=bool(release_package and release_package.release_readiness.release_ready),
        staged_count=stage_package.staged_count,
        split_count=len(split_plan.split_items),
        warnings=warnings,
    )
    if request.out is not None:
        atomic_write_text(Path(request.out).expanduser().resolve(), package.model_dump_json(indent=2))
    return package


def patch_paper_understanding_gold_candidate_draft(
    request: PaperUnderstandingGoldCandidateDraftPatchRequest,
) -> PaperUnderstandingGoldCandidateDraftPatchResult:
    source_path = Path(request.draft_path).expanduser().resolve()
    original = _load_candidate_draft(source_path)
    before_readiness = assess_paper_understanding_gold_readiness(original.draft)
    patch_payload: dict[str, Any] = {}
    changed_fields: list[str] = []
    for field_name in _PATCHABLE_GOLD_FIELDS:
        value = getattr(request, field_name)
        if value is None:
            continue
        patch_payload[field_name] = value
        changed_fields.append(field_name)
    warnings: list[str] = []
    if not changed_fields:
        warnings.append("no_patch_fields_supplied")
    patched_gold = original.draft.model_copy(update=patch_payload)
    patched_gold = PaperUnderstandingGold.model_validate(patched_gold.model_dump(mode="json"))
    after_readiness = assess_paper_understanding_gold_readiness(patched_gold)
    patched_draft = PaperUnderstandingGoldCandidateDraft(
        generated_at=datetime.now(timezone.utc),
        source_kind=original.source_kind,
        source_reviewed_dir=original.source_reviewed_dir,
        paper_id=original.paper_id,
        fixture_count=original.fixture_count,
        readiness=after_readiness,
        draft=patched_gold,
    )
    out_path = Path(request.out).expanduser().resolve() if request.out else None
    if out_path is not None:
        atomic_write_text(out_path, patched_draft.model_dump_json(indent=2))
    return PaperUnderstandingGoldCandidateDraftPatchResult(
        generated_at=datetime.now(timezone.utc),
        source_draft_path=str(source_path),
        patched_draft_path=str(out_path) if out_path is not None else None,
        reviewer_id=request.reviewer_id,
        review_notes=request.review_notes,
        changed_fields=changed_fields,
        before_readiness=before_readiness,
        after_readiness=after_readiness,
        curation_ready=after_readiness.status == "pass",
        patched_draft=patched_draft,
        warnings=warnings,
    )


def build_paper_understanding_gold_candidate_draft_patch_template(
    request: PaperUnderstandingGoldCandidateDraftPatchTemplateRequest,
) -> PaperUnderstandingGoldCandidateDraftPatchTemplate:
    source_path = Path(request.draft_path).expanduser().resolve()
    draft = _load_candidate_draft(source_path)
    readiness = assess_paper_understanding_gold_readiness(draft.draft)
    open_tasks = _draft_curation_tasks(draft, readiness.reason_codes)
    patch_request = PaperUnderstandingGoldCandidateDraftPatchRequest(
        draft_path=str(source_path),
        out=request.patched_draft_out,
        reviewer_id=request.reviewer_id,
        review_notes=request.review_notes,
        citation=draft.draft.citation,
        paper_type=draft.draft.paper_type,
        domain_tags=draft.draft.domain_tags,
        gold_claims=draft.draft.gold_claims,
        gold_methods=draft.draft.gold_methods,
        gold_results=draft.draft.gold_results,
        gold_limitations=draft.draft.gold_limitations,
        gold_gaps=draft.draft.gold_gaps,
        important_figures=draft.draft.important_figures,
        important_tables=draft.draft.important_tables,
        notes=draft.draft.notes,
    )
    warnings: list[str] = []
    if readiness.status == "pass":
        warnings.append("candidate_draft_already_ready")
    template = PaperUnderstandingGoldCandidateDraftPatchTemplate(
        generated_at=datetime.now(timezone.utc),
        source_draft_path=str(source_path),
        paper_id=draft.paper_id,
        readiness=readiness,
        open_tasks=open_tasks,
        patch_request=patch_request,
        template_notes=[
            "Edit patch_request fields, keep evidence_refs grounded, then submit the patch request.",
            "This template is a non-canonical review aid and does not promote the draft into fixed gold.",
        ],
        warnings=warnings,
    )
    if request.out is not None:
        atomic_write_text(Path(request.out).expanduser().resolve(), template.model_dump_json(indent=2))
    return template


def write_paper_understanding_gold_candidate_draft_patch_template_manifest(
    request: PaperUnderstandingGoldCandidateDraftPatchTemplateManifestRequest,
) -> PaperUnderstandingGoldCandidateDraftPatchTemplateManifest:
    package_path = Path(request.curation_package_path).expanduser().resolve()
    package = PaperUnderstandingGoldTeacherVerificationCurationPackage.model_validate_json(
        package_path.read_text(encoding="utf-8")
    )
    out_dir = Path(request.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    patched_out_dir = Path(request.patched_draft_out_dir).expanduser().resolve() if request.patched_draft_out_dir else None
    if patched_out_dir is not None:
        patched_out_dir.mkdir(parents=True, exist_ok=True)

    template_paths: list[str] = []
    readiness_counts = {"pass": 0, "warn": 0, "fail": 0}
    open_task_count = 0
    warnings: list[str] = []
    for draft_path_raw in package.draft_manifest.draft_paths:
        draft_path = Path(draft_path_raw).expanduser().resolve()
        draft = _load_candidate_draft(draft_path)
        patched_out = (
            str(patched_out_dir / f"{_safe_path_segment(draft.paper_id)}.patched_candidate_draft.json")
            if patched_out_dir is not None
            else None
        )
        template_path = out_dir / f"{_safe_path_segment(draft.paper_id)}.patch_template.json"
        template = build_paper_understanding_gold_candidate_draft_patch_template(
            PaperUnderstandingGoldCandidateDraftPatchTemplateRequest(
                draft_path=str(draft_path),
                patched_draft_out=patched_out,
                reviewer_id=request.reviewer_id,
                review_notes=request.review_notes,
                out=str(template_path),
            )
        )
        readiness_counts[template.readiness.status] += 1
        open_task_count += len(template.open_tasks)
        template_paths.append(str(template_path))

    if not template_paths:
        warnings.append("no_patch_templates_written")
    manifest = PaperUnderstandingGoldCandidateDraftPatchTemplateManifest(
        generated_at=datetime.now(timezone.utc),
        curation_package_path=str(package_path),
        out_dir=str(out_dir),
        template_count=len(template_paths),
        open_task_count=open_task_count,
        template_paths=template_paths,
        readiness_summary={
            "pass_count": readiness_counts["pass"],
            "warn_count": readiness_counts["warn"],
            "fail_count": readiness_counts["fail"],
        },
        warnings=warnings,
    )
    atomic_write_text(out_dir / "manifest.json", manifest.model_dump_json(indent=2))
    return manifest


def write_paper_understanding_gold_candidate_draft_patch_result_manifest(
    request: PaperUnderstandingGoldCandidateDraftPatchResultManifestRequest,
) -> PaperUnderstandingGoldCandidateDraftPatchResultManifest:
    out_dir = Path(request.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    template_paths = _iter_patch_template_paths(
        [Path(path).expanduser().resolve() for path in request.patch_template_paths]
    )
    result_paths: list[str] = []
    readiness_counts = {"pass": 0, "warn": 0, "fail": 0}
    curation_ready_count = 0
    edited_result_count = 0
    unedited_result_count = 0
    warnings: list[str] = []

    for template_path in template_paths:
        try:
            template = _load_candidate_draft_patch_template(template_path)
        except (OSError, ValueError) as exc:
            warnings.append(f"patch_template_skipped={template_path}:{type(exc).__name__}")
            continue
        result_path = out_dir / f"{_safe_path_segment(template.paper_id)}.patch_result.json"
        request_payload = template.patch_request.model_copy()
        result = patch_paper_understanding_gold_candidate_draft(request_payload)
        readiness_counts[result.after_readiness.status] += 1
        if result.curation_ready:
            curation_ready_count += 1
        edited_fields: list[str]
        try:
            source_draft = _load_candidate_draft(Path(template.source_draft_path).expanduser().resolve())
            edited_fields = _patch_request_fields_changed_from_source(
                template.patch_request,
                source_draft.draft,
            )
        except (OSError, ValueError) as exc:
            warnings.append(f"patch_edit_detection_fallback={template_path}:{type(exc).__name__}")
            edited_fields = list(result.changed_fields)
        if edited_fields:
            edited_result_count += 1
        else:
            unedited_result_count += 1
        atomic_write_text(result_path, result.model_dump_json(indent=2))
        result_paths.append(str(result_path))

    if not result_paths:
        warnings.append("no_patch_results_written")
    if unedited_result_count:
        warnings.append(f"unedited_patch_result_count={unedited_result_count}")
    if result_paths and unedited_result_count == len(result_paths):
        warnings.append("all_patch_results_unedited")
    manifest = PaperUnderstandingGoldCandidateDraftPatchResultManifest(
        generated_at=datetime.now(timezone.utc),
        source_patch_template_paths=[str(path) for path in template_paths],
        out_dir=str(out_dir),
        result_count=len(result_paths),
        curation_ready_count=curation_ready_count,
        not_ready_count=len(result_paths) - curation_ready_count,
        edited_result_count=edited_result_count,
        unedited_result_count=unedited_result_count,
        patch_result_paths=result_paths,
        readiness_summary={
            "pass_count": readiness_counts["pass"],
            "warn_count": readiness_counts["warn"],
            "fail_count": readiness_counts["fail"],
        },
        warnings=warnings,
    )
    atomic_write_text(out_dir / "manifest.json", manifest.model_dump_json(indent=2))
    return manifest


def _patch_request_fields_changed_from_source(
    request: PaperUnderstandingGoldCandidateDraftPatchRequest,
    source: PaperUnderstandingGold,
) -> list[str]:
    changed_fields: list[str] = []
    for field_name in _PATCHABLE_GOLD_FIELDS:
        requested_value = getattr(request, field_name)
        if requested_value is None:
            continue
        source_value = getattr(source, field_name)
        if _json_comparable(requested_value) != _json_comparable(source_value):
            changed_fields.append(field_name)
    return changed_fields


def _json_comparable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_json_comparable(item) for item in value]
    if isinstance(value, tuple):
        return [_json_comparable(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _json_comparable(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    return value


def stage_paper_understanding_gold_from_candidate_drafts(
    *,
    draft_paths: list[Path],
    out_dir: Path,
    require_ready: bool = True,
) -> PaperUnderstandingGoldStagingManifest:
    drafts = [_load_candidate_draft(path) for path in draft_paths]
    readiness_counts = {"pass": 0, "warn": 0, "fail": 0}
    not_ready_errors: list[str] = []
    for path, draft in zip(draft_paths, drafts, strict=True):
        readiness = assess_paper_understanding_gold_readiness(draft.draft)
        readiness_counts[readiness.status] += 1
        if require_ready and readiness.status != "pass":
            not_ready_errors.append(
                f"path={path} paper_id={draft.paper_id} readiness={readiness.status} "
                f"reason_codes={','.join(readiness.reason_codes)}"
            )
    if not_ready_errors:
        raise ValueError("cannot stage not-ready paper understanding gold drafts: " + "; ".join(not_ready_errors))

    out_dir.mkdir(parents=True, exist_ok=True)
    staged_paths: list[str] = []
    for draft in drafts:
        path = out_dir / f"{_safe_path_segment(draft.paper_id)}.json"
        atomic_write_text(path, draft.draft.model_dump_json(indent=2))
        staged_paths.append(str(path))

    manifest = PaperUnderstandingGoldStagingManifest(
        generated_at=datetime.now(timezone.utc),
        source_draft_paths=[str(path) for path in draft_paths],
        out_dir=str(out_dir),
        require_ready=require_ready,
        staged_count=len(staged_paths),
        staged_paths=staged_paths,
        readiness_summary={
            "pass_count": readiness_counts["pass"],
            "warn_count": readiness_counts["warn"],
            "fail_count": readiness_counts["fail"],
        },
    )
    atomic_write_text(out_dir / "staging_manifest.json", manifest.model_dump_json(indent=2))
    return manifest


def stage_paper_understanding_gold_from_patch_results(
    *,
    patch_result_paths: list[Path],
    out_dir: Path,
    require_ready: bool = True,
) -> PaperUnderstandingGoldStagingManifest:
    patched_draft_paths = _patched_candidate_draft_paths_from_patch_results(patch_result_paths)
    if not patched_draft_paths:
        raise ValueError("no patched candidate draft paths found in patch result inputs")
    return stage_paper_understanding_gold_from_candidate_drafts(
        draft_paths=patched_draft_paths,
        out_dir=out_dir,
        require_ready=require_ready,
    )


def build_paper_understanding_gold_candidate_draft_curation_progress_report(
    *,
    curation_package_path: Path,
    patch_template_paths: list[Path] | None = None,
    patch_result_paths: list[Path] | None = None,
    staged_paths: list[Path] | None = None,
    report_id: str = "paper-understanding-gold-candidate-draft-curation-progress",
    out: Path | None = None,
) -> PaperUnderstandingGoldCandidateDraftCurationProgressReport:
    package_path = Path(curation_package_path).expanduser().resolve()
    package = PaperUnderstandingGoldTeacherVerificationCurationPackage.model_validate_json(
        package_path.read_text(encoding="utf-8")
    )
    patch_templates = _latest_patch_templates_by_paper(patch_template_paths or [])
    patch_results = _latest_patch_results_by_paper(patch_result_paths or [])
    staged = _staged_gold_paths_by_paper(staged_paths or [])
    items: list[PaperUnderstandingGoldCandidateDraftCurationProgressItem] = []
    warnings: list[str] = []

    for curation_item in package.curation_report.items:
        template_entry = patch_templates.get(curation_item.paper_id)
        patch_entry = patch_results.get(curation_item.paper_id)
        staged_path = staged.get(curation_item.paper_id)
        patch_template = template_entry[1] if template_entry is not None else None
        patch_result = patch_entry[1] if patch_entry is not None else None
        latest_template_path = str(template_entry[0]) if template_entry is not None else None
        latest_patch_path = str(patch_entry[0]) if patch_entry is not None else None
        patched_draft_path = patch_result.patched_draft_path if patch_result is not None else None

        if staged_path is not None:
            status = "staged"
        elif patch_result is not None and patch_result.after_readiness.status == "pass":
            status = "ready_to_stage"
        elif patch_result is not None:
            status = "patched_not_ready"
        elif patch_template is not None:
            status = "templated"
        else:
            status = "not_started"

        if patch_result is None:
            if patch_template is None:
                readiness_status = curation_item.readiness_status
                reason_codes = curation_item.readiness_reason_codes
                open_tasks = curation_item.tasks
            else:
                readiness_status = patch_template.readiness.status
                reason_codes = patch_template.readiness.reason_codes
                open_tasks = patch_template.open_tasks
        else:
            readiness_status = patch_result.after_readiness.status
            reason_codes = patch_result.after_readiness.reason_codes
            open_tasks = (
                []
                if readiness_status == "pass"
                else _draft_curation_tasks(patch_result.patched_draft, reason_codes)
            )
        if status == "staged":
            open_tasks = []
            reason_codes = []
            readiness_status = "pass"

        items.append(
            PaperUnderstandingGoldCandidateDraftCurationProgressItem(
                paper_id=curation_item.paper_id,
                source_draft_path=curation_item.draft_path,
                latest_patch_template_path=latest_template_path,
                latest_patch_result_path=latest_patch_path,
                patched_draft_path=patched_draft_path,
                staged_gold_path=str(staged_path) if staged_path is not None else None,
                status=status,
                readiness_status=readiness_status,
                readiness_reason_codes=reason_codes,
                open_task_count=len(open_tasks),
                open_tasks=open_tasks,
            )
        )

    known_paper_ids = {item.paper_id for item in items}
    extra_template_papers = sorted(set(patch_templates) - known_paper_ids)
    extra_patch_papers = sorted(set(patch_results) - known_paper_ids)
    extra_staged_papers = sorted(set(staged) - known_paper_ids)
    if extra_template_papers:
        warnings.append(f"patch_templates_not_in_package={','.join(extra_template_papers)}")
    if extra_patch_papers:
        warnings.append(f"patch_results_not_in_package={','.join(extra_patch_papers)}")
    if extra_staged_papers:
        warnings.append(f"staged_gold_not_in_package={','.join(extra_staged_papers)}")
    if any(item.status != "staged" for item in items):
        warnings.append("curation_progress_incomplete")

    not_started_count = sum(1 for item in items if item.status == "not_started")
    templated_count = sum(1 for item in items if item.status == "templated")
    patched_count = sum(1 for item in items if item.status in {"patched_not_ready", "ready_to_stage", "staged"})
    ready_to_stage_count = sum(1 for item in items if item.status == "ready_to_stage")
    staged_count = sum(1 for item in items if item.status == "staged")
    remaining_task_count = sum(item.open_task_count for item in items)
    report = PaperUnderstandingGoldCandidateDraftCurationProgressReport(
        generated_at=datetime.now(timezone.utc),
        report_id=report_id,
        curation_package_path=str(package_path),
        draft_count=len(items),
        not_started_count=not_started_count,
        templated_count=templated_count,
        patched_count=patched_count,
        ready_to_stage_count=ready_to_stage_count,
        staged_count=staged_count,
        remaining_task_count=remaining_task_count,
        curation_complete=bool(items) and staged_count == len(items),
        items=items,
        warnings=warnings,
    )
    if out is not None:
        atomic_write_text(Path(out), report.model_dump_json(indent=2))
    return report


def build_paper_understanding_gold_curation_task_export_report(
    *,
    curation_package_path: Path,
    patch_template_paths: list[Path] | None = None,
    patch_result_paths: list[Path] | None = None,
    staged_paths: list[Path] | None = None,
    export_id: str = "paper-understanding-gold-curation-task-export",
    progress_report_out: Path | None = None,
    csv_out: Path | None = None,
    out: Path | None = None,
) -> PaperUnderstandingGoldCurationTaskExportReport:
    progress_report = build_paper_understanding_gold_candidate_draft_curation_progress_report(
        curation_package_path=curation_package_path,
        patch_template_paths=patch_template_paths,
        patch_result_paths=patch_result_paths,
        staged_paths=staged_paths,
        out=progress_report_out,
    )
    items: list[PaperUnderstandingGoldCurationTaskExportItem] = []
    status_counts: dict[str, int] = {}
    reason_code_counts: dict[str, int] = {}
    target_field_counts: dict[str, int] = {}
    curation_stage_counts: dict[str, int] = {}
    review_priority_counts: dict[str, int] = {}

    for progress_item in progress_report.items:
        status_counts[progress_item.status] = status_counts.get(progress_item.status, 0) + 1
        for task in progress_item.open_tasks:
            reason_code_counts[task.reason_code] = reason_code_counts.get(task.reason_code, 0) + 1
            target_field_counts[task.target_field] = target_field_counts.get(task.target_field, 0) + 1
            curation_stage = task.curation_stage or "unspecified"
            curation_stage_counts[curation_stage] = curation_stage_counts.get(curation_stage, 0) + 1
            priority_key = str(task.review_priority)
            review_priority_counts[priority_key] = review_priority_counts.get(priority_key, 0) + 1
            items.append(
                PaperUnderstandingGoldCurationTaskExportItem(
                    paper_id=progress_item.paper_id,
                    task_id=task.task_id,
                    status=progress_item.status,
                    readiness_status=progress_item.readiness_status,
                    reason_code=task.reason_code,
                    target_field=task.target_field,
                    curation_stage=task.curation_stage,
                    review_priority=task.review_priority,
                    current_count=task.current_count,
                    minimum_required=task.minimum_required,
                    maximum_recommended=task.maximum_recommended,
                    instruction=task.instruction,
                    evidence_hint=task.evidence_hint,
                    source_draft_path=progress_item.source_draft_path,
                    latest_patch_template_path=progress_item.latest_patch_template_path,
                    latest_patch_result_path=progress_item.latest_patch_result_path,
                    patched_draft_path=progress_item.patched_draft_path,
                )
            )
    items.sort(key=lambda item: (item.review_priority, item.paper_id, item.task_id))

    warnings = list(progress_report.warnings)
    if not items:
        warnings.append("no_open_curation_tasks")
    report = PaperUnderstandingGoldCurationTaskExportReport(
        generated_at=datetime.now(timezone.utc),
        export_id=export_id,
        curation_progress_report_path=str(Path(progress_report_out).expanduser().resolve())
        if progress_report_out is not None
        else None,
        curation_package_path=progress_report.curation_package_path,
        paper_count=progress_report.draft_count,
        open_task_count=len(items),
        status_counts=status_counts,
        reason_code_counts=reason_code_counts,
        target_field_counts=target_field_counts,
        curation_stage_counts=curation_stage_counts,
        review_priority_counts=review_priority_counts,
        items=items,
        warnings=warnings,
    )
    if csv_out is not None:
        _write_curation_task_export_csv(Path(csv_out), report)
    if out is not None:
        atomic_write_text(Path(out), report.model_dump_json(indent=2))
    return report


def build_paper_understanding_gold_candidate_draft_curation_report(
    *,
    draft_paths: list[Path],
    report_id: str = "paper-understanding-gold-candidate-draft-curation",
    out: Path | None = None,
) -> PaperUnderstandingGoldCandidateDraftCurationReport:
    items: list[PaperUnderstandingGoldCandidateDraftCurationItem] = []
    reason_code_counts: dict[str, int] = {}
    warnings: list[str] = []
    for path in _iter_candidate_draft_paths(draft_paths):
        try:
            draft = _load_candidate_draft(path)
        except (OSError, ValueError) as exc:
            warnings.append(f"candidate_draft_load_failed: path={path} error={exc}")
            continue
        readiness = assess_paper_understanding_gold_readiness(draft.draft)
        for code in readiness.reason_codes:
            reason_code_counts[code] = reason_code_counts.get(code, 0) + 1
        items.append(
            PaperUnderstandingGoldCandidateDraftCurationItem(
                paper_id=draft.paper_id,
                draft_path=str(path),
                source_kind=draft.source_kind,
                readiness_status=readiness.status,
                readiness_reason_codes=readiness.reason_codes,
                claim_count=len(draft.draft.gold_claims),
                method_count=len(draft.draft.gold_methods),
                result_count=len(draft.draft.gold_results),
                limitation_count=len(draft.draft.gold_limitations),
                gap_count=len(draft.draft.gold_gaps),
                figure_count=len(draft.draft.important_figures),
                table_count=len(draft.draft.important_tables),
                next_actions=_draft_next_actions(readiness.reason_codes),
                tasks=_draft_curation_tasks(draft, readiness.reason_codes),
            )
        )

    ready_count = sum(1 for item in items if item.readiness_status == "pass")
    warn_count = sum(1 for item in items if item.readiness_status == "warn")
    fail_count = sum(1 for item in items if item.readiness_status == "fail")
    if not items:
        warnings.append("no_candidate_drafts_loaded")
    if fail_count:
        warnings.append("candidate_drafts_not_ready")
    report = PaperUnderstandingGoldCandidateDraftCurationReport(
        generated_at=datetime.now(timezone.utc),
        report_id=report_id,
        draft_count=len(items),
        ready_count=ready_count,
        warn_count=warn_count,
        fail_count=fail_count,
        reason_code_counts=reason_code_counts,
        curation_ready=bool(items) and fail_count == 0,
        items=items,
        warnings=warnings,
    )
    if out is not None:
        atomic_write_text(Path(out), report.model_dump_json(indent=2))
    return report


def _load_candidate_draft(path: Path) -> PaperUnderstandingGoldCandidateDraft:
    return PaperUnderstandingGoldCandidateDraft.model_validate_json(path.read_text(encoding="utf-8"))


def _load_candidate_draft_patch_result(path: Path) -> PaperUnderstandingGoldCandidateDraftPatchResult:
    return PaperUnderstandingGoldCandidateDraftPatchResult.model_validate_json(path.read_text(encoding="utf-8"))


def _load_candidate_draft_patch_template(path: Path) -> PaperUnderstandingGoldCandidateDraftPatchTemplate:
    return PaperUnderstandingGoldCandidateDraftPatchTemplate.model_validate_json(path.read_text(encoding="utf-8"))


def _resolve_related_path(raw_path: str, *, base_path: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (Path(base_path).expanduser().resolve().parent / path).resolve()


def _write_curation_task_export_csv(
    path: Path,
    report: PaperUnderstandingGoldCurationTaskExportReport,
) -> None:
    fieldnames = [
        "paper_id",
        "task_id",
        "status",
        "readiness_status",
        "reason_code",
        "target_field",
        "curation_stage",
        "review_priority",
        "current_count",
        "minimum_required",
        "maximum_recommended",
        "instruction",
        "evidence_hint",
        "source_draft_path",
        "latest_patch_template_path",
        "latest_patch_result_path",
        "patched_draft_path",
    ]
    rows = []
    for item in report.items:
        payload = item.model_dump(mode="json")
        rows.append({field: payload.get(field, "") for field in fieldnames})
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _iter_candidate_draft_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path.is_dir():
            out.extend(
                sorted(
                    item
                    for item in path.rglob("*.json")
                    if item.is_file() and item.name != "manifest.json"
                )
            )
        elif path.is_file():
            out.append(path)
    return out


def _iter_json_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path.is_dir():
            out.extend(sorted(item for item in path.rglob("*.json") if item.is_file()))
        elif path.is_file():
            out.append(path)
    return out


def _iter_patch_template_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path.is_dir():
            out.extend(sorted(item for item in path.rglob("*.json") if item.is_file()))
            continue
        if not path.is_file():
            continue
        try:
            manifest = PaperUnderstandingGoldCandidateDraftPatchTemplateManifest.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            out.append(path)
            continue
        out.extend(Path(template_path).expanduser() for template_path in manifest.template_paths)
    return out


def _iter_patch_result_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path.is_dir():
            out.extend(sorted(item for item in path.rglob("*.json") if item.is_file()))
            continue
        if not path.is_file():
            continue
        try:
            manifest = PaperUnderstandingGoldCandidateDraftPatchResultManifest.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            out.append(path)
            continue
        out.extend(Path(result_path).expanduser() for result_path in manifest.patch_result_paths)
    return out


def _patched_candidate_draft_paths_from_patch_results(paths: list[Path]) -> list[Path]:
    patched_paths: list[Path] = []
    seen: set[str] = set()
    for path in _iter_patch_result_paths(paths):
        try:
            result = _load_candidate_draft_patch_result(path)
        except (OSError, ValueError):
            continue
        if result.patched_draft_path is None:
            continue
        patched_path = Path(result.patched_draft_path).expanduser()
        key = str(patched_path)
        if key in seen:
            continue
        seen.add(key)
        patched_paths.append(patched_path)
    return patched_paths


def _latest_patch_templates_by_paper(
    paths: list[Path],
) -> dict[str, tuple[Path, PaperUnderstandingGoldCandidateDraftPatchTemplate]]:
    latest: dict[str, tuple[Path, PaperUnderstandingGoldCandidateDraftPatchTemplate]] = {}
    for path in _iter_patch_template_paths(paths):
        try:
            template = _load_candidate_draft_patch_template(path)
        except (OSError, ValueError):
            continue
        current = latest.get(template.paper_id)
        if current is None or template.generated_at >= current[1].generated_at:
            latest[template.paper_id] = (path, template)
    return latest


def _latest_patch_results_by_paper(
    paths: list[Path],
) -> dict[str, tuple[Path, PaperUnderstandingGoldCandidateDraftPatchResult]]:
    latest: dict[str, tuple[Path, PaperUnderstandingGoldCandidateDraftPatchResult]] = {}
    for path in _iter_json_paths(paths):
        try:
            result = _load_candidate_draft_patch_result(path)
        except (OSError, ValueError):
            continue
        paper_id = result.patched_draft.paper_id
        current = latest.get(paper_id)
        if current is None or result.generated_at >= current[1].generated_at:
            latest[paper_id] = (path, result)
    return latest


def _staged_gold_paths_by_paper(paths: list[Path]) -> dict[str, Path]:
    staged: dict[str, Path] = {}
    for path in _iter_json_paths(paths):
        if path.name in {"manifest.json", "staging_manifest.json"}:
            continue
        try:
            gold = PaperUnderstandingGold.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        staged[gold.paper_id] = path
    return staged


def _draft_next_actions(reason_codes: list[str]) -> list[str]:
    action_by_reason = {
        "CLAIM_COUNT_OUT_OF_RANGE": "Curate 3-7 core claims with evidence.",
        "METHOD_MISSING": "Add at least one grounded method statement.",
        "RESULT_MISSING": "Add at least one grounded result statement.",
        "LIMITATION_MISSING": "Add at least one grounded limitation statement.",
        "DOMAIN_TAGS_MISSING": "Add representative domain tags.",
        "PAPER_TYPE_OTHER": "Set a specific paper_type.",
        "IMPORTANT_VISUALS_MISSING": "List important figures or tables when present.",
        "EXTERNAL_ID_MISSING": "Add DOI or PMID for metadata matching.",
    }
    return [action_by_reason.get(code, f"Review readiness reason {code}.") for code in reason_codes]


def _draft_curation_tasks(
    draft: PaperUnderstandingGoldCandidateDraft,
    reason_codes: list[str],
) -> list[PaperUnderstandingGoldCandidateDraftCurationTask]:
    counts = {
        "gold_claims": len(draft.draft.gold_claims),
        "gold_methods": len(draft.draft.gold_methods),
        "gold_results": len(draft.draft.gold_results),
        "gold_limitations": len(draft.draft.gold_limitations),
        "domain_tags": len(draft.draft.domain_tags),
        "important_visuals": len(draft.draft.important_figures) + len(draft.draft.important_tables),
        "external_ids": int(bool(draft.draft.citation.doi or draft.draft.citation.pmid)),
        "paper_type": int(draft.draft.paper_type != "other"),
    }
    task_specs = {
        "CLAIM_COUNT_OUT_OF_RANGE": {
            "target_field": "gold_claims",
            "curation_stage": "claim_set",
            "review_priority": 30,
            "current_count": counts["gold_claims"],
            "minimum_required": 3,
            "maximum_recommended": 7,
            "instruction": "Curate 3-7 core claims and keep each claim tied to source evidence.",
            "evidence_hint": "Start from teacher/reviewed claim statements, then merge duplicates and remove unsupported claims.",
        },
        "METHOD_MISSING": {
            "target_field": "gold_methods",
            "curation_stage": "method_context",
            "review_priority": 40,
            "current_count": counts["gold_methods"],
            "minimum_required": 1,
            "instruction": "Add at least one grounded method statement that describes how the study, review, assay, or analysis was performed.",
            "evidence_hint": "Look for Methods, Study Design, Participants, Assay, Data Sources, or Recommendation Process passages.",
        },
        "RESULT_MISSING": {
            "target_field": "gold_results",
            "curation_stage": "result_context",
            "review_priority": 50,
            "current_count": counts["gold_results"],
            "minimum_required": 1,
            "instruction": "Add at least one grounded result or finding statement distinct from method and limitation context.",
            "evidence_hint": "Teacher claims with type=finding are candidate result sources but still need human review.",
        },
        "LIMITATION_MISSING": {
            "target_field": "gold_limitations",
            "curation_stage": "limitation_context",
            "review_priority": 60,
            "current_count": counts["gold_limitations"],
            "minimum_required": 1,
            "instruction": "Add at least one grounded limitation statement so limitation recall can be evaluated.",
            "evidence_hint": "Look for Limitations, Discussion caveats, uncertainty, bias, cohort, assay, or generalizability passages.",
        },
        "DOMAIN_TAGS_MISSING": {
            "target_field": "domain_tags",
            "curation_stage": "metadata",
            "review_priority": 25,
            "current_count": counts["domain_tags"],
            "minimum_required": 1,
            "instruction": "Add representative domain tags for fixed-goldset slicing.",
            "evidence_hint": "Use stable research-area tags such as biomarker, neuroimaging, bilingualism, delivery, or organoid.",
        },
        "PAPER_TYPE_OTHER": {
            "target_field": "paper_type",
            "curation_stage": "metadata",
            "review_priority": 20,
            "current_count": counts["paper_type"],
            "minimum_required": 1,
            "instruction": "Set a specific paper_type rather than other.",
            "evidence_hint": "Choose from primary_research, review, systematic_review, meta_analysis, methods, case_report, guideline, or other.",
        },
        "IMPORTANT_VISUALS_MISSING": {
            "target_field": "important_figures_or_tables",
            "curation_stage": "visual_inventory",
            "review_priority": 70,
            "current_count": counts["important_visuals"],
            "minimum_required": 1,
            "instruction": "List important figures or tables when the paper has reusable visual evidence.",
            "evidence_hint": "Use figure/table IDs already present in evidence locators first, then add key visuals from captions or tables.",
        },
        "EXTERNAL_ID_MISSING": {
            "target_field": "citation.doi_or_pmid",
            "curation_stage": "metadata",
            "review_priority": 10,
            "current_count": counts["external_ids"],
            "minimum_required": 1,
            "instruction": "Add DOI or PMID for metadata matching and duplicate detection.",
            "evidence_hint": "Prefer DOI from the paper metadata; use PMID when DOI is unavailable.",
        },
    }
    tasks: list[PaperUnderstandingGoldCandidateDraftCurationTask] = []
    for code in reason_codes:
        spec = task_specs.get(code)
        if spec is None:
            spec = {
                "target_field": "draft",
                "curation_stage": "general_review",
                "review_priority": 100,
                "instruction": f"Review readiness reason {code}.",
            }
        tasks.append(
            PaperUnderstandingGoldCandidateDraftCurationTask(
                task_id=f"{_safe_path_segment(draft.paper_id)}::{code}",
                reason_code=code,
                **spec,
            )
        )
    return tasks


def _paper_understanding_gold_from_reviewed_fixtures(
    *,
    paper_id: str,
    fixtures: list[ClaimEvidenceCorrectionReviewedEvalFixture],
) -> PaperUnderstandingGold | None:
    statements: list[PaperUnderstandingGoldStatement] = []
    seen_statement_ids: set[str] = set()
    for fixture in fixtures:
        candidate = fixture.source_candidate
        evidence_refs = [
            _gold_locator_from_correction_locator(locator)
            for locator in candidate.after_evidence_refs
            if _correction_locator_has_signal(locator)
        ]
        if not evidence_refs:
            continue
        statement_id = _unique_statement_id(f"reviewed-{candidate.source_correction_id}", seen_statement_ids)
        statements.append(
            PaperUnderstandingGoldStatement(
                statement_id=statement_id,
                kind="claim",
                text=candidate.after_claim_text,
                evidence_refs=evidence_refs,
                review_failure_codes=candidate.reason_codes,
                notes=(
                    "Drafted from reviewed claim/evidence correction fixture; "
                    "requires human curation before accepted gold promotion."
                ),
            )
        )
    if not statements:
        return None
    return PaperUnderstandingGold(
        paper_id=paper_id,
        citation=PaperUnderstandingGoldMetadata(title="Reviewed claim/evidence correction draft"),
        paper_type="other",
        domain_tags=["claim_evidence_correction_review"],
        gold_claims=statements,
        notes=(
            "Non-canonical candidate draft generated from reviewed claim/evidence corrections. "
            "Add method/result/limitation/gap context, citation metadata, and visual/table inventory before "
            "using as fixed accepted gold."
        ),
    )


def _paper_understanding_gold_from_teacher_verification(payload: dict[str, Any]) -> PaperUnderstandingGold | None:
    teacher_output = payload.get("teacher_output")
    if not isinstance(teacher_output, dict):
        return None
    paper_id = str(payload.get("paper_id") or "").strip()
    if not paper_id:
        return None
    claims = teacher_output.get("claims")
    if not isinstance(claims, list):
        return None

    statements_by_kind: dict[str, list[PaperUnderstandingGoldStatement]] = {
        "claim": [],
        "method": [],
        "result": [],
        "limitation": [],
        "gap": [],
    }
    seen_statement_ids: set[str] = set()
    figure_ids: set[str] = set()
    table_ids: set[str] = set()
    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            continue
        statement = str(claim.get("statement") or "").strip()
        if not statement:
            continue
        evidence_refs = []
        evidence_spans = claim.get("evidence_spans") or []
        if not isinstance(evidence_spans, list):
            evidence_spans = []
        for span in evidence_spans:
            if not isinstance(span, dict):
                continue
            locator = _gold_locator_from_teacher_span(span)
            if locator is None:
                continue
            evidence_refs.append(locator)
            if locator.figure_id:
                figure_ids.add(locator.figure_id)
            if locator.table_id:
                table_ids.add(locator.table_id)
        if not evidence_refs:
            continue
        kind = _statement_kind_from_teacher_claim_type(str(claim.get("type") or "claim"))
        claim_id = str(claim.get("claim_id") or f"teacher-claim-{index}")
        statement_id = _unique_statement_id(f"teacher-{claim_id}", seen_statement_ids)
        statements_by_kind[kind].append(
            PaperUnderstandingGoldStatement(
                statement_id=statement_id,
                kind=kind,
                text=statement,
                evidence_refs=evidence_refs,
                tags=["teacher_verification"],
                notes=(
                    "Drafted from accepted teacher_verification.v1 output; requires human curation before "
                    "accepted fixed-goldset promotion."
                ),
            )
        )

    if not any(statements_by_kind.values()):
        return None

    title = _title_from_teacher_output(teacher_output, paper_id=paper_id)
    return PaperUnderstandingGold(
        paper_id=paper_id,
        citation=PaperUnderstandingGoldMetadata(title=title),
        paper_type="other",
        domain_tags=["teacher_verification"],
        gold_claims=statements_by_kind["claim"],
        gold_methods=statements_by_kind["method"],
        gold_results=statements_by_kind["result"],
        gold_limitations=statements_by_kind["limitation"],
        gold_gaps=statements_by_kind["gap"],
        important_figures=[
            {"figure_id": figure_id, "label": figure_id}
            for figure_id in sorted(figure_ids)
        ],
        important_tables=[
            {"table_id": table_id, "label": table_id}
            for table_id in sorted(table_ids)
        ],
        notes=(
            "Non-canonical candidate draft generated from teacher_verification.v1. "
            "Add citation metadata, method/result/limitation/gap coverage, and visual/table inventory before "
            "using as fixed accepted gold."
        ),
    )


def _gold_locator_from_teacher_span(span: dict[str, Any]) -> PaperUnderstandingGoldEvidenceLocator | None:
    source_span = span.get("source_span")
    char_start = span.get("char_start")
    char_end = span.get("char_end")
    if isinstance(source_span, list) and len(source_span) == 2:
        char_start = char_start if char_start is not None else source_span[0]
        char_end = char_end if char_end is not None else source_span[1]
    quote = str(span.get("quote") or span.get("raw_text") or "").strip()
    if not quote:
        return None
    locator_kwargs = {
        "page": span.get("page"),
        "chunk_id": span.get("chunk_id"),
        "char_start": char_start,
        "char_end": char_end,
        "quote": quote,
        "section": span.get("section"),
        "figure_id": span.get("figure_id"),
        "table_id": span.get("table_id"),
        "cell_id": span.get("cell_id"),
        "bbox_pdf": span.get("bbox_pdf"),
        "bbox_pct": span.get("bbox_pct"),
        "note": span.get("rationale"),
    }
    if not any(
        locator_kwargs.get(key) is not None
        for key in ("page", "chunk_id", "char_start", "figure_id", "table_id", "bbox_pdf", "bbox_pct")
    ):
        return None
    return PaperUnderstandingGoldEvidenceLocator(**locator_kwargs)


def _statement_kind_from_teacher_claim_type(raw_type: str) -> str:
    normalized = raw_type.strip().lower().replace("-", "_")
    if "method" in normalized or "assay" in normalized or "protocol" in normalized:
        return "method"
    if "limitation" in normalized:
        return "limitation"
    if "gap" in normalized or "future" in normalized:
        return "gap"
    if "result" in normalized or "outcome" in normalized:
        return "result"
    return "claim"


def _title_from_teacher_output(teacher_output: dict[str, Any], *, paper_id: str) -> str:
    doc_id = str(teacher_output.get("doc_id") or "").strip()
    if not doc_id:
        return paper_id
    if doc_id.startswith("file:"):
        doc_id = doc_id.removeprefix("file:")
    return doc_id.removesuffix(".pdf").strip() or paper_id


def _iter_teacher_verification_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path.is_dir():
            out.extend(sorted(item for item in path.rglob("*.json") if item.is_file()))
        elif path.is_file():
            out.append(path)
    return out


def _load_teacher_verification_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != "teacher_verification.v1":
        return None
    return payload


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
    return any(
        value is not None
        for value in (
            locator.page,
            locator.chunk_id,
            locator.char_start,
            locator.figure_id,
            locator.table_id,
            locator.bbox_pdf,
            locator.bbox_pct,
        )
    )


def _safe_path_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "paper"


def _unique_statement_id(raw: str, seen: set[str]) -> str:
    base = _safe_path_segment(raw)
    candidate = base
    index = 2
    while candidate in seen:
        candidate = f"{base}-{index}"
        index += 1
    seen.add(candidate)
    return candidate
