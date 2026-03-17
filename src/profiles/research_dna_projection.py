from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from src.profiles.profile_schema import Limits, Profile, ProfileConfig, QuerySpec
from src.profiles.profile_metadata import RESEARCH_DNA_PROFILE_PREFIX, is_research_dna_projection_profile
from src.profiles.profile_store import load_profiles, rewrite_profiles_config
from src.profiles.research_dna_schema import ApprovalAuditEntry, QueryVersion, ResearchDNA
from src.profiles.research_dna_store import (
    append_approval_audit,
    load_research_dna,
    research_dna_profile_path,
)
from src.services.runtime_paths import profiles_config_path as default_profiles_config_path


class ResearchDNAProjectionResult(BaseModel):
    dna_id: str
    profile: Profile
    profile_path: str
    selected_database: str
    query_version: str


def projected_profile_id(dna_id: str) -> str:
    return f"{RESEARCH_DNA_PROFILE_PREFIX}{dna_id}"


def build_projected_profile(
    dna: ResearchDNA,
    *,
    query_version_name: str | None = None,
    database: str | None = None,
    root: Path | None = None,
) -> ResearchDNAProjectionResult:
    query_version = _select_query_version(dna, query_version_name)
    selected_database = _select_database(dna, query_version, database)
    exact_query = query_version.per_db[selected_database]

    must_terms = _dedupe_preserve_order(
        dna.scope.population
        + dna.scope.intervention_or_exposure
        + _fallback_query_terms_if_needed(dna.scope.population + dna.scope.intervention_or_exposure, exact_query)
    )
    should_terms = _dedupe_preserve_order(
        dna.scope.comparison
        + dna.scope.outcomes
        + [term for terms in dna.scope.concept_blocks.values() for term in terms]
    )
    must_not_terms = _dedupe_preserve_order(dna.criteria.exclude)

    span_days = _derive_date_window_days(dna)
    profile = Profile(
        id=projected_profile_id(dna.id),
        title=f"{dna.title} [DNA Projection]",
        enabled=False,
        schedule="manual",
        limits=Limits(
            max_results_per_run=min(max(dna.pilot.n, 1), 100),
            date_window_days=span_days,
        ),
        query=QuerySpec(
            must=must_terms,
            should=should_terms,
            must_not=must_not_terms,
        ),
        notes=_build_projection_notes(
            dna,
            query_version=query_version,
            selected_database=selected_database,
            exact_query=exact_query,
            root=root,
        ),
    )
    return ResearchDNAProjectionResult(
        dna_id=dna.id,
        profile=profile,
        profile_path=str(default_profiles_config_path()),
        selected_database=selected_database,
        query_version=query_version.version,
    )


def sync_research_dna_profile(
    dna_id: str,
    *,
    actor_type: str,
    actor_id: str,
    reason: str,
    query_version_name: str | None = None,
    database: str | None = None,
    root: Path | None = None,
    profiles_path: Path | None = None,
) -> ResearchDNAProjectionResult:
    dna = load_research_dna(dna_id, root)
    projection = build_projected_profile(
        dna,
        query_version_name=query_version_name,
        database=database,
        root=root,
    )
    target_path = (profiles_path or default_profiles_config_path()).expanduser().resolve()
    projection.profile_path = str(target_path)
    updated_config = rewrite_profiles_config(
        lambda config: _apply_projection_upsert(config, projection.profile, dna_id),
        target_path,
        allow_operator_bulk_update=True,
    )
    for stored_profile in updated_config.profiles:
        if stored_profile.id == projection.profile.id:
            projection.profile = stored_profile
            break
    append_approval_audit(
        dna_id,
        ApprovalAuditEntry(
            ts=_now_utc(),
            dna_id=dna_id,
            action="project_profile",
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            after_version=projection.query_version,
        ),
        root,
    )
    return projection


def _select_query_version(dna: ResearchDNA, query_version_name: str | None) -> QueryVersion:
    if not dna.query_versions:
        raise ValueError("Research DNA projection requires at least one query version")
    if query_version_name is None:
        return dna.query_versions[-1]
    for query_version in dna.query_versions:
        if query_version.version == query_version_name:
            return query_version
    raise ValueError(f"Query version not found for projection: {query_version_name}")


def _select_database(dna: ResearchDNA, query_version: QueryVersion, database: str | None) -> str:
    if database is not None:
        if database not in query_version.per_db:
            raise ValueError(f"Projected database not found in query version: {database}")
        return database

    for candidate in dna.available_databases:
        if candidate in query_version.per_db:
            return candidate
    if query_version.per_db:
        return sorted(query_version.per_db.keys())[0]
    raise ValueError(f"Query version {query_version.version} has no per_db entries")


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _fallback_query_terms_if_needed(current_terms: list[str], exact_query: str) -> list[str]:
    if any(term.strip() for term in current_terms):
        return []
    quoted = [match.strip() for match in re.findall(r'"([^"]+)"', exact_query)]
    return quoted[:8]


def _derive_date_window_days(dna: ResearchDNA) -> int:
    start = dna.filters.year_start
    end = dna.filters.year_end
    if start is not None and end is not None and end >= start:
        return max(365, (end - start + 1) * 366)
    return 365


def _build_projection_notes(
    dna: ResearchDNA,
    *,
    query_version: QueryVersion,
    selected_database: str,
    exact_query: str,
    root: Path | None,
) -> str:
    payload = {
        "schema_version": "research_dna.profile_projection.v1",
        "projection_mode": "compatibility_snapshot",
        "source_of_truth": str(research_dna_profile_path(dna.id, root)),
        "source_dna_id": dna.id,
        "source_dna_revision": dna.revision,
        "source_query_version": query_version.version,
        "selected_database": selected_database,
        "dna_status": dna.status,
        "exact_query": exact_query,
        "recommended_databases": dna.recommended_databases,
        "available_databases": dna.available_databases,
        "filters": dna.filters.model_dump(exclude_none=True),
        "criteria": dna.criteria.model_dump(exclude_none=True),
        "query_version_created_at": query_version.created_at.isoformat().replace("+00:00", "Z"),
        "projection_note": (
            "This profile is a deterministic compatibility snapshot. "
            "ResearchDNA remains the canonical editable source of truth."
        ),
    }
    header = "ResearchDNA Projection\n"
    return header + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).strip()


def _is_same_projection_owner(profile: Profile, dna_id: str) -> bool:
    return (
        profile.id == projected_profile_id(dna_id)
        and is_research_dna_projection_profile(profile)
        and f"source_dna_id: {dna_id}" in profile.notes
    )


def _apply_projection_upsert(config: ProfileConfig, profile: Profile, dna_id: str) -> ProfileConfig:
    stored_profile = profile.model_copy(deep=True)
    for idx, existing in enumerate(config.profiles):
        if existing.id != profile.id:
            continue
        if not _is_same_projection_owner(existing, dna_id):
            raise ValueError(
                f"Projected profile ID collision for {profile.id}; existing profile is not owned by {dna_id}"
            )
        stored_profile.revision = existing.revision + 1
        config.profiles[idx] = stored_profile
        return config
    stored_profile.revision = 0
    config.profiles.append(stored_profile)
    return config


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)
