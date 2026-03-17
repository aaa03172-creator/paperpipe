from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.schemas.agent_artifacts import EvidenceSpan, StatCheckEntry, StatsReport, VerificationStatus
from src.services.runtime_paths import artifact_paper_dir_candidates, preferred_artifact_paper_dir


DEFAULT_STATS_REPAIR_PAPER_IDS = [
    "zotero:schindlerHeadtoheadComparisonLeading2024",
    "zotero:duboisAmnesticMCIProdromal2004",
    "zotero:hanssonAlzheimersAssociationAppropriate2022",
]


@dataclass(frozen=True)
class StatsSeedResult:
    paper_id: str
    run_id: str | None
    status: str
    checks: int = 0
    reason: str = ""


def _safe_load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _iter_run_dirs(paper_dir: Path) -> Iterable[Path]:
    if not paper_dir.exists():
        return []
    run_dirs = [p for p in paper_dir.iterdir() if p.is_dir()]
    run_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return run_dirs


def _select_run_dir(paper_dir: Path, run_id: str | None) -> Path | None:
    if run_id:
        candidate = paper_dir / run_id
        return candidate if candidate.exists() and candidate.is_dir() else None
    for run_dir in _iter_run_dirs(paper_dir):
        if (run_dir / "claimset.resolved.json").exists() or (run_dir / "claimset.json").exists():
            return run_dir
    return None


def _load_claimset(run_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    resolved = run_dir / "claimset.resolved.json"
    legacy = run_dir / "claimset.json"
    if resolved.exists():
        return resolved, _safe_load_json(resolved)
    if legacy.exists():
        return legacy, _safe_load_json(legacy)
    return None, None


def _coerce_evidence(raw: Any, statement: str) -> EvidenceSpan:
    payload: dict[str, Any] = raw if isinstance(raw, dict) else {}
    candidate = dict(payload)
    raw_text = str(candidate.get("raw_text") or candidate.get("quote") or statement or "").strip()
    if not raw_text:
        raw_text = "No explicit evidence text; claimset fallback generated."
    candidate["raw_text"] = raw_text
    candidate["quote"] = str(candidate.get("quote") or raw_text[:180]).strip()
    candidate["rationale"] = str(
        candidate.get("rationale") or "Generated from claimset because stats_report artifact was missing."
    ).strip()

    table_id = candidate.get("table_id")
    cell_id = candidate.get("cell_id")
    if bool(table_id) ^ bool(cell_id):
        candidate.pop("table_id", None)
        candidate.pop("cell_id", None)

    try:
        return EvidenceSpan.model_validate(candidate)
    except Exception:
        return EvidenceSpan(
            page=candidate.get("page") if isinstance(candidate.get("page"), int) else None,
            raw_text=raw_text,
            quote=raw_text[:180],
            rationale="Generated from claimset because stats_report artifact was missing.",
            section=str(candidate.get("section") or "unknown"),
            highlight_source="text_match",
        )


def _build_report(*, paper_id: str, run_id: str, claimset: dict[str, Any], max_checks: int) -> StatsReport:
    claims = claimset.get("claims") if isinstance(claimset.get("claims"), list) else []
    checks: list[StatCheckEntry] = []
    for idx, claim in enumerate(claims[: max(1, int(max_checks))], start=1):
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or f"CHK-{idx:03d}")
        statement = str(claim.get("statement") or "").strip() or f"Claim {idx}"
        raw_evidence = claim.get("evidence_spans")
        evidence_items = raw_evidence if isinstance(raw_evidence, list) and raw_evidence else [None]
        evidence = [_coerce_evidence(evidence_items[0], statement)]

        checks.append(
            StatCheckEntry(
                check_id=claim_id,
                hypothesis=statement[:320],
                test_type="consistency-check",
                method="claimset_fallback",
                reported_stat=None,
                reported_df_tuple=None,
                df_parse_status="unknown",
                reported_p=None,
                alpha_used=0.05,
                computed_p=None,
                decision_error=False,
                confidence_interval_consistency=None,
                code="# Auto-generated fallback. Run full verifier for executable statistical checks.",
                outputs="stats_report auto-generated from claimset fallback.",
                verdict=VerificationStatus.UNVERIFIABLE,
                notes="AUTO_GENERATED_FROM_CLAIMSET",
                evidence=evidence,
            )
        )

    doc_id = str(claimset.get("doc_id") or paper_id)
    return StatsReport(
        doc_id=doc_id,
        run_id=run_id,
        input_tables_used=[],
        checks=checks,
    )


def _write_bootstrap_meta(run_dir: Path) -> None:
    meta_path = run_dir / "bootstrap_meta.json"
    meta = _safe_load_json(meta_path) or {}
    meta["stats_report_written"] = True
    meta["artifact_stats_written"] = True
    meta.setdefault("artifact_claimset_written", True)
    meta.setdefault("verifier_status", "fallback_generated")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def seed_for_paper(
    *,
    artifacts_root: Path,
    paper_id: str,
    run_id: str | None = None,
    max_checks: int = 6,
    write_bootstrap_meta: bool = True,
    skip_existing: bool = True,
    dry_run: bool = False,
) -> StatsSeedResult:
    preferred_dir = preferred_artifact_paper_dir(paper_id, root=artifacts_root)
    paper_dirs = [preferred_dir]
    for candidate in artifact_paper_dir_candidates(paper_id, root=artifacts_root):
        if candidate not in paper_dirs:
            paper_dirs.append(candidate)

    selected_run: Path | None = None
    for paper_dir in paper_dirs:
        selected_run = _select_run_dir(paper_dir, run_id)
        if selected_run is not None:
            break
    if selected_run is None:
        return StatsSeedResult(paper_id=paper_id, run_id=None, status="skipped", reason="run_not_found")

    claimset_path, claimset = _load_claimset(selected_run)
    if claimset_path is None or claimset is None:
        return StatsSeedResult(paper_id=paper_id, run_id=selected_run.name, status="skipped", reason="claimset_missing")

    stats_path = selected_run / "stats_report.json"
    if skip_existing and stats_path.exists():
        return StatsSeedResult(paper_id=paper_id, run_id=selected_run.name, status="skipped", reason="stats_exists")

    report = _build_report(
        paper_id=paper_id,
        run_id=selected_run.name,
        claimset=claimset,
        max_checks=max_checks,
    )

    if not dry_run:
        stats_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        if write_bootstrap_meta:
            _write_bootstrap_meta(selected_run)

    return StatsSeedResult(
        paper_id=paper_id,
        run_id=selected_run.name,
        status="seeded" if not dry_run else "planned",
        checks=len(report.checks),
        reason=claimset_path.name,
    )


def seed_stats_reports_from_claimset(
    *,
    paper_ids: list[str],
    artifacts_root: Path,
    run_id: str | None = None,
    max_checks: int = 6,
    write_bootstrap_meta: bool = True,
    skip_existing: bool = True,
    dry_run: bool = False,
) -> list[StatsSeedResult]:
    return [
        seed_for_paper(
            artifacts_root=artifacts_root,
            paper_id=str(paper_id),
            run_id=run_id,
            max_checks=max_checks,
            write_bootstrap_meta=write_bootstrap_meta,
            skip_existing=skip_existing,
            dry_run=dry_run,
        )
        for paper_id in paper_ids
    ]
