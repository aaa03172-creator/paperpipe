from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.services.pr_scope_guard import is_doc_file, normalize_paths


_CROSS_PAPER_EXACT = {
    "backend/services/job_runner.py",
    "scripts/backfill_deepread_handoff_artifacts.py",
    "scripts/eval/audit_deepread_handoff.py",
    "scripts/eval/compare_deepread_handoff_audits.py",
    "scripts/eval/check_deepread_handoff_gate.py",
    "scripts/eval/recommend_deepread_handoff_gate_mode.py",
    "src/agents/reader_agent.py",
    "src/schemas/deepread_handoff.py",
    "src/services/deepread_handoff_artifacts.py",
    "src/services/deepread_handoff_gate_scope.py",
    "tests/test_backfill_deepread_handoff_artifacts.py",
    "tests/test_deepread_handoff_artifacts.py",
    "tests/test_deepread_handoff_audit.py",
    "tests/test_deepread_handoff_compare.py",
    "tests/test_deepread_handoff_gate.py",
    "tests/test_deepread_handoff_gate_scope.py",
    "tests/test_reader_runtime_metrics.py",
    "tests/test_worker_job_runner_chain.py",
}

_CROSS_PAPER_PREFIXES = (
    "goldset/manifests/deepread_handoff_multicase_",
    "baselines/deepread_handoff/deepread_handoff_multicase_",
    "snapshots/deepread_handoff_eval/deepread_handoff_multicase_",
    "snapshots/deepread_handoff_gate/",
)

_CONTINUITY_PREFIXES = (
    "goldset/manifests/deepread_handoff_coric_",
    "baselines/deepread_handoff/deepread_handoff_coric_",
    "snapshots/deepread_handoff_eval/deepread_handoff_coric_",
)


@dataclass(frozen=True)
class DeepreadHandoffGateScopeReport:
    mode: str
    reason: str
    relevant_files: list[str]
    continuity_files: list[str]
    cross_paper_files: list[str]
    ignored_doc_files: list[str]


def _is_cross_paper_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    if normalized in _CROSS_PAPER_EXACT:
        return True
    if any(normalized.startswith(prefix) for prefix in _CROSS_PAPER_PREFIXES):
        return True
    return "deepread_handoff" in normalized and not any(
        normalized.startswith(prefix) for prefix in _CONTINUITY_PREFIXES
    )


def _is_continuity_path(path: str) -> bool:
    normalized = path.strip().replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in _CONTINUITY_PREFIXES)


def classify_deepread_handoff_gate_scope(files: Sequence[str]) -> DeepreadHandoffGateScopeReport:
    normalized = normalize_paths(files)

    ignored_doc_files: list[str] = []
    continuity_files: list[str] = []
    cross_paper_files: list[str] = []

    for path in normalized:
        if is_doc_file(path):
            ignored_doc_files.append(path)
            continue
        if _is_cross_paper_path(path):
            cross_paper_files.append(path)
            continue
        if _is_continuity_path(path):
            continuity_files.append(path)

    if cross_paper_files:
        mode = "cross-paper"
        reason = "shared deep-read handoff owners or multicase artifacts changed"
    elif continuity_files:
        mode = "continuity"
        reason = "only coric continuity artifacts changed"
    else:
        mode = "not_applicable"
        reason = "no non-doc deep-read handoff files matched the current gate scope"

    relevant_files = sorted(set(continuity_files + cross_paper_files))
    return DeepreadHandoffGateScopeReport(
        mode=mode,
        reason=reason,
        relevant_files=relevant_files,
        continuity_files=sorted(set(continuity_files)),
        cross_paper_files=sorted(set(cross_paper_files)),
        ignored_doc_files=sorted(set(ignored_doc_files)),
    )
