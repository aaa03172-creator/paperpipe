from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any

from src import db_utils
from src.method_comparisons.renderer import (
    render_method_comparison_csv,
    render_method_comparison_markdown,
)
from src.method_comparisons.source_loader import (
    ClaimsetResolvedSource,
    build_claimset_comparison_row,
    load_claimset_resolved_source,
)
from src.method_comparisons.store import (
    list_method_comparison_ids,
    load_method_comparison,
    load_method_comparison_csv,
    load_method_comparison_markdown,
    save_method_comparison_bundle,
)
from src.schemas.method_comparison import (
    MethodComparison,
    MethodComparisonListItem,
    MethodComparisonListResponse,
    MethodComparisonResponse,
    MethodComparisonRequest,
    build_method_comparison_columns,
)
from src.skills.storage import load_structured_state, resolve_note_path, safe_read_text, split_frontmatter


@dataclass(frozen=True)
class MethodComparisonResult:
    comparison: MethodComparison
    csv_text: str
    markdown: str


def generate_method_comparison(
    *,
    request: MethodComparisonRequest,
    root: Path | None = None,
    artifacts_root: Path | None = None,
    vault_path: Path | None = None,
    paper_slug_overrides: dict[str, str] | None = None,
    paper_title_overrides: dict[str, str] | None = None,
    allow_paper_id_slug_fallback: bool = False,
    now: datetime | None = None,
) -> MethodComparisonResult:
    now = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    rows = []
    warnings: list[str] = []

    for paper_id in request.paper_ids:
        source = load_claimset_resolved_source(paper_id, root=artifacts_root)
        paper_slug, slug_warning = _resolve_paper_slug(
            paper_id=paper_id,
            source=source,
            vault_path=vault_path,
            overrides=paper_slug_overrides or {},
            allow_paper_id_slug_fallback=allow_paper_id_slug_fallback,
        )
        if slug_warning:
            warnings.append(slug_warning)
        title = _resolve_paper_title(
            paper_id=paper_id,
            paper_slug=paper_slug,
            source=source,
            vault_path=vault_path,
            overrides=paper_title_overrides or {},
        )
        rows.append(
            build_claimset_comparison_row(
                source,
                request.field_ids,
                paper_slug=paper_slug,
                title=title,
            )
        )

    comparison = MethodComparison(
        comparison_id=request.comparison_id or _new_method_comparison_id(request.paper_ids, request.field_ids, now),
        title=request.title or _default_comparison_title(rows),
        created_at=request.created_at or now,
        generated_at=now,
        paper_ids=list(request.paper_ids),
        columns=build_method_comparison_columns(request.field_ids),
        rows=rows,
        source_summary={
            "source_priority": ["claimset.resolved.json", "document_artifact", "paper_note_state"],
            "source_paper_count": len(rows),
            "note_backed_paper_count": 0,
            "operator_override_count": 0,
            "note": "v0 generation currently reads only claimset.resolved.json-backed method cells.",
        },
        warnings=warnings,
    )
    csv_text = render_method_comparison_csv(comparison)
    markdown = render_method_comparison_markdown(comparison)
    save_method_comparison_bundle(comparison, csv_text, markdown, root)
    return MethodComparisonResult(comparison=comparison, csv_text=csv_text, markdown=markdown)


def get_method_comparison(comparison_id: str, *, root: Path | None = None) -> MethodComparisonResult:
    comparison = load_method_comparison(comparison_id, root)
    csv_text = load_method_comparison_csv(comparison_id, root)
    markdown = load_method_comparison_markdown(comparison_id, root)
    return MethodComparisonResult(comparison=comparison, csv_text=csv_text, markdown=markdown)


def list_method_comparison_summaries(*, root: Path | None = None) -> list[MethodComparison]:
    items = [load_method_comparison(comparison_id, root) for comparison_id in list_method_comparison_ids(root)]
    return sorted(
        items,
        key=lambda item: (item.generated_at or item.created_at, item.comparison_id),
        reverse=True,
    )


def method_comparison_response_payload(result: MethodComparisonResult) -> MethodComparisonResponse:
    return MethodComparisonResponse(
        comparison=result.comparison,
        csv_text=result.csv_text,
        markdown=result.markdown,
    )


def method_comparison_list_response(*, root: Path | None = None) -> MethodComparisonListResponse:
    items = [
        MethodComparisonListItem(
            comparison_id=comparison.comparison_id,
            title=comparison.title,
            created_at=comparison.created_at,
            generated_at=comparison.generated_at,
            paper_count=len(comparison.paper_ids),
            field_count=len(comparison.columns),
            warning_count=len(comparison.warnings),
        )
        for comparison in list_method_comparison_summaries(root=root)
    ]
    return MethodComparisonListResponse(items=items, total=len(items))


def _resolve_paper_slug(
    *,
    paper_id: str,
    source: ClaimsetResolvedSource,
    vault_path: Path | None,
    overrides: dict[str, str],
    allow_paper_id_slug_fallback: bool,
) -> tuple[str, str | None]:
    override = str(overrides.get(paper_id) or "").strip()
    if override:
        return override, None

    if vault_path is not None:
        slug = _find_slug_by_candidate_id(vault_path, paper_id)
        if slug:
            return slug, None
        if source.claimset_doc_id:
            slug = _find_slug_by_candidate_id(vault_path, source.claimset_doc_id)
            if slug:
                return slug, None

    if allow_paper_id_slug_fallback:
        return paper_id, f"paper_slug unresolved for {paper_id}; using paper_id as fallback."

    raise ValueError(
        "Method Comparison generation could not resolve paper_slug for "
        f"paper_id={paper_id}. Pass `vault_path`, `paper_slug_overrides`, or enable explicit fallback."
    )


def _resolve_paper_title(
    *,
    paper_id: str,
    paper_slug: str,
    source: ClaimsetResolvedSource,
    vault_path: Path | None,
    overrides: dict[str, str],
) -> str:
    override = str(overrides.get(paper_id) or "").strip()
    if override:
        return override

    row = db_utils.get_paper_by_id(paper_id)
    if isinstance(row, dict):
        title = str(row.get("title") or "").strip()
        if title:
            return title

    if vault_path is not None:
        note_title = _paper_title(vault_path, paper_slug)
        if note_title:
            return note_title

    if source.claimset_doc_id:
        return source.claimset_doc_id
    return paper_id


def _default_comparison_title(rows: list[Any]) -> str:
    if not rows:
        return "Method comparison"
    if len(rows) == 1:
        return f"{rows[0].title} method comparison"
    return f"{rows[0].title} + {len(rows) - 1} more method comparison"


def _new_method_comparison_id(
    paper_ids: list[str],
    field_ids: list[str],
    now: datetime,
) -> str:
    digest = sha1("|".join([*paper_ids, *field_ids]).encode("utf-8")).hexdigest()[:8]
    return f"methodcmp_{now.strftime('%Y%m%dT%H%M%SZ')}_{digest}"


def _find_slug_by_candidate_id(vault_path: Path, candidate_id: str) -> str | None:
    target_variants = _identifier_variants(candidate_id)
    if not target_variants:
        return None
    sidecar_root = vault_path / ".pp"
    if not sidecar_root.exists():
        return None

    direct_state = load_structured_state(vault_path, candidate_id, None)
    if direct_state is not None:
        return candidate_id

    for state_path in sorted(sidecar_root.glob("*/state.json")):
        slug = state_path.parent.name
        variants = {slug.lower()}
        state = load_structured_state(vault_path, slug, None)
        if state is not None:
            variants.update(_identifier_variants(state.paper_slug))
        note_path = resolve_note_path(vault_path, slug)
        if note_path is not None:
            frontmatter, _body = split_frontmatter(safe_read_text(note_path))
            for key in ("id", "doi"):
                variants.update(_identifier_variants(frontmatter.get(key)))
        if target_variants & variants:
            return slug
    return None


def _identifier_variants(value: Any) -> set[str]:
    text = str(value or "").strip().lower()
    if not text:
        return set()
    variants = {text}
    if text.startswith("doi:"):
        variants.add(text.split(":", 1)[1].strip())
    if "doi.org/" in text:
        variants.add(text.split("doi.org/", 1)[1].strip("/"))
    if text.startswith("zotero:"):
        variants.add(text.split(":", 1)[1].strip())
    return {variant for variant in variants if variant}


def _paper_title(vault_path: Path, slug: str) -> str:
    note_path = resolve_note_path(vault_path, slug)
    if note_path is None:
        return slug
    frontmatter, body = split_frontmatter(safe_read_text(note_path))
    aliases = frontmatter.get("aliases")
    if isinstance(aliases, list):
        for item in aliases:
            text = str(item or "").strip()
            if text:
                return text
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title
    return slug
