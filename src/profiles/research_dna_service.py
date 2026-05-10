from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import load_config
from src.fetch.pubmed import PubMedFetcher
from src.profiles.research_dna_schema import (
    ActorType,
    ApprovalAuditEntry,
    InterviewLogEntry,
    InterviewRound,
    PilotRunArtifacts,
    QueryVersion,
    ResearchDNA,
    ResearchDNANextScreeningCandidate,
    ResearchDNAResumeSnapshot,
    ResearchDNARunIndex,
    ResearchDNARunSummary,
    ResearchDNARerankArtifacts,
    RerankGateStatus,
    ResearchDNAScreeningGuidanceArtifact,
    ResearchDNAScreeningGuidanceFollowSummary,
    ResearchDNAScreeningGuidanceIndexArtifact,
    ResearchDNAScreeningGuidanceIndexEntry,
    ResearchDNAScreeningProgressReport,
    ResearchDNARerankGateReport,
    ResearchDNARerankReport,
    ResearchDNAScreeningRecommendation,
    ResearchDNAScreeningSession,
    ResearchDNAScreeningQueueArtifact,
    ScreeningQueueVariant,
    ResearchDNAUpdate,
    ResearchIntent,
    RunLogEntry,
    ScreeningDecision,
    ScreeningLogEntry,
)
from src.profiles.research_dna_store import (
    append_approval_audit,
    append_interview_log,
    append_run_log,
    append_screening_log,
    load_research_dna,
    research_dna_log_path,
    research_dna_profile_path,
    sanitize_research_dna_log_model,
    sanitize_research_dna_log_payload,
    save_research_dna,
)
from src.schemas import Paper
from src.services.runtime_paths import search_eval_root as default_search_eval_root
from src.skills.storage import atomic_write_text

_QUERY_TOKEN_BLACKLIST = {
    "and",
    "or",
    "not",
    "the",
    "for",
    "with",
    "without",
    "from",
    "into",
    "over",
    "under",
    "via",
    "using",
    "use",
    "title",
    "abstract",
    "ti",
    "tiab",
    "ab",
    "mesh",
    "mh",
    "majr",
    "tw",
    "text",
    "word",
    "words",
    "all",
    "term",
    "terms",
    "pubmed",
}


class ResearchDNAStateError(ValueError):
    pass


_RECOMMENDATION_REASON_SUMMARIES = {
    "screening_in_progress": "Keep the original queue because screening is already in progress.",
    "reranked_unavailable": "Keep the original queue because the reranked queue is unavailable.",
    "rerank_warnings_present": "Keep the original queue because rerank warnings are present.",
    "rerank_report_unavailable": "Keep the original queue because the rerank report is unavailable.",
    "no_position_change": "Keep the original queue because reranking did not change candidate positions.",
    "non_positive_rerank_scores": "Keep the original queue because rerank scores are not positive.",
    "reranked_top_candidate_missing": "Keep the original queue because the reranked top candidate is missing.",
    "top_candidate_stable": "Keep the original queue because reranking did not change the top candidate.",
}


def _primary_text_value(values: list[str]) -> str | None:
    return values[0] if values else None


def _build_recommendation_summary(
    recommended_variant: ScreeningQueueVariant,
    *,
    primary_reason_code: str | None,
) -> str:
    if recommended_variant == "reranked":
        return "Consider the reranked queue because the top candidate changed with positive rerank signal."
    if primary_reason_code is None:
        return "Keep the original queue until stronger rerank signal is available."
    return _RECOMMENDATION_REASON_SUMMARIES.get(
        primary_reason_code,
        "Keep the original queue until stronger rerank signal is available.",
    )


def _build_gate_summary(
    gate_status: str,
    *,
    primary_reason_code: str | None,
    primary_warning_code: str | None,
) -> str:
    if gate_status == "eligible":
        return "Reranked queue is eligible for advisory operator use."
    if gate_status == "not_eligible":
        if primary_reason_code == "screening_in_progress":
            return "Reranked queue is not eligible because screening is already in progress."
        if primary_warning_code is not None:
            return "Reranked queue is not eligible because rerank warnings are present."
        return "Reranked queue is not eligible under the current screening state."
    if primary_reason_code == "no_position_change":
        return "Reranked queue is not yet eligible because reranking did not change candidate positions."
    if primary_reason_code == "top_candidate_stable":
        return "Reranked queue is not yet eligible because the top candidate did not change."
    return "Reranked queue is not yet eligible because the current signal is insufficient."


def log_interview_response(
    dna_id: str,
    *,
    round: InterviewRound,
    question_id: str,
    question: str,
    answer: str,
    actor_type: ActorType,
    actor_id: str,
    root: Path | None = None,
) -> tuple[ResearchDNA, InterviewLogEntry]:
    dna = load_research_dna(dna_id, root)
    if dna.status == "LOCKED":
        raise ResearchDNAStateError("log_interview_response is not allowed while status is LOCKED")

    entry = InterviewLogEntry(
        ts=_now_utc(),
        dna_id=dna_id,
        round=round,
        question_id=question_id,
        question=question,
        answer=answer,
        actor_type=actor_type,
        actor_id=actor_id,
    )
    entry = sanitize_research_dna_log_model(entry)
    append_interview_log(dna_id, entry, root)
    return dna, entry


def create_research_dna(
    *,
    topic: str,
    intent: ResearchIntent,
    actor_type: ActorType,
    actor_id: str,
    reason: str,
    root: Path | None = None,
    dna_id: str | None = None,
    title: str | None = None,
    recommended_databases: list[str] | None = None,
    available_databases: list[str] | None = None,
) -> ResearchDNA:
    now = _now_utc()
    effective_dna_id = dna_id or _slugify_topic(topic)
    if research_dna_profile_path(effective_dna_id, root).exists():
        raise ResearchDNAStateError("create_research_dna requires a new dna_id; profile already exists")
    created = ResearchDNA(
        id=effective_dna_id,
        title=title or topic.strip(),
        intent=intent,
        recommended_databases=list(recommended_databases or []),
        available_databases=list(available_databases or []),
    )
    save_research_dna(created, root)
    append_approval_audit(
        created.id,
        ApprovalAuditEntry(
            ts=now,
            dna_id=created.id,
            action="create",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
        ),
        root,
    )
    return created


def approve_pilot(
    dna_id: str,
    *,
    actor_type: ActorType,
    actor_id: str,
    reason: str,
    root: Path | None = None,
) -> ResearchDNA:
    dna = load_research_dna(dna_id, root)
    if dna.status != "DRAFT":
        raise ResearchDNAStateError(f"approve_pilot requires DRAFT state, got {dna.status}")

    now = _now_utc()
    dna.status = "PILOT"
    dna.governance.approved_for_pilot_at = now
    dna.governance.approved_for_pilot_by = f"{actor_type}:{actor_id}"
    save_research_dna(dna, root, expected_revision=dna.revision)
    append_approval_audit(
        dna_id,
        ApprovalAuditEntry(
            ts=now,
            dna_id=dna_id,
            action="approve_pilot",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            after_version=dna.query_versions[-1].version if dna.query_versions else None,
        ),
        root,
    )
    return dna


def update_research_dna(
    dna_id: str,
    *,
    patch: ResearchDNAUpdate,
    actor_type: ActorType,
    actor_id: str,
    reason: str,
    root: Path | None = None,
) -> ResearchDNA:
    dna = load_research_dna(dna_id, root)
    if dna.status == "LOCKED":
        raise ResearchDNAStateError("update_research_dna is not allowed while status is LOCKED")

    previous_goldset_kind = dna.pilot.goldset_kind
    changed = False
    if patch.title is not None:
        dna.title = patch.title
        changed = True
    if patch.intent is not None:
        dna.intent = patch.intent
        changed = True
    if patch.scope is not None:
        dna.scope = patch.scope
        changed = True
    if patch.criteria is not None:
        dna.criteria = patch.criteria
        changed = True
    if patch.recommended_databases is not None:
        dna.recommended_databases = list(patch.recommended_databases)
        changed = True
    if patch.available_databases is not None:
        dna.available_databases = list(patch.available_databases)
        changed = True
    if patch.filters is not None:
        dna.filters = patch.filters
        changed = True
    if patch.pilot is not None:
        dna.pilot = patch.pilot
        changed = True
    if patch.change_policy is not None:
        dna.governance.change_policy = patch.change_policy
        changed = True

    if not changed:
        raise ResearchDNAStateError("update_research_dna requires at least one changed field")

    save_research_dna(dna, root, expected_revision=dna.revision)
    audit_action = "update"
    if patch.pilot is not None and patch.pilot.goldset_kind != previous_goldset_kind:
        audit_action = "change_goldset_kind"
    append_approval_audit(
        dna_id,
        ApprovalAuditEntry(
            ts=_now_utc(),
            dna_id=dna_id,
            action=audit_action,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            after_version=dna.query_versions[-1].version if dna.query_versions else None,
        ),
        root,
    )
    return dna


def submit_screening_decision(
    dna_id: str,
    *,
    run_id: str,
    candidate_id: str,
    decision: ScreeningDecision,
    reason_code: str,
    variant: ScreeningQueueVariant = "original",
    owner_variant: ScreeningQueueVariant = "original",
    recommended_variant: ScreeningQueueVariant | None = None,
    guidance_gate_status: RerankGateStatus | None = None,
    guidance_primary_reason_code: str | None = None,
    followed_guidance: bool | None = None,
    actor_type: ActorType,
    actor_id: str,
    note: str | None = None,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNA:
    dna = load_research_dna(dna_id, root)
    if dna.status != "PILOT":
        raise ResearchDNAStateError(f"submit_screening_decision requires PILOT state, got {dna.status}")

    append_screening_log(
        dna_id,
        ScreeningLogEntry(
            ts=_now_utc(),
            dna_id=dna_id,
            run_id=run_id,
            candidate_id=candidate_id,
            variant=variant,
            owner_variant=owner_variant,
            recommended_variant=recommended_variant,
            guidance_gate_status=guidance_gate_status,
            guidance_primary_reason_code=guidance_primary_reason_code,
            followed_guidance=followed_guidance,
            decision=decision,
            reason_code=reason_code,
            note=note,
            actor_type=actor_type,
            actor_id=actor_id,
        ),
        root,
    )
    append_approval_audit(
        dna_id,
        ApprovalAuditEntry(
            ts=_now_utc(),
            dna_id=dna_id,
            action="submit_screening",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=f"{decision}:{reason_code}",
            run_id=run_id,
        ),
        root,
    )
    _best_effort_refresh_run_screening_progress_sidecars(
        dna_id,
        run_id=run_id,
        variant=variant,
        root=root,
        search_eval_root=search_eval_root,
    )
    return dna


def refine_query_version(
    dna_id: str,
    *,
    query_version: QueryVersion,
    actor_type: ActorType,
    actor_id: str,
    reason: str,
    root: Path | None = None,
) -> ResearchDNA:
    dna = load_research_dna(dna_id, root)
    if dna.status not in {"DRAFT", "PILOT"}:
        raise ResearchDNAStateError(f"refine_query_version requires DRAFT or PILOT state, got {dna.status}")
    if any(existing.version == query_version.version for existing in dna.query_versions):
        raise ResearchDNAStateError(f"Query version already exists: {query_version.version}")

    before_version = dna.query_versions[-1].version if dna.query_versions else None
    dna.query_versions.append(query_version)
    save_research_dna(dna, root, expected_revision=dna.revision)
    append_approval_audit(
        dna_id,
        ApprovalAuditEntry(
            ts=_now_utc(),
            dna_id=dna_id,
            action="refine",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            before_version=before_version,
            after_version=query_version.version,
        ),
        root,
    )
    return dna


def lock_research_dna(
    dna_id: str,
    *,
    actor_type: ActorType,
    actor_id: str,
    reason: str,
    root: Path | None = None,
) -> ResearchDNA:
    dna = load_research_dna(dna_id, root)
    if dna.status != "PILOT":
        raise ResearchDNAStateError(f"lock_research_dna requires PILOT state, got {dna.status}")

    now = _now_utc()
    dna.status = "LOCKED"
    dna.governance.locked_at = now
    dna.governance.locked_by = f"{actor_type}:{actor_id}"
    save_research_dna(dna, root, expected_revision=dna.revision)
    append_approval_audit(
        dna_id,
        ApprovalAuditEntry(
            ts=now,
            dna_id=dna_id,
            action="lock",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            after_version=dna.query_versions[-1].version if dna.query_versions else None,
        ),
        root,
    )
    return dna


def unlock_research_dna(
    dna_id: str,
    *,
    actor_type: ActorType,
    actor_id: str,
    reason: str,
    root: Path | None = None,
) -> ResearchDNA:
    dna = load_research_dna(dna_id, root)
    if dna.status != "LOCKED":
        raise ResearchDNAStateError(f"unlock_research_dna requires LOCKED state, got {dna.status}")

    dna.status = "PILOT"
    dna.governance.locked_at = None
    dna.governance.locked_by = None
    save_research_dna(dna, root, expected_revision=dna.revision)
    append_approval_audit(
        dna_id,
        ApprovalAuditEntry(
            ts=_now_utc(),
            dna_id=dna_id,
            action="unlock",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            after_version=dna.query_versions[-1].version if dna.query_versions else None,
        ),
        root,
    )
    return dna


def run_pilot(
    dna_id: str,
    *,
    actor_type: ActorType,
    actor_id: str,
    root: Path | None = None,
    search_eval_root: Path | None = None,
    run_id: str | None = None,
    source_fetchers: dict[str, object] | None = None,
) -> PilotRunArtifacts:
    dna = load_research_dna(dna_id, root)
    if dna.status != "PILOT":
        raise ResearchDNAStateError(f"run_pilot requires PILOT state, got {dna.status}")
    if not dna.query_versions:
        raise ResearchDNAStateError("run_pilot requires at least one query version")

    active_query = dna.query_versions[-1]
    supported_fetchers = source_fetchers or _default_source_fetchers()
    active_sources = [
        source
        for source in dna.available_databases
        if source in supported_fetchers and active_query.per_db.get(source)
    ]
    if not active_sources:
        raise ResearchDNAStateError("run_pilot requires at least one supported available database with a query")

    effective_run_id = run_id or f"pilot_{_now_utc().strftime('%Y%m%dT%H%M%S%f%z')}"
    eval_root = (search_eval_root or default_search_eval_root()).expanduser().resolve()
    run_dir = eval_root / effective_run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    queries_payload = {
        "dna_id": dna.id,
        "query_version": active_query.version,
        "queries": {source: active_query.per_db[source] for source in active_sources},
    }
    _write_json(run_dir / "queries.json", queries_payload)

    retrieved_rows: list[dict] = []
    source_statuses: list[dict] = []
    for source in active_sources:
        query = active_query.per_db[source]
        fetcher = supported_fetchers[source]
        try:
            papers = fetcher.fetch(query, dna.pilot.n)
            retrieved_rows.extend(
                _paper_to_row(
                    paper=paper,
                    dna_id=dna.id,
                    run_id=effective_run_id,
                    query_version=active_query.version,
                    source=source,
                )
                for paper in papers
            )
            source_statuses.append(
                {
                    "source": source,
                    "status": "ok",
                    "query": query,
                    "retrieved_count": len(papers),
                }
            )
        except Exception as exc:
            source_statuses.append(
                {
                    "source": source,
                    "status": "error",
                    "query": query,
                    "error": str(exc),
                }
            )

    retrieved_path = run_dir / "retrieved.jsonl"
    _write_jsonl(retrieved_path, retrieved_rows)

    deduped_rows = list(_dedupe_rows(retrieved_rows).values())
    screening_rows = deduped_rows[: dna.pilot.n]
    screening_path = run_dir / "screening_queue.jsonl"
    _write_jsonl(screening_path, screening_rows)

    dedupe_rate = 0.0
    if retrieved_rows:
        dedupe_rate = max(0.0, 1.0 - (len(deduped_rows) / len(retrieved_rows)))

    metrics = {
        "run_id": effective_run_id,
        "dna_id": dna.id,
        "query_version": active_query.version,
        "retrieved_count": len(retrieved_rows),
        "deduped_count": len(deduped_rows),
        "dedupe_rate": dedupe_rate,
        "labeled_count": 0,
        "include_count": 0,
        "exclude_count": 0,
        "unclear_count": 0,
        "precision_proxy": 0.0,
        "goldset_recall": None,
        "top_reason_codes": [],
    }
    metrics_path = run_dir / "metrics.json"
    _write_json(metrics_path, metrics)

    manifest = {
        "run_id": effective_run_id,
        "dna_id": dna.id,
        "status": "completed" if source_statuses and all(row["status"] == "ok" for row in source_statuses) else "partial",
        "actor_type": actor_type,
        "actor_id": actor_id,
        "query_version": active_query.version,
        "pilot_n": dna.pilot.n,
        "recommended_databases": dna.recommended_databases,
        "available_databases": dna.available_databases,
        "active_sources": active_sources,
        "source_statuses": source_statuses,
        "artifact_paths": {
            "queries": str(run_dir / "queries.json"),
            "retrieved": str(retrieved_path),
            "screening_queue": str(screening_path),
            "metrics": str(metrics_path),
        },
    }
    _write_json(run_dir / "manifest.json", manifest)

    append_run_log(
        dna.id,
        RunLogEntry(
            ts=_now_utc(),
            run_id=effective_run_id,
            dna_id=dna.id,
            query_version=active_query.version,
            status=manifest["status"],
            actor_type=actor_type,
            actor_id=actor_id,
            sources=active_sources,
            retrieved_count=len(retrieved_rows),
            deduped_count=len(deduped_rows),
            dedupe_rate=dedupe_rate,
            pilot_n=dna.pilot.n,
            labeled_count=0,
            include_count=0,
            exclude_count=0,
            unclear_count=0,
            precision_proxy=0.0,
            top_reason_codes=[],
        ),
        root,
    )

    return PilotRunArtifacts(
        run_id=effective_run_id,
        dna_id=dna.id,
        run_dir=str(run_dir),
        query_version=active_query.version,
        sources=active_sources,
        retrieved_count=len(retrieved_rows),
        deduped_count=len(deduped_rows),
        dedupe_rate=dedupe_rate,
        screening_queue_path=str(screening_path),
        metrics_path=str(metrics_path),
    )


def materialize_reranked_screening_queue(
    dna_id: str,
    *,
    run_id: str,
    actor_type: ActorType,
    actor_id: str,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNARerankArtifacts:
    load_research_dna(dna_id, root)

    eval_root = (search_eval_root or default_search_eval_root()).expanduser().resolve()
    run_dir = eval_root / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise ResearchDNAStateError(f"rerank requires manifest.json for run_id={run_id}")

    manifest = _read_json(manifest_path)
    if manifest.get("dna_id") != dna_id:
        raise ResearchDNAStateError(
            f"rerank run_id={run_id} belongs to dna_id={manifest.get('dna_id')}, not {dna_id}"
        )

    artifact_paths = manifest.get("artifact_paths") if isinstance(manifest.get("artifact_paths"), dict) else {}
    screening_path = Path(str(artifact_paths.get("screening_queue") or run_dir / "screening_queue.jsonl"))
    queries_path = Path(str(artifact_paths.get("queries") or run_dir / "queries.json"))
    metrics_path = Path(str(artifact_paths.get("metrics") or run_dir / "metrics.json"))

    if not screening_path.exists():
        raise ResearchDNAStateError(f"rerank requires screening queue artifact: {screening_path}")
    if not queries_path.exists():
        raise ResearchDNAStateError(f"rerank requires queries artifact: {queries_path}")

    screening_rows = _read_jsonl(screening_path)
    queries_payload = _read_json(queries_path)
    query_version = str(queries_payload.get("query_version") or manifest.get("query_version") or "")
    if not query_version:
        raise ResearchDNAStateError(f"rerank requires query_version in {queries_path}")

    queries_by_source_raw = queries_payload.get("queries")
    if not isinstance(queries_by_source_raw, dict):
        raise ResearchDNAStateError(f"rerank requires source queries in {queries_path}")
    queries_by_source = {str(key): str(value) for key, value in queries_by_source_raw.items()}

    reranked_rows, report = _build_reranked_screening_queue(
        dna_id=dna_id,
        run_id=run_id,
        query_version=query_version,
        actor_type=actor_type,
        actor_id=actor_id,
        screening_path=screening_path,
        screening_rows=screening_rows,
        queries_by_source=queries_by_source,
        active_sources=[str(source) for source in manifest.get("active_sources", []) if str(source).strip()],
    )

    reranked_path = run_dir / "reranked_screening_queue.jsonl"
    rerank_report_path = run_dir / "rerank_report.json"
    _write_jsonl(reranked_path, reranked_rows)
    _write_json(rerank_report_path, report.model_dump(mode="json", exclude_none=True))

    metrics = _read_json(metrics_path) if metrics_path.exists() else {}
    metrics["research_dna_rerank"] = {
        "algorithm_version": report.algorithm_version,
        "row_count": report.row_count,
        "changed_position_count": report.changed_position_count,
        "changed_position_ratio": report.changed_position_ratio,
        "top_candidate_id": report.top_candidate_id,
        "query_token_count": report.query_token_count,
        "query_phrase_count": report.query_phrase_count,
        "min_score": report.min_score,
        "max_score": report.max_score,
        "mean_score": report.mean_score,
        "top_score": report.top_score,
        "second_score": report.second_score,
        "top_score_margin": report.top_score_margin,
    }
    _write_json(metrics_path, metrics)

    artifact_paths["reranked_screening_queue"] = str(reranked_path)
    artifact_paths["rerank_report"] = str(rerank_report_path)
    manifest["artifact_paths"] = artifact_paths
    manifest["rerank"] = {
        "algorithm_version": report.algorithm_version,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "materialized_at": report.evaluated_at.isoformat(),
        "row_count": report.row_count,
        "changed_position_count": report.changed_position_count,
        "changed_position_ratio": report.changed_position_ratio,
        "top_candidate_id": report.top_candidate_id,
        "top_score_margin": report.top_score_margin,
    }
    _write_json(manifest_path, manifest)

    return ResearchDNARerankArtifacts(
        run_id=run_id,
        dna_id=dna_id,
        run_dir=str(run_dir),
        query_version=query_version,
        screening_queue_path=str(screening_path),
        reranked_screening_queue_path=str(reranked_path),
        rerank_report_path=str(rerank_report_path),
        metrics_path=str(metrics_path),
        row_count=report.row_count,
        changed_position_count=report.changed_position_count,
        top_candidate_id=report.top_candidate_id,
        algorithm_version=report.algorithm_version,
    )


def materialize_screening_guidance_artifact(
    dna_id: str,
    *,
    run_id: str,
    actor_type: ActorType,
    actor_id: str,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNAScreeningGuidanceArtifact:
    load_research_dna(dna_id, root)

    eval_root = (search_eval_root or default_search_eval_root()).expanduser().resolve()
    run_dir = eval_root / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise ResearchDNAStateError(f"guidance materialization requires manifest.json for run_id={run_id}")

    manifest = _read_json(manifest_path)
    if manifest.get("dna_id") != dna_id:
        raise ResearchDNAStateError(
            f"guidance run_id={run_id} belongs to dna_id={manifest.get('dna_id')}, not {dna_id}"
        )

    recommendation, gate = load_screening_operator_guidance(
        dna_id,
        run_id=run_id,
        root=root,
        search_eval_root=search_eval_root,
    )

    evaluated_at = _now_utc()
    timestamp_token = evaluated_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    artifact_path = run_dir / f"screening_guidance_{timestamp_token}.json"
    collision_index = 1
    while artifact_path.exists():
        artifact_path = run_dir / f"screening_guidance_{timestamp_token}_{collision_index}.json"
        collision_index += 1
    guidance_artifact = ResearchDNAScreeningGuidanceArtifact(
        evaluated_at=evaluated_at,
        run_id=run_id,
        dna_id=dna_id,
        query_version=recommendation.query_version,
        actor_type=actor_type,
        actor_id=actor_id,
        artifact_path=str(artifact_path),
        recommendation=recommendation,
        gate=gate,
    )
    _write_json(artifact_path, guidance_artifact.model_dump(mode="json", exclude_none=True))

    index_path = run_dir / "screening_guidance_index.json"
    existing_index_entries: list[ResearchDNAScreeningGuidanceIndexEntry] = []
    if index_path.exists():
        try:
            existing_index = ResearchDNAScreeningGuidanceIndexArtifact.model_validate(_read_json(index_path))
            if (
                existing_index.run_id != run_id
                or existing_index.dna_id != dna_id
                or existing_index.query_version != recommendation.query_version
            ):
                raise ResearchDNAStateError(
                    "guidance index does not match current run identity"
                )
            existing_index_entries = list(existing_index.entries)
        except Exception as exc:
            raise ResearchDNAStateError(f"guidance index is invalid for run_id={run_id}: {exc}")

    new_index_entry = ResearchDNAScreeningGuidanceIndexEntry(
        evaluated_at=evaluated_at,
        artifact_path=str(artifact_path),
        actor_type=actor_type,
        actor_id=actor_id,
        recommended_variant=recommendation.recommended_variant,
        gate_status=gate.gate_status,
        screening_started=recommendation.screening_started,
        primary_reason_code=recommendation.primary_reason_code,
        primary_warning_code=recommendation.primary_warning_code,
    )
    guidance_index = ResearchDNAScreeningGuidanceIndexArtifact(
        run_id=run_id,
        dna_id=dna_id,
        query_version=recommendation.query_version,
        artifact_path=str(index_path),
        entry_count=len(existing_index_entries) + 1,
        latest_artifact_path=str(artifact_path),
        entries=[*existing_index_entries, new_index_entry],
    )
    _write_json(index_path, guidance_index.model_dump(mode="json", exclude_none=True))

    artifact_paths = manifest.get("artifact_paths") if isinstance(manifest.get("artifact_paths"), dict) else {}
    artifact_paths["screening_guidance"] = str(artifact_path)
    artifact_paths["screening_guidance_index"] = str(index_path)
    manifest["artifact_paths"] = artifact_paths
    manifest["screening_guidance"] = {
        "materialized_at": evaluated_at.isoformat(),
        "actor_type": actor_type,
        "actor_id": actor_id,
        "artifact_path": str(artifact_path),
        "index_path": str(index_path),
        "history_count": guidance_index.entry_count,
        "recommended_variant": recommendation.recommended_variant,
        "gate_status": gate.gate_status,
        "screening_started": recommendation.screening_started,
    }
    _write_json(manifest_path, manifest)

    metrics_path = Path(str(artifact_paths.get("metrics") or run_dir / "metrics.json"))
    metrics = _read_json(metrics_path) if metrics_path.exists() else {}
    metrics["research_dna_guidance"] = {
        "materialized_at": evaluated_at.isoformat(),
        "artifact_path": str(artifact_path),
        "index_path": str(index_path),
        "history_count": guidance_index.entry_count,
        "recommended_variant": recommendation.recommended_variant,
        "gate_status": gate.gate_status,
        "screening_started": recommendation.screening_started,
        "changed_position_ratio": recommendation.changed_position_ratio,
        "top_score_margin": recommendation.rerank_top_score_margin,
        "primary_reason_code": recommendation.primary_reason_code,
        "primary_warning_code": recommendation.primary_warning_code,
    }
    _write_json(metrics_path, metrics)

    return guidance_artifact


def load_screening_guidance_index_artifact(
    dna_id: str,
    *,
    run_id: str,
    limit: int = 20,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNAScreeningGuidanceIndexArtifact:
    load_research_dna(dna_id, root)
    if limit < 1:
        raise ResearchDNAStateError("guidance history limit must be >= 1")

    eval_root = (search_eval_root or default_search_eval_root()).expanduser().resolve()
    run_dir = eval_root / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise ResearchDNAStateError(f"guidance history requires manifest.json for run_id={run_id}")

    manifest = _read_json(manifest_path)
    if manifest.get("dna_id") != dna_id:
        raise ResearchDNAStateError(
            f"guidance history run_id={run_id} belongs to dna_id={manifest.get('dna_id')}, not {dna_id}"
        )

    artifact_paths = manifest.get("artifact_paths") if isinstance(manifest.get("artifact_paths"), dict) else {}
    queries_path = Path(str(artifact_paths.get("queries") or run_dir / "queries.json"))
    query_version = str(manifest.get("query_version") or "")
    if queries_path.exists():
        queries_payload = _read_json(queries_path)
        query_version = str(queries_payload.get("query_version") or query_version)
    if not query_version:
        raise ResearchDNAStateError(f"guidance history requires query_version for run_id={run_id}")

    index_path = Path(str(artifact_paths.get("screening_guidance_index") or run_dir / "screening_guidance_index.json"))
    if not index_path.exists():
        raise ResearchDNAStateError(f"guidance history artifact is unavailable for run_id={run_id}")

    try:
        guidance_index = ResearchDNAScreeningGuidanceIndexArtifact.model_validate(_read_json(index_path))
    except Exception as exc:
        raise ResearchDNAStateError(f"guidance history is invalid for run_id={run_id}: {exc}")

    if (
        guidance_index.run_id != run_id
        or guidance_index.dna_id != dna_id
        or guidance_index.query_version != query_version
    ):
        raise ResearchDNAStateError("guidance history does not match current run identity")

    entries = list(guidance_index.entries)
    if len(entries) > limit:
        entries = entries[-limit:]

    return ResearchDNAScreeningGuidanceIndexArtifact(
        run_id=guidance_index.run_id,
        dna_id=guidance_index.dna_id,
        query_version=guidance_index.query_version,
        artifact_path=guidance_index.artifact_path,
        entry_count=guidance_index.entry_count,
        latest_artifact_path=guidance_index.latest_artifact_path,
        entries=entries,
    )


def load_latest_screening_guidance_artifact(
    dna_id: str,
    *,
    run_id: str,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNAScreeningGuidanceArtifact:
    load_research_dna(dna_id, root)

    eval_root = (search_eval_root or default_search_eval_root()).expanduser().resolve()
    run_dir = eval_root / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise ResearchDNAStateError(f"screening guidance artifact requires manifest.json for run_id={run_id}")

    manifest = _read_json(manifest_path)
    if manifest.get("dna_id") != dna_id:
        raise ResearchDNAStateError(
            f"screening guidance artifact run_id={run_id} belongs to dna_id={manifest.get('dna_id')}, not {dna_id}"
        )

    artifact_paths = manifest.get("artifact_paths") if isinstance(manifest.get("artifact_paths"), dict) else {}
    queries_path = Path(str(artifact_paths.get("queries") or run_dir / "queries.json"))
    query_version = str(manifest.get("query_version") or "")
    if queries_path.exists():
        queries_payload = _read_json(queries_path)
        query_version = str(queries_payload.get("query_version") or query_version)
    if not query_version:
        raise ResearchDNAStateError(f"screening guidance artifact requires query_version for run_id={run_id}")

    guidance_meta = manifest.get("screening_guidance") if isinstance(manifest.get("screening_guidance"), dict) else {}
    artifact_path_value = artifact_paths.get("screening_guidance") or guidance_meta.get("artifact_path")
    artifact_path_text = str(artifact_path_value or "").strip()
    if not artifact_path_text:
        raise ResearchDNAStateError(f"screening guidance artifact is unavailable for run_id={run_id}")

    artifact_path = Path(artifact_path_text)
    if not artifact_path.exists():
        raise ResearchDNAStateError(f"screening guidance artifact missing for run_id={run_id}: {artifact_path}")

    try:
        guidance_artifact = ResearchDNAScreeningGuidanceArtifact.model_validate(_read_json(artifact_path))
    except Exception as exc:
        raise ResearchDNAStateError(f"screening guidance artifact is invalid for run_id={run_id}: {exc}")

    if (
        guidance_artifact.run_id != run_id
        or guidance_artifact.dna_id != dna_id
        or guidance_artifact.query_version != query_version
    ):
        raise ResearchDNAStateError("screening guidance artifact does not match current run identity")

    loaded_artifact_path = str(Path(guidance_artifact.artifact_path))
    if loaded_artifact_path != str(artifact_path):
        raise ResearchDNAStateError("screening guidance artifact path does not match the current manifest pointer")

    return guidance_artifact


def load_research_dna_run_index(
    dna_id: str,
    *,
    limit: int = 20,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNARunIndex:
    if limit < 1:
        raise ResearchDNAStateError("limit must be >= 1")

    load_research_dna(dna_id, root)
    run_log_path = research_dna_log_path(dna_id, "runs", root)
    run_rows = _read_jsonl(run_log_path) if run_log_path.exists() else []
    run_entries = sorted(
        (
            RunLogEntry.model_validate(sanitize_research_dna_log_payload(row))
            for row in run_rows
            if str(row.get("dna_id") or "").strip() == dna_id
        ),
        key=lambda row: row.ts,
        reverse=True,
    )

    return ResearchDNARunIndex(
        dna_id=dna_id,
        run_count=len(run_entries),
        latest_run_id=run_entries[0].run_id if run_entries else None,
        runs=[
            _build_run_summary_from_entry(
                entry,
                root=root,
                search_eval_root=search_eval_root,
            )
            for entry in run_entries[:limit]
        ],
    )


def load_research_dna_resume_snapshot(
    dna_id: str,
    *,
    variant: ScreeningQueueVariant = "original",
    recent_limit: int = 5,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNAResumeSnapshot:
    run_index = load_research_dna_run_index(
        dna_id,
        limit=1,
        root=root,
        search_eval_root=search_eval_root,
    )
    latest_run = run_index.runs[0] if run_index.runs else None
    if latest_run is None:
        return ResearchDNAResumeSnapshot(
            dna_id=dna_id,
            run_count=run_index.run_count,
            has_runs=False,
            latest_run_id=None,
        )

    normalized_variant = _normalize_screening_queue_variant(variant)
    session = load_screening_session(
        dna_id,
        run_id=latest_run.run_id,
        variant=normalized_variant,
        recent_limit=recent_limit,
        root=root,
        search_eval_root=search_eval_root,
    )
    progress = load_screening_progress_report(
        dna_id,
        run_id=latest_run.run_id,
        variant=normalized_variant,
        root=root,
        search_eval_root=search_eval_root,
    )
    recommendation, gate = load_screening_operator_guidance(
        dna_id,
        run_id=latest_run.run_id,
        root=root,
        search_eval_root=search_eval_root,
    )
    return ResearchDNAResumeSnapshot(
        dna_id=dna_id,
        run_count=run_index.run_count,
        has_runs=True,
        latest_run_id=latest_run.run_id,
        latest_run=latest_run,
        session=session,
        progress=progress,
        recommendation=recommendation,
        gate=gate,
    )


def resolve_research_dna_run_id(
    dna_id: str,
    *,
    run_id: str | None = None,
    latest: bool = False,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> str:
    normalized_run_id = str(run_id or "").strip() or None
    if normalized_run_id and latest:
        raise ResearchDNAStateError("provide either run_id or latest=true, not both")
    if normalized_run_id:
        load_research_dna(dna_id, root)
        return normalized_run_id
    if not latest:
        raise ResearchDNAStateError("provide run_id or set latest=true")

    run_index = load_research_dna_run_index(
        dna_id,
        limit=1,
        root=root,
        search_eval_root=search_eval_root,
    )
    if not run_index.latest_run_id:
        raise ResearchDNAStateError(f"latest run is unavailable for dna_id={dna_id}; pilot a run first")
    return run_index.latest_run_id


def load_screening_queue_artifact(
    dna_id: str,
    *,
    run_id: str,
    variant: ScreeningQueueVariant = "original",
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNAScreeningQueueArtifact:
    load_research_dna(dna_id, root)
    normalized_variant = _normalize_screening_queue_variant(variant)

    eval_root = (search_eval_root or default_search_eval_root()).expanduser().resolve()
    run_dir = eval_root / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise ResearchDNAStateError(f"screening queue view requires manifest.json for run_id={run_id}")

    manifest = _read_json(manifest_path)
    if manifest.get("dna_id") != dna_id:
        raise ResearchDNAStateError(
            f"screening queue run_id={run_id} belongs to dna_id={manifest.get('dna_id')}, not {dna_id}"
        )

    artifact_paths = manifest.get("artifact_paths") if isinstance(manifest.get("artifact_paths"), dict) else {}
    artifact_key = "reranked_screening_queue" if normalized_variant == "reranked" else "screening_queue"
    default_filename = "reranked_screening_queue.jsonl" if normalized_variant == "reranked" else "screening_queue.jsonl"
    artifact_path = Path(str(artifact_paths.get(artifact_key) or run_dir / default_filename))
    if not artifact_path.exists():
        if normalized_variant == "reranked":
            raise ResearchDNAStateError(
                f"reranked screening queue missing for run_id={run_id}; materialize rerank before reading it"
            )
        raise ResearchDNAStateError(f"screening queue artifact missing for run_id={run_id}: {artifact_path}")

    queries_path = Path(str(artifact_paths.get("queries") or run_dir / "queries.json"))
    query_version = str(manifest.get("query_version") or "")
    if queries_path.exists():
        queries_payload = _read_json(queries_path)
        query_version = str(queries_payload.get("query_version") or query_version)
    if not query_version:
        raise ResearchDNAStateError(f"screening queue view requires query_version for run_id={run_id}")

    rows = _read_jsonl(artifact_path)
    return ResearchDNAScreeningQueueArtifact(
        run_id=run_id,
        dna_id=dna_id,
        run_dir=str(run_dir),
        query_version=query_version,
        variant=normalized_variant,
        artifact_path=str(artifact_path),
        row_count=len(rows),
        rows=rows,
    )


def load_next_screening_candidate(
    dna_id: str,
    *,
    run_id: str,
    variant: ScreeningQueueVariant = "original",
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNANextScreeningCandidate:
    queue_artifact = load_screening_queue_artifact(
        dna_id,
        run_id=run_id,
        variant=variant,
        root=root,
        search_eval_root=search_eval_root,
    )

    run_screening_entries = _load_run_screening_entries(dna_id, run_id=run_id, root=root)
    labeled_candidate_ids = {
        entry.candidate_id.strip().lower()
        for entry in run_screening_entries
        if entry.candidate_id.strip()
    }

    next_candidate: dict[str, Any] | None = None
    queue_position: int | None = None
    remaining_count = 0
    for index, row in enumerate(queue_artifact.rows, start=1):
        candidate_id = str(row.get("candidate_id") or "").strip().lower()
        if candidate_id and candidate_id in labeled_candidate_ids:
            continue
        remaining_count += 1
        if next_candidate is None:
            next_candidate = row
            queue_position = index

    labeled_count = 0
    queue_candidate_ids = {
        str(row.get("candidate_id") or "").strip().lower()
        for row in queue_artifact.rows
        if str(row.get("candidate_id") or "").strip()
    }
    if queue_candidate_ids:
        labeled_count = sum(1 for candidate_id in labeled_candidate_ids if candidate_id in queue_candidate_ids)

    return ResearchDNANextScreeningCandidate(
        run_id=run_id,
        dna_id=dna_id,
        query_version=queue_artifact.query_version,
        variant=queue_artifact.variant,
        artifact_path=queue_artifact.artifact_path,
        total_count=queue_artifact.row_count,
        labeled_count=labeled_count,
        remaining_count=remaining_count,
        queue_position=queue_position,
        candidate=next_candidate,
    )


def load_screening_session(
    dna_id: str,
    *,
    run_id: str,
    variant: ScreeningQueueVariant = "original",
    recent_limit: int = 5,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNAScreeningSession:
    if recent_limit < 1:
        raise ResearchDNAStateError("recent_limit must be >= 1")
    if recent_limit > 20:
        raise ResearchDNAStateError("recent_limit must be <= 20")

    next_candidate = load_next_screening_candidate(
        dna_id,
        run_id=run_id,
        variant=variant,
        root=root,
        search_eval_root=search_eval_root,
    )
    queue_artifact = load_screening_queue_artifact(
        dna_id,
        run_id=run_id,
        variant=variant,
        root=root,
        search_eval_root=search_eval_root,
    )
    run_screening_entries = _load_run_screening_entries(dna_id, run_id=run_id, root=root)
    recent_decisions = sorted(run_screening_entries, key=lambda entry: entry.ts, reverse=True)[:recent_limit]

    queue_candidate_ids = {
        str(row.get("candidate_id") or "").strip().lower()
        for row in queue_artifact.rows
        if str(row.get("candidate_id") or "").strip()
    }
    latest_decisions = _latest_screening_entries_by_candidate(run_screening_entries)
    include_count = 0
    exclude_count = 0
    unclear_count = 0
    for candidate_id, entry in latest_decisions.items():
        if queue_candidate_ids and candidate_id not in queue_candidate_ids:
            continue
        if entry.decision == "include":
            include_count += 1
        elif entry.decision == "exclude":
            exclude_count += 1
        elif entry.decision == "unclear":
            unclear_count += 1

    available_variants: list[ScreeningQueueVariant] = ["original"]
    if (Path(queue_artifact.run_dir) / "reranked_screening_queue.jsonl").exists():
        available_variants.append("reranked")

    guidance_follow_summary = _build_guidance_follow_summary(
        latest_decisions=list(latest_decisions.values()),
        queue_candidate_ids=queue_candidate_ids,
    )

    return ResearchDNAScreeningSession(
        run_id=run_id,
        dna_id=dna_id,
        query_version=queue_artifact.query_version,
        variant=queue_artifact.variant,
        available_variants=available_variants,
        artifact_path=queue_artifact.artifact_path,
        total_count=next_candidate.total_count,
        labeled_count=next_candidate.labeled_count,
        remaining_count=next_candidate.remaining_count,
        include_count=include_count,
        exclude_count=exclude_count,
        unclear_count=unclear_count,
        session_complete=next_candidate.candidate is None,
        next_queue_position=next_candidate.queue_position,
        next_candidate=next_candidate.candidate,
        recent_limit=recent_limit,
        guidance_follow_summary=guidance_follow_summary,
        recent_decisions=recent_decisions,
    )


def load_screening_progress_report(
    dna_id: str,
    *,
    run_id: str,
    variant: ScreeningQueueVariant = "original",
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNAScreeningProgressReport:
    normalized_variant = _normalize_screening_queue_variant(variant)
    session = load_screening_session(
        dna_id,
        run_id=run_id,
        variant=normalized_variant,
        root=root,
        search_eval_root=search_eval_root,
    )
    recommendation, gate = load_screening_operator_guidance(
        dna_id,
        run_id=run_id,
        root=root,
        search_eval_root=search_eval_root,
    )
    queue_artifact = load_screening_queue_artifact(
        dna_id,
        run_id=run_id,
        variant=normalized_variant,
        root=root,
        search_eval_root=search_eval_root,
    )

    run_screening_entries = _load_run_screening_entries(dna_id, run_id=run_id, root=root)
    latest_decisions = list(_latest_screening_entries_by_candidate(run_screening_entries).values())
    queue_candidate_ids = {
        str(row.get("candidate_id") or "").strip().lower()
        for row in queue_artifact.rows
        if str(row.get("candidate_id") or "").strip()
    }
    top_reason_codes = _top_reason_codes_from_latest_decisions(
        latest_decisions=latest_decisions,
        queue_candidate_ids=queue_candidate_ids,
    )
    precision_proxy = round(session.include_count / session.labeled_count, 4) if session.labeled_count else 0.0

    eval_root = (search_eval_root or default_search_eval_root()).expanduser().resolve()
    run_dir = eval_root / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise ResearchDNAStateError(f"screening progress requires manifest.json for run_id={run_id}")
    manifest = _read_json(manifest_path)
    if manifest.get("dna_id") != dna_id:
        raise ResearchDNAStateError(
            f"screening progress run_id={run_id} belongs to dna_id={manifest.get('dna_id')}, not {dna_id}"
        )
    artifact_paths = manifest.get("artifact_paths") if isinstance(manifest.get("artifact_paths"), dict) else {}
    metrics_path = Path(str(artifact_paths.get("metrics") or run_dir / "metrics.json"))
    guidance_meta = manifest.get("screening_guidance") if isinstance(manifest.get("screening_guidance"), dict) else {}
    guidance_artifact_path = str(
        artifact_paths.get("screening_guidance") or guidance_meta.get("artifact_path") or ""
    ).strip() or None

    return ResearchDNAScreeningProgressReport(
        run_id=run_id,
        dna_id=dna_id,
        query_version=session.query_version,
        owner_variant=recommendation.owner_variant,
        variant=session.variant,
        available_variants=session.available_variants,
        advisory_only=True,
        recommended_variant=recommendation.recommended_variant,
        gate_status=gate.gate_status,
        primary_reason_code=recommendation.primary_reason_code,
        primary_warning_code=recommendation.primary_warning_code,
        artifact_path=session.artifact_path,
        manifest_path=str(manifest_path),
        metrics_path=str(metrics_path),
        guidance_artifact_path=guidance_artifact_path,
        labeled_count=session.labeled_count,
        remaining_count=session.remaining_count,
        include_count=session.include_count,
        exclude_count=session.exclude_count,
        unclear_count=session.unclear_count,
        precision_proxy=precision_proxy,
        session_complete=session.session_complete,
        next_candidate_id=_candidate_id_from_candidate_payload(session.next_candidate),
        top_reason_codes=top_reason_codes,
        guidance_follow_summary=session.guidance_follow_summary,
    )


def load_screening_recommendation(
    dna_id: str,
    *,
    run_id: str,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNAScreeningRecommendation:
    original_queue = load_screening_queue_artifact(
        dna_id,
        run_id=run_id,
        variant="original",
        root=root,
        search_eval_root=search_eval_root,
    )
    original_next = load_next_screening_candidate(
        dna_id,
        run_id=run_id,
        variant="original",
        root=root,
        search_eval_root=search_eval_root,
    )

    reranked_queue: ResearchDNAScreeningQueueArtifact | None = None
    reranked_next: ResearchDNANextScreeningCandidate | None = None
    available_variants: list[ScreeningQueueVariant] = ["original"]
    try:
        reranked_queue = load_screening_queue_artifact(
            dna_id,
            run_id=run_id,
            variant="reranked",
            root=root,
            search_eval_root=search_eval_root,
        )
        reranked_next = load_next_screening_candidate(
            dna_id,
            run_id=run_id,
            variant="reranked",
            root=root,
            search_eval_root=search_eval_root,
        )
        available_variants.append("reranked")
    except ResearchDNAStateError:
        reranked_queue = None
        reranked_next = None

    report: ResearchDNARerankReport | None = None
    warning_codes: list[str] = []
    rerank_report_path: str | None = None
    if reranked_queue is not None:
        run_dir = Path(original_queue.run_dir)
        manifest = _read_json(run_dir / "manifest.json")
        artifact_paths = manifest.get("artifact_paths") if isinstance(manifest.get("artifact_paths"), dict) else {}
        report_path = Path(str(artifact_paths.get("rerank_report") or run_dir / "rerank_report.json"))
        rerank_report_path = str(report_path)
        if report_path.exists():
            try:
                report = ResearchDNARerankReport.model_validate(_read_json(report_path))
                warning_codes.extend(report.warnings)
            except Exception:
                warning_codes.append("rerank_report_invalid")
        else:
            warning_codes.append("rerank_report_missing")

    screening_started = original_next.labeled_count > 0
    original_top_candidate_id = _candidate_id_from_queue_rows(original_queue.rows)
    reranked_top_candidate_id = _candidate_id_from_queue_rows(reranked_queue.rows) if reranked_queue is not None else None
    original_next_candidate_id = _candidate_id_from_candidate_payload(original_next.candidate)
    reranked_next_candidate_id = _candidate_id_from_candidate_payload(reranked_next.candidate) if reranked_next is not None else None
    top_candidate_changed = bool(
        original_top_candidate_id
        and reranked_top_candidate_id
        and original_top_candidate_id != reranked_top_candidate_id
    )

    recommended_variant: ScreeningQueueVariant = "original"
    confidence: str = "low"
    reason_codes: list[str] = []

    if screening_started:
        reason_codes.append("screening_in_progress")
    elif reranked_queue is None:
        reason_codes.append("reranked_unavailable")
    elif warning_codes:
        reason_codes.append("rerank_warnings_present")
    elif report is None:
        reason_codes.append("rerank_report_unavailable")
    elif report.changed_position_count <= 0:
        reason_codes.append("no_position_change")
    elif report.max_score <= 0.0:
        reason_codes.append("non_positive_rerank_scores")
    elif not reranked_top_candidate_id:
        reason_codes.append("reranked_top_candidate_missing")
    elif not top_candidate_changed:
        reason_codes.append("top_candidate_stable")
    else:
        recommended_variant = "reranked"
        confidence = "medium"
        reason_codes.extend(["top_candidate_changed", "positive_query_overlap_signal"])

    deduped_reason_codes = _dedupe_text_values(reason_codes)
    deduped_warning_codes = _dedupe_text_values(warning_codes)
    primary_reason_code = _primary_text_value(deduped_reason_codes)
    primary_warning_code = _primary_text_value(deduped_warning_codes)

    return ResearchDNAScreeningRecommendation(
        run_id=run_id,
        dna_id=dna_id,
        query_version=original_queue.query_version,
        owner_variant="original",
        available_variants=available_variants,
        recommended_variant=recommended_variant,
        advisory_only=True,
        confidence=confidence,  # type: ignore[arg-type]
        screening_started=screening_started,
        labeled_count=original_next.labeled_count,
        remaining_count=original_next.remaining_count,
        row_count=original_queue.row_count,
        changed_position_count=report.changed_position_count if report is not None else 0,
        changed_position_ratio=report.changed_position_ratio if report is not None else 0.0,
        top_candidate_changed=top_candidate_changed,
        original_top_candidate_id=original_top_candidate_id,
        reranked_top_candidate_id=reranked_top_candidate_id,
        original_next_candidate_id=original_next_candidate_id,
        reranked_next_candidate_id=reranked_next_candidate_id,
        rerank_algorithm_version=report.algorithm_version if report is not None else None,
        rerank_score_min=report.min_score if report is not None else None,
        rerank_score_max=report.max_score if report is not None else None,
        rerank_score_mean=report.mean_score if report is not None else None,
        rerank_top_score=report.top_score if report is not None else None,
        rerank_second_score=report.second_score if report is not None else None,
        rerank_top_score_margin=report.top_score_margin if report is not None else None,
        rerank_report_path=rerank_report_path,
        primary_reason_code=primary_reason_code,
        primary_warning_code=primary_warning_code,
        recommendation_summary=_build_recommendation_summary(
            recommended_variant,
            primary_reason_code=primary_reason_code,
        ),
        reason_codes=deduped_reason_codes,
        warning_codes=deduped_warning_codes,
    )


def _build_rerank_gate_report(
    dna_id: str,
    *,
    run_id: str,
    recommendation: ResearchDNAScreeningRecommendation,
) -> ResearchDNARerankGateReport:
    if recommendation.screening_started or recommendation.warning_codes:
        gate_status = "not_eligible"
    elif recommendation.recommended_variant == "reranked":
        gate_status = "eligible"
    else:
        gate_status = "insufficient_signal"

    score_spread: float | None = None
    if recommendation.rerank_score_min is not None and recommendation.rerank_score_max is not None:
        score_spread = round(recommendation.rerank_score_max - recommendation.rerank_score_min, 4)

    return ResearchDNARerankGateReport(
        run_id=run_id,
        dna_id=dna_id,
        query_version=recommendation.query_version,
        owner_variant=recommendation.owner_variant,
        candidate_variant="reranked",
        available_variants=recommendation.available_variants,
        recommended_variant=recommendation.recommended_variant,
        gate_status=gate_status,  # type: ignore[arg-type]
        advisory_only=True,
        screening_started=recommendation.screening_started,
        changed_position_count=recommendation.changed_position_count,
        changed_position_ratio=recommendation.changed_position_ratio,
        top_candidate_changed=recommendation.top_candidate_changed,
        row_count=recommendation.row_count,
        remaining_count=recommendation.remaining_count,
        original_top_candidate_id=recommendation.original_top_candidate_id,
        reranked_top_candidate_id=recommendation.reranked_top_candidate_id,
        rerank_algorithm_version=recommendation.rerank_algorithm_version,
        rerank_report_path=recommendation.rerank_report_path,
        rerank_score_min=recommendation.rerank_score_min,
        rerank_score_max=recommendation.rerank_score_max,
        rerank_score_mean=recommendation.rerank_score_mean,
        rerank_score_spread=score_spread,
        rerank_top_score=recommendation.rerank_top_score,
        rerank_second_score=recommendation.rerank_second_score,
        rerank_top_score_margin=recommendation.rerank_top_score_margin,
        primary_reason_code=recommendation.primary_reason_code,
        primary_warning_code=recommendation.primary_warning_code,
        gate_summary=_build_gate_summary(
            gate_status,
            primary_reason_code=recommendation.primary_reason_code,
            primary_warning_code=recommendation.primary_warning_code,
        ),
        reason_codes=recommendation.reason_codes,
        warning_codes=recommendation.warning_codes,
    )


def load_screening_operator_guidance(
    dna_id: str,
    *,
    run_id: str,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> tuple[ResearchDNAScreeningRecommendation, ResearchDNARerankGateReport]:
    recommendation = load_screening_recommendation(
        dna_id,
        run_id=run_id,
        root=root,
        search_eval_root=search_eval_root,
    )
    gate = _build_rerank_gate_report(
        dna_id,
        run_id=run_id,
        recommendation=recommendation,
    )
    return recommendation, gate


def load_rerank_gate_report(
    dna_id: str,
    *,
    run_id: str,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNARerankGateReport:
    _, gate = load_screening_operator_guidance(
        dna_id,
        run_id=run_id,
        root=root,
        search_eval_root=search_eval_root,
    )
    return gate


def submit_screening_decision_and_load_next_candidate(
    dna_id: str,
    *,
    run_id: str,
    candidate_id: str,
    decision: ScreeningDecision,
    reason_code: str,
    variant: ScreeningQueueVariant = "original",
    actor_type: ActorType,
    actor_id: str,
    note: str | None = None,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> tuple[ResearchDNA, ResearchDNANextScreeningCandidate]:
    normalized_variant = _normalize_screening_queue_variant(variant)
    owner_variant: ScreeningQueueVariant = "original"
    recommended_variant: ScreeningQueueVariant | None = None
    guidance_gate_status: RerankGateStatus | None = None
    guidance_primary_reason_code: str | None = None
    followed_guidance: bool | None = None
    try:
        recommendation, gate = load_screening_operator_guidance(
            dna_id,
            run_id=run_id,
            root=root,
            search_eval_root=search_eval_root,
        )
        owner_variant = recommendation.owner_variant
        recommended_variant = recommendation.recommended_variant
        guidance_gate_status = gate.gate_status
        guidance_primary_reason_code = recommendation.primary_reason_code
        followed_guidance = normalized_variant == recommendation.recommended_variant
    except ResearchDNAStateError:
        pass

    dna = submit_screening_decision(
        dna_id,
        run_id=run_id,
        candidate_id=candidate_id,
        decision=decision,
        reason_code=reason_code,
        variant=normalized_variant,
        owner_variant=owner_variant,
        recommended_variant=recommended_variant,
        guidance_gate_status=guidance_gate_status,
        guidance_primary_reason_code=guidance_primary_reason_code,
        followed_guidance=followed_guidance,
        actor_type=actor_type,
        actor_id=actor_id,
        note=note,
        root=root,
        search_eval_root=search_eval_root,
    )
    next_candidate = load_next_screening_candidate(
        dna_id,
        run_id=run_id,
        variant=normalized_variant,
        root=root,
        search_eval_root=search_eval_root,
    )
    return dna, next_candidate


def submit_screening_decision_and_load_session(
    dna_id: str,
    *,
    run_id: str,
    candidate_id: str,
    decision: ScreeningDecision,
    reason_code: str,
    variant: ScreeningQueueVariant = "original",
    recent_limit: int = 5,
    actor_type: ActorType,
    actor_id: str,
    note: str | None = None,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> tuple[ResearchDNA, ResearchDNANextScreeningCandidate, ResearchDNAScreeningSession]:
    dna, next_candidate = submit_screening_decision_and_load_next_candidate(
        dna_id,
        run_id=run_id,
        candidate_id=candidate_id,
        decision=decision,
        reason_code=reason_code,
        variant=variant,
        actor_type=actor_type,
        actor_id=actor_id,
        note=note,
        root=root,
        search_eval_root=search_eval_root,
    )
    session = load_screening_session(
        dna_id,
        run_id=run_id,
        variant=variant,
        recent_limit=recent_limit,
        root=root,
        search_eval_root=search_eval_root,
    )
    return dna, next_candidate, session


def screen_current_candidate_and_load_session(
    dna_id: str,
    *,
    run_id: str,
    decision: ScreeningDecision,
    reason_code: str,
    variant: ScreeningQueueVariant = "original",
    recent_limit: int = 5,
    expected_candidate_id: str | None = None,
    actor_type: ActorType,
    actor_id: str,
    note: str | None = None,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> tuple[ResearchDNA, str, ResearchDNANextScreeningCandidate, ResearchDNAScreeningSession]:
    next_candidate = load_next_screening_candidate(
        dna_id,
        run_id=run_id,
        variant=variant,
        root=root,
        search_eval_root=search_eval_root,
    )
    candidate_payload = next_candidate.candidate
    if candidate_payload is None:
        raise ResearchDNAStateError(f"no remaining screening candidates for run_id={run_id}")

    screened_candidate_id = str(candidate_payload.get("candidate_id") or "").strip()
    if not screened_candidate_id:
        raise ResearchDNAStateError(f"current screening candidate is missing candidate_id for run_id={run_id}")

    if expected_candidate_id is not None:
        normalized_expected = expected_candidate_id.strip().lower()
        if normalized_expected and normalized_expected != screened_candidate_id.lower():
            raise ResearchDNAStateError(
                f"current next candidate mismatch for run_id={run_id}: expected {expected_candidate_id}, found {screened_candidate_id}"
            )

    dna, refreshed_next_candidate, session = submit_screening_decision_and_load_session(
        dna_id,
        run_id=run_id,
        candidate_id=screened_candidate_id,
        decision=decision,
        reason_code=reason_code,
        variant=variant,
        recent_limit=recent_limit,
        actor_type=actor_type,
        actor_id=actor_id,
        note=note,
        root=root,
        search_eval_root=search_eval_root,
    )
    return dna, screened_candidate_id, refreshed_next_candidate, session


def _slugify_topic(topic: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")
    if not normalized:
        raise ValueError("Topic must contain at least one alphanumeric character")
    if not normalized.startswith("dna_"):
        normalized = f"dna_{normalized}"
    return normalized


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _default_source_fetchers() -> dict[str, object]:
    config = load_config()
    return {
        "pubmed": PubMedFetcher(config),
    }


def _paper_to_row(*, paper: Paper, dna_id: str, run_id: str, query_version: str, source: str) -> dict:
    return {
        "candidate_id": _candidate_id_for(paper),
        "paper_id": paper.id,
        "doi": paper.doi,
        "title": paper.title,
        "authors": paper.authors,
        "published": paper.published,
        "source": source,
        "link": paper.link,
        "summary": paper.summary,
        "dna_id": dna_id,
        "run_id": run_id,
        "query_version": query_version,
    }


def _candidate_id_for(paper: Paper) -> str:
    if paper.doi:
        return f"doi:{paper.doi.lower()}"
    if paper.id.upper().startswith("PMID:"):
        return paper.id.lower()
    normalized_title = re.sub(r"\s+", " ", paper.title.lower()).strip()
    published_year = (paper.published or "")[:4]
    return f"title_year:{normalized_title}:{published_year}"


def _dedupe_rows(rows: list[dict]) -> dict[str, dict]:
    deduped: dict[str, dict] = {}
    for row in rows:
        deduped.setdefault(row["candidate_id"], row)
    return deduped


def _build_reranked_screening_queue(
    *,
    dna_id: str,
    run_id: str,
    query_version: str,
    actor_type: ActorType,
    actor_id: str,
    screening_path: Path,
    screening_rows: list[dict[str, Any]],
    queries_by_source: dict[str, str],
    active_sources: list[str],
) -> tuple[list[dict[str, Any]], ResearchDNARerankReport]:
    warnings: list[str] = []
    aggregate_query_tokens: set[str] = set()
    aggregate_query_phrases: list[str] = []
    seen_phrases: set[str] = set()

    scored_rows: list[tuple[float, int, dict[str, Any]]] = []
    for original_rank, row in enumerate(screening_rows, start=1):
        source_key = str(row.get("source") or "").strip().lower()
        source_query = queries_by_source.get(source_key) or " ".join(queries_by_source.values())
        query_tokens, query_phrases = _extract_query_features(source_query)
        aggregate_query_tokens.update(query_tokens)
        for phrase in query_phrases:
            if phrase not in seen_phrases:
                seen_phrases.add(phrase)
                aggregate_query_phrases.append(phrase)

        score_payload = _score_screening_candidate(
            row=row,
            source_key=source_key,
            query_tokens=query_tokens,
            query_phrases=query_phrases,
        )
        scored_row = dict(row)
        scored_row["original_rank"] = original_rank
        scored_row["rerank_score"] = score_payload["score"]
        scored_row["rerank_version"] = "research_dna.query_overlap.v1"
        scored_row["rerank_features"] = score_payload["features"]
        scored_rows.append((score_payload["score"], original_rank, scored_row))

    if not aggregate_query_tokens and not aggregate_query_phrases:
        warnings.append("query_features_empty")

    reranked_rows: list[dict[str, Any]] = []
    scores: list[float] = []
    for rerank_rank, (_, _, row) in enumerate(
        sorted(
            scored_rows,
            key=lambda item: (
                -item[0],
                item[1],
                str(item[2].get("candidate_id") or ""),
                str(item[2].get("paper_id") or ""),
            ),
        ),
        start=1,
    ):
        row["rerank_rank"] = rerank_rank
        reranked_rows.append(row)
        scores.append(float(row["rerank_score"]))

    changed_position_count = sum(1 for row in reranked_rows if row["original_rank"] != row["rerank_rank"])
    changed_position_ratio = round(changed_position_count / len(reranked_rows), 4) if reranked_rows else 0.0
    top_candidate_id = str(reranked_rows[0].get("candidate_id") or "") if reranked_rows else None
    top_score = round(scores[0], 4) if scores else 0.0
    second_score = round(scores[1], 4) if len(scores) > 1 else None
    top_score_margin = round(scores[0] - scores[1], 4) if len(scores) > 1 else None

    report = ResearchDNARerankReport(
        evaluated_at=_now_utc(),
        run_id=run_id,
        dna_id=dna_id,
        query_version=query_version,
        actor_type=actor_type,
        actor_id=actor_id,
        active_sources=active_sources,
        screening_queue_path=str(screening_path),
        reranked_screening_queue_path=str(screening_path.parent / "reranked_screening_queue.jsonl"),
        row_count=len(reranked_rows),
        changed_position_count=changed_position_count,
        changed_position_ratio=changed_position_ratio,
        top_candidate_id=top_candidate_id or None,
        query_token_count=len(aggregate_query_tokens),
        query_phrase_count=len(aggregate_query_phrases),
        min_score=round(min(scores), 4) if scores else 0.0,
        max_score=round(max(scores), 4) if scores else 0.0,
        mean_score=round(sum(scores) / len(scores), 4) if scores else 0.0,
        top_score=top_score,
        second_score=second_score,
        top_score_margin=top_score_margin,
        warnings=warnings,
    )
    return reranked_rows, report


def _score_screening_candidate(
    *,
    row: dict[str, Any],
    source_key: str,
    query_tokens: set[str],
    query_phrases: list[str],
) -> dict[str, Any]:
    title_text = _normalize_text(row.get("title"))
    summary_text = _normalize_text(row.get("summary"))
    title_tokens = set(title_text.split())
    summary_tokens = set(summary_text.split())

    title_phrase_hits = [phrase for phrase in query_phrases if phrase and phrase in title_text]
    summary_phrase_hits = [phrase for phrase in query_phrases if phrase and phrase in summary_text and phrase not in title_phrase_hits]
    title_token_overlap = sorted(title_tokens & query_tokens)
    summary_token_overlap = sorted((summary_tokens & query_tokens) - set(title_token_overlap))

    score = (
        (len(title_phrase_hits) * 3.0)
        + (len(summary_phrase_hits) * 1.5)
        + (len(title_token_overlap) * 0.5)
        + (len(summary_token_overlap) * 0.2)
    )
    if source_key:
        score += 0.05
    score = round(score, 4)

    return {
        "score": score,
        "features": {
            "source_query": source_key,
            "matched_title_phrases": title_phrase_hits,
            "matched_summary_phrases": summary_phrase_hits,
            "matched_title_tokens": title_token_overlap,
            "matched_summary_tokens": summary_token_overlap,
            "query_token_count": len(query_tokens),
            "query_phrase_count": len(query_phrases),
        },
    }


def _extract_query_features(query_text: str) -> tuple[set[str], list[str]]:
    phrases: list[str] = []
    seen_phrases: set[str] = set()
    for raw_phrase in re.findall(r'"([^\"]+)"', query_text):
        normalized_phrase = _normalize_text(raw_phrase)
        if not normalized_phrase or normalized_phrase in seen_phrases:
            continue
        seen_phrases.add(normalized_phrase)
        phrases.append(normalized_phrase)

    tokens = {
        token
        for token in _normalize_text(re.sub(r'"[^\"]+"', " ", query_text)).split()
        if len(token) >= 3 and token not in _QUERY_TOKEN_BLACKLIST and not token.isdigit()
    }
    for phrase in phrases:
        for token in phrase.split():
            if len(token) >= 3 and token not in _QUERY_TOKEN_BLACKLIST and not token.isdigit():
                tokens.add(token)
    return tokens, phrases


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _candidate_id_from_queue_rows(rows: list[dict[str, Any]]) -> str | None:
    for row in rows:
        candidate_id = _candidate_id_from_candidate_payload(row)
        if candidate_id:
            return candidate_id
    return None


def _candidate_id_from_candidate_payload(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    candidate_id = str(payload.get("candidate_id") or "").strip()
    return candidate_id or None


def _dedupe_text_values(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = str(value or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        result.append(candidate)
    return result


def _normalize_screening_queue_variant(value: Any) -> ScreeningQueueVariant:
    normalized = str(value or "").strip().lower()
    if normalized in {"original", "reranked"}:
        return normalized  # type: ignore[return-value]
    raise ResearchDNAStateError("screening queue variant must be 'original' or 'reranked'")


def _int_or_default(value: Any, default: int) -> int:
    return value if isinstance(value, int) and value >= 0 else default


def _float_or_default(value: Any, default: float) -> float:
    if isinstance(value, (int, float)):
        numeric = float(value)
        if 0.0 <= numeric <= 1.0:
            return numeric
    return default


def _list_of_strings_or_default(value: Any, default: list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return list(default)


def _screening_variant_or_default(value: Any, *, default: ScreeningQueueVariant) -> ScreeningQueueVariant:
    normalized = str(value or "").strip().lower()
    if normalized in {"original", "reranked"}:
        return normalized  # type: ignore[return-value]
    return default


def _build_run_summary_from_entry(
    entry: RunLogEntry,
    *,
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> ResearchDNARunSummary:
    eval_root = (search_eval_root or default_search_eval_root()).expanduser().resolve()
    run_dir = eval_root / entry.run_id
    manifest_path = run_dir / "manifest.json"
    metrics_path = run_dir / "metrics.json"
    screening_queue_path = run_dir / "screening_queue.jsonl"
    reranked_screening_queue_path: str | None = None
    guidance_artifact_path: str | None = None

    query_version = entry.query_version
    status = entry.status
    sources = list(entry.sources)
    pilot_n = entry.pilot_n

    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        if (
            str(manifest.get("dna_id") or "").strip() == entry.dna_id
            and str(manifest.get("run_id") or "").strip() == entry.run_id
        ):
            query_version = str(manifest.get("query_version") or query_version)
            manifest_status = str(manifest.get("status") or "").strip()
            if manifest_status in {"started", "completed", "partial", "failed"}:
                status = manifest_status  # type: ignore[assignment]
            active_sources = manifest.get("active_sources")
            if isinstance(active_sources, list):
                sources = [str(source).strip() for source in active_sources if str(source).strip()]
            manifest_pilot_n = manifest.get("pilot_n")
            if isinstance(manifest_pilot_n, int) and 20 <= manifest_pilot_n <= 50:
                pilot_n = manifest_pilot_n

            artifact_paths = manifest.get("artifact_paths") if isinstance(manifest.get("artifact_paths"), dict) else {}
            metrics_path = Path(str(artifact_paths.get("metrics") or metrics_path))
            screening_queue_path = Path(str(artifact_paths.get("screening_queue") or screening_queue_path))
            reranked_candidate = str(artifact_paths.get("reranked_screening_queue") or "").strip()
            reranked_screening_queue_path = reranked_candidate or None
            guidance_candidate = str(artifact_paths.get("screening_guidance") or "").strip()
            guidance_artifact_path = guidance_candidate or None

    labeled_count = entry.labeled_count
    include_count = entry.include_count
    exclude_count = entry.exclude_count
    unclear_count = entry.unclear_count
    precision_proxy = entry.precision_proxy
    top_reason_codes = list(entry.top_reason_codes)
    screening_variant: ScreeningQueueVariant = "original"
    session_complete = False

    if metrics_path.exists():
        metrics = _read_json(metrics_path)
        labeled_count = _int_or_default(metrics.get("labeled_count"), labeled_count)
        include_count = _int_or_default(metrics.get("include_count"), include_count)
        exclude_count = _int_or_default(metrics.get("exclude_count"), exclude_count)
        unclear_count = _int_or_default(metrics.get("unclear_count"), unclear_count)
        precision_proxy = _float_or_default(metrics.get("precision_proxy"), precision_proxy)
        top_reason_codes = _list_of_strings_or_default(metrics.get("top_reason_codes"), top_reason_codes)
        screening_meta = metrics.get("research_dna_screening")
        if isinstance(screening_meta, dict):
            screening_variant = _screening_variant_or_default(
                screening_meta.get("variant"),
                default=screening_variant,
            )
            session_complete = bool(screening_meta.get("session_complete"))

    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        screening_progress = manifest.get("screening_progress")
        if isinstance(screening_progress, dict):
            screening_variant = _screening_variant_or_default(
                screening_progress.get("variant"),
                default=screening_variant,
            )
            session_complete = bool(screening_progress.get("session_complete", session_complete))

    return ResearchDNARunSummary(
        ts=entry.ts,
        run_id=entry.run_id,
        dna_id=entry.dna_id,
        query_version=query_version,
        status=status,
        actor_type=entry.actor_type,
        actor_id=entry.actor_id,
        sources=sources,
        retrieved_count=entry.retrieved_count,
        deduped_count=entry.deduped_count,
        dedupe_rate=entry.dedupe_rate,
        pilot_n=pilot_n,
        labeled_count=labeled_count,
        include_count=include_count,
        exclude_count=exclude_count,
        unclear_count=unclear_count,
        precision_proxy=precision_proxy,
        screening_started=labeled_count > 0,
        session_complete=session_complete,
        screening_variant=screening_variant,
        top_reason_codes=top_reason_codes,
        run_dir=str(run_dir),
        manifest_path=str(manifest_path),
        metrics_path=str(metrics_path),
        screening_queue_path=str(screening_queue_path),
        reranked_screening_queue_path=reranked_screening_queue_path,
        guidance_artifact_path=guidance_artifact_path,
    )


def _load_run_screening_entries(
    dna_id: str,
    *,
    run_id: str,
    root: Path | None = None,
) -> list[ScreeningLogEntry]:
    screening_log_path = research_dna_log_path(dna_id, "screening", root)
    screening_rows = _read_jsonl(screening_log_path) if screening_log_path.exists() else []
    return [
        ScreeningLogEntry.model_validate(sanitize_research_dna_log_payload(row))
        for row in screening_rows
        if str(row.get("run_id") or "").strip() == run_id
    ]


def _latest_screening_entries_by_candidate(
    entries: list[ScreeningLogEntry],
) -> dict[str, ScreeningLogEntry]:
    latest_by_candidate: dict[str, ScreeningLogEntry] = {}
    for entry in sorted(entries, key=lambda row: row.ts):
        candidate_id = entry.candidate_id.strip().lower()
        if candidate_id:
            latest_by_candidate[candidate_id] = entry
    return latest_by_candidate


def _build_guidance_follow_summary(
    *,
    latest_decisions: list[ScreeningLogEntry],
    queue_candidate_ids: set[str],
) -> ResearchDNAScreeningGuidanceFollowSummary:
    relevant_entries: list[ScreeningLogEntry] = []
    for entry in latest_decisions:
        candidate_id = entry.candidate_id.strip().lower()
        if queue_candidate_ids and candidate_id not in queue_candidate_ids:
            continue
        relevant_entries.append(entry)

    telemetry_entries = [
        entry
        for entry in relevant_entries
        if entry.recommended_variant is not None and entry.followed_guidance is not None
    ]
    followed_guidance_count = sum(1 for entry in telemetry_entries if entry.followed_guidance is True)
    diverged_guidance_count = sum(1 for entry in telemetry_entries if entry.followed_guidance is False)
    telemetry_count = len(telemetry_entries)

    followed_guidance_ratio: float | None = None
    if telemetry_count > 0:
        followed_guidance_ratio = round(followed_guidance_count / telemetry_count, 4)

    return ResearchDNAScreeningGuidanceFollowSummary(
        evaluated_decision_count=len(relevant_entries),
        telemetry_count=telemetry_count,
        followed_guidance_count=followed_guidance_count,
        diverged_guidance_count=diverged_guidance_count,
        followed_guidance_ratio=followed_guidance_ratio,
        recommended_reranked_count=sum(1 for entry in telemetry_entries if entry.recommended_variant == "reranked"),
        selected_reranked_count=sum(1 for entry in relevant_entries if entry.variant == "reranked"),
    )


def _top_reason_codes_from_latest_decisions(
    *,
    latest_decisions: list[ScreeningLogEntry],
    queue_candidate_ids: set[str],
    limit: int = 3,
) -> list[str]:
    counts: dict[str, int] = {}
    for entry in latest_decisions:
        candidate_id = entry.candidate_id.strip().lower()
        if queue_candidate_ids and candidate_id not in queue_candidate_ids:
            continue
        reason_code = str(entry.reason_code or "").strip()
        if not reason_code:
            continue
        counts[reason_code] = counts.get(reason_code, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [reason_code for reason_code, _ in ordered[: max(limit, 0)]]


def _best_effort_refresh_run_screening_progress_sidecars(
    dna_id: str,
    *,
    run_id: str,
    variant: ScreeningQueueVariant = "original",
    root: Path | None = None,
    search_eval_root: Path | None = None,
) -> None:
    try:
        normalized_variant = _normalize_screening_queue_variant(variant)
        eval_root = (search_eval_root or default_search_eval_root()).expanduser().resolve()
        run_dir = eval_root / run_id
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            return

        manifest = _read_json(manifest_path)
        if manifest.get("dna_id") != dna_id:
            return

        queue_artifact = load_screening_queue_artifact(
            dna_id,
            run_id=run_id,
            variant=normalized_variant,
            root=root,
            search_eval_root=search_eval_root,
        )
        session = load_screening_session(
            dna_id,
            run_id=run_id,
            variant=normalized_variant,
            root=root,
            search_eval_root=search_eval_root,
        )
        run_screening_entries = _load_run_screening_entries(dna_id, run_id=run_id, root=root)
        latest_decisions = list(_latest_screening_entries_by_candidate(run_screening_entries).values())
        queue_candidate_ids = {
            str(row.get("candidate_id") or "").strip().lower()
            for row in queue_artifact.rows
            if str(row.get("candidate_id") or "").strip()
        }
        top_reason_codes = _top_reason_codes_from_latest_decisions(
            latest_decisions=latest_decisions,
            queue_candidate_ids=queue_candidate_ids,
        )
        precision_proxy = round(session.include_count / session.labeled_count, 4) if session.labeled_count else 0.0

        artifact_paths = manifest.get("artifact_paths") if isinstance(manifest.get("artifact_paths"), dict) else {}
        metrics_path = Path(str(artifact_paths.get("metrics") or run_dir / "metrics.json"))
        metrics = _read_json(metrics_path) if metrics_path.exists() else {}
        metrics["labeled_count"] = session.labeled_count
        metrics["include_count"] = session.include_count
        metrics["exclude_count"] = session.exclude_count
        metrics["unclear_count"] = session.unclear_count
        metrics["precision_proxy"] = precision_proxy
        metrics["top_reason_codes"] = top_reason_codes
        metrics["research_dna_screening"] = {
            "updated_at": _now_utc().isoformat(),
            "variant": normalized_variant,
            "labeled_count": session.labeled_count,
            "remaining_count": session.remaining_count,
            "include_count": session.include_count,
            "exclude_count": session.exclude_count,
            "unclear_count": session.unclear_count,
            "session_complete": session.session_complete,
            "next_candidate_id": _candidate_id_from_candidate_payload(session.next_candidate),
            "top_reason_codes": top_reason_codes,
            "guidance_follow_summary": session.guidance_follow_summary.model_dump(mode="json", exclude_none=True),
        }
        _write_json(metrics_path, metrics)

        manifest["screening_progress"] = {
            "updated_at": metrics["research_dna_screening"]["updated_at"],
            "variant": normalized_variant,
            "labeled_count": session.labeled_count,
            "remaining_count": session.remaining_count,
            "session_complete": session.session_complete,
            "top_reason_codes": top_reason_codes,
            "guidance_follow_summary": session.guidance_follow_summary.model_dump(mode="json", exclude_none=True),
        }
        _write_json(manifest_path, manifest)
    except Exception:
        # Screening writes are primary; run-local progress sidecars are additive telemetry only.
        return


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ResearchDNAStateError(f"Expected JSON object: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_json(path: Path, data: dict) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    atomic_write_text(path, payload)
