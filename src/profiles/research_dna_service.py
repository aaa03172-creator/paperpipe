from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

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
    research_dna_profile_path,
    save_research_dna,
)
from src.schemas import Paper
from src.services.runtime_paths import search_eval_root as default_search_eval_root


class ResearchDNAStateError(ValueError):
    pass


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
    actor_type: ActorType,
    actor_id: str,
    note: str | None = None,
    root: Path | None = None,
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


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")
