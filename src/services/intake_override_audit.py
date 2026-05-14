from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import shlex
import sys
from typing import Any, Mapping, Sequence

from src.schemas.intake_override_audit import (
    IntakeOverrideAuditDetails,
    IntakeOverrideAuditDocument,
    IntakeOverrideAuditInput,
    IntakeOverrideAuditMetrics,
    IntakeOverrideAuditSummary,
    IntakeOverrideProducerMetrics,
)
from src.schemas.intake_override_log import IntakeOverrideLog
from src.services.fixture_visibility import classify_test_fixture_paper_record
from src.skills.storage import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INTAKE_OVERRIDE_AUDITS_ROOT = REPO_ROOT / "snapshots" / "intake_override_audits"
DEFAULT_INTAKE_OVERRIDE_THRESHOLD_REVIEW_ROOT = REPO_ROOT / "snapshots" / "intake_override_threshold_review"
INTAKE_OVERRIDE_AUDIT_CALIBRATION_TARGET_RUNS = 3
_SYNTHETIC_RUN_NAME_PREFIXES: tuple[str, ...] = ("test", "smoke", "fixture", "pytest", "tmp", "temp")
THRESHOLD_REVIEW_PROVENANCE_KINDS: tuple[str, ...] = ("operator", "synthetic")
_CALIBRATION_RATE_FIELDS: tuple[tuple[str, str], ...] = (
    ("triage", "triage_override_rate"),
    ("slot", "slot_disagreement_rate"),
    ("slot_adjudication", "llm_slot_adjudication_rate"),
    ("tagging_adjudication", "llm_tagging_adjudication_rate"),
    ("fallback", "selection_fallback_rate"),
    ("analysis", "analysis_unavailable_rate"),
    ("issues", "issues_state_unavailable_rate"),
)
_ADJUDICATION_WARN_RATE = 0.25


def default_intake_override_audits_root(*, repo_root: Path | None = None) -> Path:
    base = (repo_root or REPO_ROOT).expanduser().resolve(strict=False)
    return (base / "snapshots" / "intake_override_audits").resolve(strict=False)


def default_intake_override_threshold_review_root(*, repo_root: Path | None = None) -> Path:
    base = (repo_root or REPO_ROOT).expanduser().resolve(strict=False)
    return (base / "snapshots" / "intake_override_threshold_review").resolve(strict=False)


def _looks_like_synthetic_run_name(name: str) -> bool:
    parts = [part for part in name.lower().replace("-", "_").split("_") if part]
    return any(
        part in _SYNTHETIC_RUN_NAME_PREFIXES
        or any(part.startswith(prefix) for prefix in _SYNTHETIC_RUN_NAME_PREFIXES)
        for part in parts
    )


def normalize_threshold_review_provenance_kind(value: object) -> str:
    kind = str(value or "operator").strip().lower()
    if kind not in THRESHOLD_REVIEW_PROVENANCE_KINDS:
        allowed = ", ".join(THRESHOLD_REVIEW_PROVENANCE_KINDS)
        raise ValueError(f"unsupported threshold review provenance kind: {kind!r} (expected one of: {allowed})")
    return kind


def threshold_review_summary_provenance_kind(summary: Mapping[str, Any] | None) -> str | None:
    if not isinstance(summary, Mapping):
        return None
    raw_provenance = summary.get("provenance")
    if not isinstance(raw_provenance, Mapping):
        return None
    raw_kind = raw_provenance.get("kind")
    if raw_kind in (None, ""):
        return None
    try:
        return normalize_threshold_review_provenance_kind(raw_kind)
    except ValueError:
        return None


def threshold_review_summary_latest_eligible(summary: Mapping[str, Any] | None) -> bool | None:
    if not isinstance(summary, Mapping):
        return None
    raw_provenance = summary.get("provenance")
    if not isinstance(raw_provenance, Mapping):
        return None
    raw_latest_eligible = raw_provenance.get("latest_eligible")
    if isinstance(raw_latest_eligible, bool):
        return raw_latest_eligible
    return None


def _latest_run_with_summary(
    root: Path,
    *,
    include_synthetic: bool = True,
) -> Path | None:
    if not root.exists() or not root.is_dir():
        return None

    candidates: list[tuple[float, str, Path]] = []
    for candidate in root.iterdir():
        if not candidate.is_dir():
            continue
        if not include_synthetic and _looks_like_synthetic_run_name(candidate.name):
            continue
        summary_path = candidate / "summary.json"
        if not summary_path.exists():
            continue
        try:
            mtime = summary_path.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, candidate.name, candidate))

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def latest_intake_override_audit_run(root: Path | None = None) -> Path | None:
    audit_root = (root or DEFAULT_INTAKE_OVERRIDE_AUDITS_ROOT).expanduser().resolve(strict=False)
    return _latest_run_with_summary(audit_root)


def latest_intake_override_threshold_review_run(
    root: Path | None = None,
    *,
    include_synthetic: bool = False,
) -> Path | None:
    review_root = (root or DEFAULT_INTAKE_OVERRIDE_THRESHOLD_REVIEW_ROOT).expanduser().resolve(strict=False)
    if include_synthetic:
        return _latest_run_with_summary(review_root, include_synthetic=True)

    if not review_root.exists() or not review_root.is_dir():
        return None

    candidates: list[tuple[float, str, Path]] = []
    for candidate in review_root.iterdir():
        if not candidate.is_dir():
            continue
        summary_path = candidate / "summary.json"
        if not summary_path.exists():
            continue
        try:
            summary_payload = load_intake_override_threshold_review_summary(summary_path)
        except Exception:
            summary_payload = None
        latest_eligible = threshold_review_summary_latest_eligible(summary_payload)
        if latest_eligible is False:
            continue
        if latest_eligible is True:
            provenance_kind = "operator"
        else:
            provenance_kind = threshold_review_summary_provenance_kind(summary_payload)
        if provenance_kind == "synthetic":
            continue
        if _looks_like_synthetic_run_name(candidate.name) and latest_eligible is not True:
            continue
        try:
            mtime = summary_path.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, candidate.name, candidate))

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def load_intake_override_threshold_review_summary(path_or_dir: Path) -> dict[str, Any]:
    candidate = path_or_dir.expanduser().resolve(strict=False)
    summary_path = candidate / "summary.json" if candidate.is_dir() else candidate
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("threshold review summary must be a JSON object")
    return payload


def latest_intake_override_threshold_review_summary(root: Path | None = None) -> dict[str, Any] | None:
    latest_run = latest_intake_override_threshold_review_run(root)
    if latest_run is None:
        return None
    return load_intake_override_threshold_review_summary(latest_run)


def load_intake_override_audit_summary(path_or_dir: Path) -> IntakeOverrideAuditSummary:
    candidate = path_or_dir.expanduser().resolve(strict=False)
    summary_path = candidate / "summary.json" if candidate.is_dir() else candidate
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return IntakeOverrideAuditSummary.model_validate(payload)


def latest_intake_override_audit_summary(root: Path | None = None) -> IntakeOverrideAuditSummary | None:
    latest_run = latest_intake_override_audit_run(root)
    if latest_run is None:
        return None
    return load_intake_override_audit_summary(latest_run)


def list_intake_override_audit_summaries(root: Path | None = None) -> list[IntakeOverrideAuditSummary]:
    audit_root = (root or DEFAULT_INTAKE_OVERRIDE_AUDITS_ROOT).expanduser().resolve(strict=False)
    if not audit_root.exists() or not audit_root.is_dir():
        return []

    summaries: list[IntakeOverrideAuditSummary] = []
    for candidate in audit_root.iterdir():
        if not candidate.is_dir():
            continue
        summary_path = candidate / "summary.json"
        if not summary_path.exists():
            continue
        try:
            summaries.append(load_intake_override_audit_summary(summary_path))
        except Exception:
            continue

    summaries.sort(key=lambda summary: (summary.generated_at, summary.run_id), reverse=True)
    return summaries


def build_intake_override_audit_calibration_snapshot(
    *,
    root: Path | None = None,
    warn_threshold: float,
    min_audited_docs: int,
    calibration_target_runs: int = INTAKE_OVERRIDE_AUDIT_CALIBRATION_TARGET_RUNS,
) -> dict[str, Any]:
    audit_root = (root or DEFAULT_INTAKE_OVERRIDE_AUDITS_ROOT).expanduser().resolve(strict=False)
    summaries = list_intake_override_audit_summaries(audit_root)
    runs: list[dict[str, Any]] = []
    signal_warn_counts: Counter[str] = Counter()
    signal_max_rates = {signal: 0.0 for signal, _ in _CALIBRATION_RATE_FIELDS}
    signal_latest_rates: dict[str, float] = {}
    eligible_runs = 0
    warn_runs = 0

    for summary in summaries:
        metrics = summary.metrics
        audited_docs = int(metrics.audited_document_count or 0)
        rates = {
            signal: float(getattr(metrics, field_name, 0.0) or 0.0)
            for signal, field_name in _CALIBRATION_RATE_FIELDS
        }
        sample_sufficient = audited_docs >= min_audited_docs
        warn_signals = [
            signal
            for signal, rate in rates.items()
            if sample_sufficient and rate >= warn_threshold
        ]
        status = "small_sample"
        if sample_sufficient:
            eligible_runs += 1
            signal_warn_counts.update(warn_signals)
            for signal, rate in rates.items():
                signal_max_rates[signal] = max(signal_max_rates[signal], rate)
            if warn_signals:
                warn_runs += 1
                status = "warn"
            else:
                status = "ok"

        for signal, rate in rates.items():
            signal_latest_rates.setdefault(signal, rate)

        runs.append(
            {
                "run_id": summary.run_id,
                "generated_at": summary.generated_at.isoformat(),
                "source": summary.inputs.source,
                "row_count": summary.inputs.row_count,
                "audited_document_count": audited_docs,
                "sample_sufficient": sample_sufficient,
                "status": status,
                "rates": rates,
                "warn_signals": warn_signals,
            }
        )

    signal_summary = [
        {
            "signal": signal,
            "latest_rate": signal_latest_rates.get(signal, 0.0),
            "max_rate": signal_max_rates.get(signal, 0.0),
            "warn_run_count": int(signal_warn_counts.get(signal, 0)),
            "warn_run_rate": _rate(int(signal_warn_counts.get(signal, 0)), eligible_runs),
        }
        for signal, _ in _CALIBRATION_RATE_FIELDS
    ]

    recommendations: list[str] = []
    if not runs:
        recommendations.append(
            "No intake override audit runs were found yet; generate a fresh audit before calibrating warning heuristics."
        )
    else:
        if eligible_runs < calibration_target_runs:
            recommendations.append(
                "Keep the current "
                f"{warn_threshold:.0%} warning threshold for now; only {eligible_runs} run(s) meet the "
                f"{min_audited_docs}-document sample floor, below the {calibration_target_runs}-run "
                "calibration floor."
            )
        else:
            recommendations.append(
                f"{eligible_runs} run(s) meet the {min_audited_docs}-document sample floor, "
                "so threshold calibration can start from this evidence."
            )

        persistent_signals = [
            item for item in signal_summary if item["warn_run_count"] > 0
        ]
        persistent_signals.sort(
            key=lambda item: (item["warn_run_count"], item["max_rate"], item["signal"]),
            reverse=True,
        )
        if persistent_signals:
            top_signals = ", ".join(
                f"{item['signal']} ({item['warn_run_count']}/{eligible_runs}, max {item['max_rate']:.1%})"
                for item in persistent_signals[:3]
            )
            recommendations.append(
                f"Most persistent sufficiently-audited signals: {top_signals}."
            )
        else:
            recommendations.append(
                "No sufficiently-audited run crosses the current warning threshold yet."
            )

        latest_run = runs[0]
        if latest_run["status"] == "warn":
            recommendations.append(
                f"Latest run {latest_run['run_id']} still crosses the warning threshold on "
                + ", ".join(latest_run["warn_signals"])
                + "."
            )
        elif latest_run["status"] == "small_sample":
            recommendations.append(
                f"Latest run {latest_run['run_id']} is below the sample floor "
                f"({latest_run['audited_document_count']} < {min_audited_docs}); gather more audited rows before "
                "treating it as calibration evidence."
            )
        else:
            recommendations.append(
                f"Latest run {latest_run['run_id']} stays below the current warning threshold."
            )

    return {
        "root": str(audit_root),
        "total_runs": len(runs),
        "eligible_runs": eligible_runs,
        "warn_runs": warn_runs,
        "warn_threshold": warn_threshold,
        "min_audited_docs": min_audited_docs,
        "calibration_target_runs": calibration_target_runs,
        "runs": runs,
        "signal_summary": signal_summary,
        "recommendations": recommendations,
    }


def load_audit_rows_from_db(db_path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM papers ORDER BY paper_id")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def load_audit_rows_from_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"rows_jsonl line must be a JSON object: {path}")
        rows.append(payload)
    return rows


def build_intake_override_audit(
    *,
    rows: Sequence[Mapping[str, Any]],
    run_id: str,
    source: str,
    db_path: Path | None = None,
    rows_jsonl_path: Path | None = None,
) -> tuple[IntakeOverrideAuditSummary, IntakeOverrideAuditDetails]:
    documents = [_build_audit_document(row) for row in rows]
    metrics = _build_metrics(documents)
    producer_metrics = _build_producer_metrics(documents)
    generated_at = datetime.now(timezone.utc)
    summary = IntakeOverrideAuditSummary(
        generated_at=generated_at,
        run_id=run_id,
        inputs=IntakeOverrideAuditInput(
            source=source,
            db_path=str(db_path) if db_path is not None else None,
            rows_jsonl_path=str(rows_jsonl_path) if rows_jsonl_path is not None else None,
            row_count=len(rows),
        ),
        metrics=metrics,
        producer_metrics=producer_metrics,
        documents_with_slot_disagreement=[
            doc.paper_id for doc in documents if doc.slot_changed is True and doc.has_intake_override_log
        ],
        documents_with_tag_disagreement=[
            doc.paper_id for doc in documents if doc.tags_changed is True and doc.has_intake_override_log
        ],
        documents_with_missing_log=[
            doc.paper_id for doc in documents if doc.parse_error in {"no_feedback_json", "missing_intake_override_log"}
        ],
        documents_with_missing_log_non_fixture=[
            doc.paper_id
            for doc in documents
            if doc.is_test_fixture is False and doc.parse_error in {"no_feedback_json", "missing_intake_override_log"}
        ],
        documents_with_invalid_log=[
            doc.paper_id
            for doc in documents
            if str(doc.parse_error or "").startswith("invalid_feedback_json")
            or str(doc.parse_error or "").startswith("invalid_intake_override_log")
        ],
        documents_with_selection_context=[
            doc.paper_id for doc in documents if doc.has_selection_context is True
        ],
        documents_with_selection_fallback=[
            doc.paper_id
            for doc in documents
            if doc.has_selection_context is True and doc.selection_skipped_processed_count > 0
        ],
    )
    details = IntakeOverrideAuditDetails(
        generated_at=generated_at,
        run_id=run_id,
        documents=documents,
    )
    return summary, details


def write_intake_override_audit(
    *,
    summary: IntakeOverrideAuditSummary,
    details: IntakeOverrideAuditDetails,
    out_dir: Path,
) -> Path:
    run_root = out_dir / summary.run_id
    atomic_write_text(run_root / "summary.json", summary.model_dump_json(indent=2))
    atomic_write_text(run_root / "details.json", details.model_dump_json(indent=2))
    atomic_write_text(
        run_root / "audit.md",
        render_intake_override_audit_markdown(summary=summary, details=details, run_root=run_root),
    )
    return run_root


def _build_repo_local_cli_viewer_command(
    run_root: Path,
    *,
    command_name: str,
    repo_root: Path | None = None,
    python_executable: Path | None = None,
) -> str:
    resolved_repo_root = (repo_root or REPO_ROOT).resolve()
    if os.name == "nt":
        venv_cli = resolved_repo_root / ".venv" / "Scripts" / "paperpipe.exe"
        venv_python = resolved_repo_root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_cli = resolved_repo_root / ".venv" / "bin" / "paperpipe"
        venv_python = resolved_repo_root / ".venv" / "bin" / "python"

    if venv_cli.exists():
        return (
            f"{shlex.quote(str(venv_cli))} "
            f"{command_name} {shlex.quote(str(run_root))}"
        )

    interpreter = venv_python if venv_python.exists() else Path(python_executable or sys.executable)
    return (
        f"PYTHONPATH={shlex.quote(str(resolved_repo_root))} "
        f"{shlex.quote(str(interpreter))} "
        f"-m src.cli {command_name} {shlex.quote(str(run_root))}"
    )


def build_intake_override_audit_viewer_command(
    run_root: Path,
    *,
    repo_root: Path | None = None,
    python_executable: Path | None = None,
) -> str:
    return _build_repo_local_cli_viewer_command(
        run_root,
        command_name="show-intake-override-audit",
        repo_root=repo_root,
        python_executable=python_executable,
    )


def build_intake_override_threshold_review_viewer_command(
    run_root: Path,
    *,
    repo_root: Path | None = None,
    python_executable: Path | None = None,
) -> str:
    return _build_repo_local_cli_viewer_command(
        run_root,
        command_name="show-intake-override-threshold-review",
        repo_root=repo_root,
        python_executable=python_executable,
    )


def render_intake_override_threshold_review_markdown(
    summary: Mapping[str, Any],
    *,
    run_root: Path | None = None,
) -> str:
    provenance = summary.get("provenance") if isinstance(summary.get("provenance"), Mapping) else {}
    inputs = summary.get("inputs") if isinstance(summary.get("inputs"), Mapping) else {}
    decision = summary.get("decision") if isinstance(summary.get("decision"), Mapping) else {}
    snapshot = summary.get("snapshot") if isinstance(summary.get("snapshot"), Mapping) else {}

    run_id = str(summary.get("run_id") or "unknown")
    generated_at = str(summary.get("generated_at") or "-")
    provenance_kind = str(provenance.get("kind") or "-")
    latest_eligible = provenance.get("latest_eligible")
    latest_eligible_text = "yes" if latest_eligible is True else "no" if latest_eligible is False else "-"
    audit_root = str(inputs.get("audit_root") or "-")
    warn_threshold = inputs.get("warn_threshold")
    min_audited_docs = inputs.get("min_audited_docs")
    calibration_target_runs = inputs.get("calibration_target_runs")

    lines = [
        f"# Intake Override Threshold Review: {run_id}",
        "",
        f"- Generated At: {generated_at}",
        f"- Provenance: {provenance_kind}",
        f"- Latest Eligible: {latest_eligible_text}",
        f"- Audit Root: {audit_root}",
    ]
    if warn_threshold not in (None, ""):
        lines.append(f"- Warn Threshold: {float(warn_threshold):.1%}")
    if min_audited_docs not in (None, ""):
        lines.append(f"- Minimum Audited Docs: {int(min_audited_docs)}")
    if calibration_target_runs not in (None, ""):
        lines.append(f"- Calibration Target Runs: {int(calibration_target_runs)}")
    lines.append("")

    if run_root is not None:
        viewer_command = build_intake_override_threshold_review_viewer_command(run_root)
        lines.extend(
            [
                "## Operator Flow",
                f"- Run Root: {run_root}",
                f"- Summary JSON: {run_root / 'summary.json'}",
                f"- Markdown: {run_root / 'audit.md'}",
                "",
                "```bash",
                viewer_command,
                "```",
                "",
            ]
        )

    recommended_action = str(decision.get("recommended_action") or "-")
    review_ready = "yes" if bool(decision.get("review_ready")) else "no"
    next_step = str(decision.get("next_step") or "-")
    latest_run_id = str(decision.get("latest_run_id") or "").strip()
    latest_run_status = str(decision.get("latest_run_status") or "").strip()
    latest_run_text = latest_run_id or "-"
    if latest_run_status:
        latest_run_text = f"{latest_run_text} ({latest_run_status})"
    lines.extend(
        [
            "## Decision",
            f"- Recommended Action: {recommended_action}",
            f"- Review Ready: {review_ready}",
            f"- Next Step: {next_step}",
            f"- Latest Run: {latest_run_text}",
        ]
    )

    focus_signals = [str(item).strip() for item in decision.get("focus_signals", []) if str(item).strip()]
    latest_warn_signals = [str(item).strip() for item in decision.get("latest_warn_signals", []) if str(item).strip()]
    tuning_targets = [str(item).strip() for item in decision.get("tuning_targets", []) if str(item).strip()]
    tuning_actions = [
        item for item in decision.get("tuning_actions", []) if isinstance(item, Mapping)
    ]
    action_plan = [
        item for item in decision.get("action_plan", []) if isinstance(item, Mapping)
    ]
    blocking_action = (
        decision.get("blocking_action")
        if isinstance(decision.get("blocking_action"), Mapping)
        else None
    )
    blocking_summary = str(decision.get("blocking_summary") or "").strip()
    tuning_recommendations = [
        str(item).strip() for item in decision.get("tuning_recommendations", []) if str(item).strip()
    ]
    decision_reason = str(decision.get("decision_reason") or "").strip()

    if focus_signals:
        lines.append(f"- Focus Signals: {', '.join(focus_signals)}")
    if latest_warn_signals:
        lines.append(f"- Latest Warn Signals: {', '.join(latest_warn_signals)}")
    if tuning_targets:
        lines.append(f"- Tuning Targets: {', '.join(tuning_targets)}")
    if decision_reason:
        lines.append(f"- Reason: {decision_reason}")
    if blocking_action is not None:
        blocking_order = int(blocking_action.get("order") or 0)
        blocking_name = str(blocking_action.get("action") or "").strip()
        blocking_target = str(blocking_action.get("target") or "").strip()
        blocking_signals = [
            str(signal).strip() for signal in blocking_action.get("signals", []) if str(signal).strip()
        ]
        blocking_evidence = str(blocking_action.get("evidence") or "").strip()
        blocking_text = f"{blocking_order}. `{blocking_name}`" if blocking_order > 0 else f"`{blocking_name}`"
        if blocking_target:
            blocking_text = f"{blocking_text} -> `{blocking_target}`"
        lines.append(f"- Blocking Action: {blocking_text}")
        if blocking_signals:
            lines.append(f"- Blocking Signals: {', '.join(blocking_signals)}")
        if blocking_evidence:
            lines.append(f"- Blocking Evidence: {blocking_evidence}")
    if blocking_summary:
        lines.append(f"- Blocking Summary: {blocking_summary}")
    lines.append("")

    if tuning_actions:
        lines.extend(["## Tuning Actions", ""])
        for item in tuning_actions:
            target = str(item.get("target") or "").strip()
            action = str(item.get("action") or "").strip()
            summary_text = str(item.get("summary") or "").strip()
            lines.append(f"- `{target}:{action}`")
            if summary_text:
                lines.append(f"  - {summary_text}")
        lines.append("")

    if action_plan:
        lines.extend(["## Action Plan", ""])
        for item in action_plan:
            order = int(item.get("order") or 0)
            action = str(item.get("action") or "").strip()
            target = str(item.get("target") or "").strip()
            signals = [str(signal).strip() for signal in item.get("signals", []) if str(signal).strip()]
            summary_text = str(item.get("summary") or "").strip()
            evidence_text = str(item.get("evidence") or "").strip()
            action_text = f"{order}. `{action}`"
            if target:
                action_text = f"{action_text} -> `{target}`"
            if bool(item.get("blocking")):
                action_text = f"{action_text} (blocking)"
            lines.append(action_text)
            if summary_text:
                lines.append(f"   - {summary_text}")
            if signals:
                lines.append(f"   - Signals: {', '.join(signals)}")
            if evidence_text:
                lines.append(f"   - Evidence: {evidence_text}")
        lines.append("")

    if tuning_recommendations:
        lines.extend(["## Tuning Recommendations", ""])
        for item in tuning_recommendations:
            lines.append(f"- {item}")
        lines.append("")

    total_runs = snapshot.get("total_runs")
    eligible_runs = snapshot.get("eligible_runs")
    warn_runs = snapshot.get("warn_runs")
    lines.extend(
        [
            "## Coverage",
            "",
            f"- Total Runs: {int(total_runs or 0)}",
            f"- Sufficient Runs: {int(eligible_runs or 0)}",
            f"- Warn Runs: {int(warn_runs or 0)}",
            "",
        ]
    )

    signal_summary = snapshot.get("signal_summary")
    if isinstance(signal_summary, list) and signal_summary:
        lines.extend(
            [
                "## Signal Summary",
                "",
                "| Signal | Latest Rate | Max Rate | Warn Runs |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for item in signal_summary:
            if not isinstance(item, Mapping):
                continue
            signal = str(item.get("signal") or "-")
            latest_rate = float(item.get("latest_rate") or 0.0)
            max_rate = float(item.get("max_rate") or 0.0)
            warn_run_count = int(item.get("warn_run_count") or 0)
            lines.append(
                f"| {signal} | {latest_rate:.1%} | {max_rate:.1%} | {warn_run_count} |"
            )
        lines.append("")

    recommendations = snapshot.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        lines.extend(["## Snapshot Recommendations", ""])
        for item in recommendations:
            text = str(item).strip()
            if text:
                lines.append(f"- {text}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_intake_override_audit_markdown(
    *,
    summary: IntakeOverrideAuditSummary,
    details: IntakeOverrideAuditDetails,
    run_root: Path | None = None,
) -> str:
    metrics = summary.metrics
    lines = [
        f"# Intake Override Audit: {summary.run_id}",
        "",
        f"- Generated At: {summary.generated_at.isoformat()}",
        f"- Source: {summary.inputs.source}",
        f"- Rows: {summary.inputs.row_count}",
        "",
    ]

    if run_root is not None:
        viewer_command = build_intake_override_audit_viewer_command(run_root)
        lines.extend(
            [
                "## Operator Flow",
                f"- Run Root: {run_root}",
                f"- Summary JSON: {run_root / 'summary.json'}",
                f"- Details JSON: {run_root / 'details.json'}",
                f"- Markdown: {run_root / 'audit.md'}",
                "",
                "```bash",
                viewer_command,
                "```",
                "",
            ]
        )

    adjudication_warnings: list[str] = []
    if metrics.llm_slot_classification_used_count > 0 and metrics.llm_slot_adjudication_rate >= _ADJUDICATION_WARN_RATE:
        adjudication_warnings.append(
            "Slot adjudication is firing frequently; review slot-classification ambiguity thresholds or evidence-bundle cues."
        )
    if metrics.llm_tagging_used_count > 0 and metrics.llm_tagging_adjudication_rate >= _ADJUDICATION_WARN_RATE:
        adjudication_warnings.append(
            "Tagging adjudication is firing frequently; review first-pass tagging robustness, soft-tag formatting, or evidence-span quality."
        )
    if adjudication_warnings:
        lines.extend(
            [
                "## Warnings",
                *[f"- {warning}" for warning in adjudication_warnings],
                "",
            ]
        )

    lines.extend(
        [
        "## Metrics",
        "| Metric | Count | Rate |",
        "| :--- | ---: | ---: |",
        f"| Audited documents | {metrics.audited_document_count} | - |",
        f"| Missing logs | {metrics.missing_intake_override_log_count} | - |",
        f"| Invalid feedback JSON | {metrics.invalid_feedback_json_count} | - |",
        f"| Invalid intake logs | {metrics.invalid_intake_override_log_count} | - |",
        f"| Slot disagreements | {metrics.slot_disagreement_count} | {_markdown_rate(metrics.slot_disagreement_rate)} |",
        f"| Tag disagreements | {metrics.tag_disagreement_count} | {_markdown_rate(metrics.tag_disagreement_rate)} |",
        f"| Slot adjudication used | {metrics.llm_slot_adjudication_used_count} | {_markdown_rate(metrics.llm_slot_adjudication_rate)} |",
        f"| Tagging adjudication used | {metrics.llm_tagging_adjudication_used_count} | {_markdown_rate(metrics.llm_tagging_adjudication_rate)} |",
        f"| Selection context | {metrics.selection_context_count} | {_markdown_rate(metrics.selection_context_rate)} |",
        f"| Selection fallback | {metrics.selection_fallback_count} | {_markdown_rate(metrics.selection_fallback_rate)} |",
        ]
    )

    documents_by_id = {doc.paper_id: doc for doc in details.documents}
    lines.extend(_markdown_bucket("Selection Fallback", summary.documents_with_selection_fallback, documents_by_id, selection_bucket=True))
    lines.extend(_markdown_bucket("Slot Disagreements", summary.documents_with_slot_disagreement, documents_by_id, slot_bucket=True))
    lines.extend(_markdown_bucket("Missing Logs", summary.documents_with_missing_log, documents_by_id))
    lines.extend(_markdown_bucket("Invalid Logs", summary.documents_with_invalid_log, documents_by_id))
    return "\n".join(lines) + "\n"


def _build_audit_document(row: Mapping[str, Any]) -> IntakeOverrideAuditDocument:
    paper_id = _paper_id_from_row(row)
    title = _clean_text(row.get("title"))
    is_test_fixture, fixture_reason = classify_test_fixture_paper_record(row)
    feedback_json = row.get("feedback_json")
    if feedback_json in (None, ""):
        return IntakeOverrideAuditDocument(
            paper_id=paper_id,
            title=title,
            is_test_fixture=is_test_fixture,
            fixture_reason=fixture_reason,
            has_feedback_json=False,
            has_intake_override_log=False,
            parse_error="no_feedback_json",
        )

    try:
        payload = json.loads(str(feedback_json))
    except Exception:
        return IntakeOverrideAuditDocument(
            paper_id=paper_id,
            title=title,
            is_test_fixture=is_test_fixture,
            fixture_reason=fixture_reason,
            has_feedback_json=True,
            has_intake_override_log=False,
            parse_error="invalid_feedback_json",
        )

    if not isinstance(payload, dict):
        return IntakeOverrideAuditDocument(
            paper_id=paper_id,
            title=title,
            is_test_fixture=is_test_fixture,
            fixture_reason=fixture_reason,
            has_feedback_json=True,
            has_intake_override_log=False,
            parse_error="invalid_feedback_json_shape",
        )

    raw_log = payload.get("intake_override_log")
    if raw_log is None:
        return IntakeOverrideAuditDocument(
            paper_id=paper_id,
            title=title,
            is_test_fixture=is_test_fixture,
            fixture_reason=fixture_reason,
            has_feedback_json=True,
            has_intake_override_log=False,
            parse_error="missing_intake_override_log",
        )

    try:
        intake_log = IntakeOverrideLog.model_validate(raw_log)
    except Exception as exc:
        return IntakeOverrideAuditDocument(
            paper_id=paper_id,
            title=title,
            is_test_fixture=is_test_fixture,
            fixture_reason=fixture_reason,
            has_feedback_json=True,
            has_intake_override_log=False,
            parse_error=f"invalid_intake_override_log:{type(exc).__name__}",
        )

    triage_override = bool(intake_log.slot_changed or intake_log.tags_changed)
    selection = _parse_selection_context(payload)
    return IntakeOverrideAuditDocument(
        paper_id=paper_id,
        title=title,
        producer=intake_log.producer,
        is_test_fixture=is_test_fixture,
        fixture_reason=fixture_reason,
        has_feedback_json=True,
        has_intake_override_log=True,
        analysis_available=intake_log.analysis_available,
        llm_tagging_used=intake_log.llm_tagging_used,
        llm_slot_classification_used=intake_log.llm_slot_classification_used,
        llm_tagging_adjudication_used=intake_log.llm_tagging_adjudication_used,
        llm_tagging_adjudication_reason=intake_log.llm_tagging_adjudication_reason,
        llm_slot_adjudication_used=intake_log.llm_slot_adjudication_used,
        llm_slot_adjudication_reason=intake_log.llm_slot_adjudication_reason,
        triage_override=triage_override,
        input_slot=intake_log.input_slot,
        stored_slot=intake_log.stored_slot,
        slot_changed=intake_log.slot_changed,
        input_tags=list(intake_log.input_tags),
        stored_tags=list(intake_log.stored_tags),
        tags_changed=intake_log.tags_changed,
        processing_status=intake_log.processing_status,
        issues_state=intake_log.issues_state,
        confidence=intake_log.confidence,
        has_selection_context=selection["has_selection_context"],
        selection_method=selection["selection_method"],
        selection_selected_rank=selection["selection_selected_rank"],
        selection_candidate_count=selection["selection_candidate_count"],
        selection_score=selection["selection_score"],
        selection_skipped_processed_count=selection["selection_skipped_processed_count"],
    )


def _build_metrics(documents: Sequence[IntakeOverrideAuditDocument]) -> IntakeOverrideAuditMetrics:
    audited_docs = [doc for doc in documents if doc.has_intake_override_log]
    fixture_docs = [doc for doc in documents if doc.is_test_fixture]
    non_fixture_docs = [doc for doc in documents if not doc.is_test_fixture]
    slot_used_denominator = sum(1 for doc in audited_docs if doc.llm_slot_classification_used is True)
    tag_used_denominator = sum(1 for doc in audited_docs if doc.llm_tagging_used is True)
    slot_adjudication_count = sum(1 for doc in audited_docs if doc.llm_slot_adjudication_used is True)
    tagging_adjudication_count = sum(1 for doc in audited_docs if doc.llm_tagging_adjudication_used is True)
    producer_counts = Counter(doc.producer for doc in audited_docs if doc.producer)
    processing_status_counts = Counter(doc.processing_status for doc in audited_docs if doc.processing_status)
    triage_override_count = sum(1 for doc in audited_docs if doc.triage_override is True)
    slot_disagreement_count = sum(1 for doc in audited_docs if doc.slot_changed is True)
    tag_disagreement_count = sum(1 for doc in audited_docs if doc.tags_changed is True)
    analysis_unavailable_count = sum(1 for doc in audited_docs if doc.analysis_available is False)
    issues_state_unavailable_count = sum(1 for doc in audited_docs if doc.issues_state == "unavailable")
    selection_context_count = sum(1 for doc in audited_docs if doc.has_selection_context is True)
    selection_fallback_count = sum(
        1 for doc in audited_docs if doc.has_selection_context is True and doc.selection_skipped_processed_count > 0
    )
    return IntakeOverrideAuditMetrics(
        document_count=len(documents),
        test_fixture_document_count=len(fixture_docs),
        non_fixture_document_count=len(non_fixture_docs),
        audited_document_count=len(audited_docs),
        has_feedback_json_count=sum(1 for doc in documents if doc.has_feedback_json),
        no_feedback_json_count=sum(1 for doc in documents if doc.parse_error == "no_feedback_json"),
        test_fixture_no_feedback_json_count=sum(
            1 for doc in fixture_docs if doc.parse_error == "no_feedback_json"
        ),
        non_fixture_no_feedback_json_count=sum(
            1 for doc in non_fixture_docs if doc.parse_error == "no_feedback_json"
        ),
        missing_intake_override_log_count=sum(
            1 for doc in documents if doc.parse_error == "missing_intake_override_log"
        ),
        invalid_feedback_json_count=sum(
            1 for doc in documents if str(doc.parse_error or "").startswith("invalid_feedback_json")
        ),
        invalid_intake_override_log_count=sum(
            1 for doc in documents if str(doc.parse_error or "").startswith("invalid_intake_override_log")
        ),
        triage_override_count=triage_override_count,
        slot_disagreement_count=slot_disagreement_count,
        tag_disagreement_count=tag_disagreement_count,
        analysis_unavailable_count=analysis_unavailable_count,
        issues_state_unavailable_count=issues_state_unavailable_count,
        selection_context_count=selection_context_count,
        selection_fallback_count=selection_fallback_count,
        llm_slot_classification_used_count=slot_used_denominator,
        llm_tagging_used_count=tag_used_denominator,
        llm_slot_adjudication_used_count=slot_adjudication_count,
        llm_tagging_adjudication_used_count=tagging_adjudication_count,
        triage_override_rate=_rate(triage_override_count, len(audited_docs)),
        slot_disagreement_rate=_rate(slot_disagreement_count, slot_used_denominator),
        tag_disagreement_rate=_rate(tag_disagreement_count, tag_used_denominator),
        analysis_unavailable_rate=_rate(analysis_unavailable_count, len(audited_docs)),
        issues_state_unavailable_rate=_rate(issues_state_unavailable_count, len(audited_docs)),
        selection_context_rate=_rate(selection_context_count, len(audited_docs)),
        selection_fallback_rate=_rate(selection_fallback_count, selection_context_count),
        llm_slot_adjudication_rate=_rate(slot_adjudication_count, slot_used_denominator),
        llm_tagging_adjudication_rate=_rate(tagging_adjudication_count, tag_used_denominator),
        producer_counts=dict(sorted(producer_counts.items())),
        processing_status_counts=dict(sorted(processing_status_counts.items())),
    )


def _build_producer_metrics(
    documents: Sequence[IntakeOverrideAuditDocument],
) -> list[IntakeOverrideProducerMetrics]:
    producer_names = sorted({doc.producer for doc in documents if doc.producer})
    reports: list[IntakeOverrideProducerMetrics] = []
    for producer in producer_names:
        producer_docs = [doc for doc in documents if doc.producer == producer]
        reports.append(
            IntakeOverrideProducerMetrics(
                producer=producer,
                metrics=_build_metrics(producer_docs),
            )
        )
    return reports


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _paper_id_from_row(row: Mapping[str, Any]) -> str:
    for key in ("paper_id", "doi", "id", "title"):
        candidate = _clean_text(row.get(key))
        if candidate:
            return candidate
    return "unknown"


def _clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _parse_selection_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_selection = payload.get("selection")
    if not isinstance(raw_selection, dict):
        return {
            "has_selection_context": False,
            "selection_method": None,
            "selection_selected_rank": None,
            "selection_candidate_count": None,
            "selection_score": None,
            "selection_skipped_processed_count": 0,
        }

    skipped_processed = raw_selection.get("skipped_processed_candidates")
    skipped_processed_count = len(skipped_processed) if isinstance(skipped_processed, list) else 0
    return {
        "has_selection_context": True,
        "selection_method": _clean_text(raw_selection.get("method")),
        "selection_selected_rank": _coerce_optional_int(raw_selection.get("selected_rank")),
        "selection_candidate_count": _coerce_optional_int(raw_selection.get("candidate_count")),
        "selection_score": _coerce_optional_float(raw_selection.get("selected_manual_rank_score")),
        "selection_skipped_processed_count": skipped_processed_count,
    }


def _coerce_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _markdown_rate(value: float) -> str:
    return f"{value:.1%}"


def _markdown_bucket(
    title: str,
    paper_ids: Sequence[str],
    documents_by_id: Mapping[str, IntakeOverrideAuditDocument],
    *,
    selection_bucket: bool = False,
    slot_bucket: bool = False,
) -> list[str]:
    if not paper_ids:
        return []

    lines = ["", f"## {title}"]
    if selection_bucket:
        lines.extend(
            [
                "| Paper | Title | Selection |",
                "| :--- | :--- | :--- |",
            ]
        )
    elif slot_bucket:
        lines.extend(
            [
                "| Paper | Title | Slot |",
                "| :--- | :--- | :--- |",
            ]
        )
    else:
        lines.extend(
            [
                "| Paper | Title |",
                "| :--- | :--- |",
            ]
        )

    for paper_id in paper_ids:
        doc = documents_by_id.get(paper_id)
        title = doc.title if doc and doc.title else "-"
        if selection_bucket:
            lines.append(f"| {paper_id} | {title} | {_selection_markdown(doc)} |")
        elif slot_bucket:
            input_slot = doc.input_slot if doc and doc.input_slot else "-"
            stored_slot = doc.stored_slot if doc and doc.stored_slot else "-"
            lines.append(f"| {paper_id} | {title} | {input_slot} -> {stored_slot} |")
        else:
            lines.append(f"| {paper_id} | {title} |")
    return lines


def _selection_markdown(doc: IntakeOverrideAuditDocument | None) -> str:
    if doc is None:
        return "-"
    parts: list[str] = []
    if doc.selection_selected_rank is not None and doc.selection_candidate_count is not None:
        parts.append(f"r{doc.selection_selected_rank}/{doc.selection_candidate_count}")
    elif doc.selection_selected_rank is not None:
        parts.append(f"r{doc.selection_selected_rank}")
    if doc.selection_score is not None:
        parts.append(f"s={doc.selection_score:.2f}")
    if doc.selection_skipped_processed_count > 0:
        parts.append(f"skip={doc.selection_skipped_processed_count}")
    return ", ".join(parts) or "-"
