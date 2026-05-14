from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
import json
import logging
from pathlib import Path
from typing import Any

from src.chart_packs.renderer import (
    render_chart_pack_markdown,
    render_chart_snapshot_csv,
    render_chart_spec,
    render_chart_svg,
)
from src.chart_packs.handoff_artifacts import write_chart_pack_handoff_artifacts
from src.chart_packs.source_loader import build_chart_data_snapshot
from src.chart_packs.store import (
    load_chart_pack_artifact_json,
    list_chart_pack_ids,
    load_chart_pack,
    load_chart_pack_data_csv,
    load_chart_pack_markdown,
    load_chart_pack_spec,
    save_chart_pack_bundle,
)
from src.chart_packs.handoff_artifacts import build_chart_pack_quality_gate
from src.schemas.chart_pack import (
    CHART_TEMPLATE_MAP,
    ChartArtifactRef,
    ChartDataSnapshot,
    ChartDefinition,
    ChartPack,
    ChartPackListResponse,
    ChartPackRequest,
    ChartPackResponse,
    ChartPackSummary,
    ChartRenderEnv,
)
from src.schemas.chart_pack_handoff import ChartPackQualityGate
from src.services.artifact_planning import build_chart_pack_artifact_brief
from src.services.listing_resilience import load_available_items


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChartPackResult:
    chart_pack: ChartPack
    markdown: str
    data_snapshots: dict[str, str]
    specs: dict[str, Any]
    quality_gate: ChartPackQualityGate | None = None


def generate_chart_pack(
    *,
    request: ChartPackRequest,
    root: Path | None = None,
    artifacts_root: Path | None = None,
    now: datetime | None = None,
) -> ChartPackResult:
    now = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    chart_definitions: list[ChartDefinition] = []
    snapshots: dict[str, ChartDataSnapshot] = {}
    data_snapshot_texts: dict[str, str] = {}
    specs: dict[str, Any] = {}
    renders: dict[str, dict[str, str]] = {}
    pack_warnings = []
    source_items = []

    for index, chart_request in enumerate(request.charts, start=1):
        chart_id = chart_request.chart_id or _new_chart_id(index, chart_request.template_id)
        template_label = CHART_TEMPLATE_MAP[chart_request.template_id].label
        chart_title = chart_request.title or f"{template_label} {index}"
        snapshot = build_chart_data_snapshot(chart_request, artifacts_root=artifacts_root)
        snapshots[chart_id] = snapshot
        data_snapshot_texts[chart_id] = render_chart_snapshot_csv(snapshot)
        chart_definition = ChartDefinition(
            chart_id=chart_id,
            title=chart_title,
            template_id=chart_request.template_id,
            source_ref=chart_request.source_ref,
            field_mappings=list(chart_request.field_mappings),
            filters=list(chart_request.filters),
            sort=chart_request.sort,
            transforms=list(snapshot.transforms),
            warnings=list(snapshot.warnings),
            data_snapshot_ref=ChartArtifactRef(
                kind="data_csv",
                path=f"data/{chart_id}.csv",
                mime_type="text/csv",
            ),
            spec_ref=ChartArtifactRef(
                kind="spec_json",
                path=f"specs/{chart_id}.json",
                mime_type="application/json",
            ),
            render_refs=[
                ChartArtifactRef(
                    kind="render_svg",
                    path=f"renders/{chart_id}.svg",
                    mime_type="image/svg+xml",
                )
            ],
        )
        spec_payload = render_chart_spec(chart_definition, snapshot)
        specs[chart_id] = spec_payload
        renders[chart_id] = {"svg": render_chart_svg(chart_definition, snapshot, spec_payload)}
        chart_definitions.append(chart_definition)
        source_items.append(chart_request.source_ref)
        pack_warnings.extend(snapshot.warnings)

    chart_pack = ChartPack(
        chart_pack_id=request.chart_pack_id or _new_chart_pack_id(request, now),
        title=request.title or _default_chart_pack_title(chart_definitions),
        created_at=request.created_at or now,
        generated_at=now,
        charts=chart_definitions,
        source_items=_dedupe_source_items(source_items),
        generation_request=request,
        render_env=ChartRenderEnv(
            engine="chart_pack_template_renderer",
            version="v0",
            notes="Deterministic template-driven spec builder over saved artifact snapshots.",
        ),
        caution_notes=_collect_caution_notes(chart_definitions, pack_warnings),
        warnings=_dedupe_warnings(pack_warnings),
    )
    artifact_brief, artifact_brief_review = build_chart_pack_artifact_brief(
        request=request,
        pack=chart_pack,
    )
    chart_pack.artifact_brief = artifact_brief
    chart_pack.artifact_brief_review = artifact_brief_review
    markdown = render_chart_pack_markdown(chart_pack, snapshots)
    quality_gate = build_chart_pack_quality_gate(
        pack=chart_pack,
        data_snapshot_ids=set(data_snapshot_texts),
        spec_ids=set(specs),
        markdown_sync_status=_chart_pack_markdown_sync_status(
            chart_pack=chart_pack,
            markdown=markdown,
            snapshots=snapshots,
        ),
    )
    save_chart_pack_bundle(
        chart_pack,
        markdown,
        data_snapshots=data_snapshot_texts,
        specs=specs,
        renders=renders,
        root=root,
    )
    _write_chart_pack_handoff_artifacts(
        chart_pack=chart_pack,
        root=root,
        markdown=markdown,
        snapshots=snapshots,
        data_snapshots=data_snapshot_texts,
        specs=specs,
        quality_gate=quality_gate,
    )
    return ChartPackResult(
        chart_pack=chart_pack,
        markdown=markdown,
        data_snapshots=data_snapshot_texts,
        specs=specs,
        quality_gate=quality_gate,
    )


def get_chart_pack(chart_pack_id: str, *, root: Path | None = None) -> ChartPackResult:
    chart_pack = load_chart_pack(chart_pack_id, root)
    markdown = load_chart_pack_markdown(chart_pack_id, root)
    data_snapshots = {
        chart.chart_id: load_chart_pack_data_csv(chart_pack_id, chart.chart_id, root)
        for chart in chart_pack.charts
        if chart.data_snapshot_ref is not None
    }
    specs = {
        chart.chart_id: load_chart_pack_spec(chart_pack_id, chart.chart_id, root)
        for chart in chart_pack.charts
        if chart.spec_ref is not None
    }
    return ChartPackResult(
        chart_pack=chart_pack,
        markdown=markdown,
        data_snapshots=data_snapshots,
        specs=specs,
        quality_gate=_load_chart_pack_quality_gate(chart_pack_id, root=root),
    )


def list_chart_pack_summaries(*, root: Path | None = None) -> list[ChartPack]:
    items = load_available_items(
        list_chart_pack_ids(root),
        lambda chart_pack_id: load_chart_pack(chart_pack_id, root),
        item_kind="chart pack",
        logger=logger,
    )
    return sorted(
        items,
        key=lambda item: (item.generated_at or item.created_at, item.chart_pack_id),
        reverse=True,
    )


def chart_pack_response_payload(result: ChartPackResult) -> ChartPackResponse:
    return ChartPackResponse(
        chart_pack=result.chart_pack,
        markdown=result.markdown,
        data_snapshots=result.data_snapshots,
        specs=result.specs,
        quality_gate=result.quality_gate,
    )


def chart_pack_list_response(*, root: Path | None = None) -> ChartPackListResponse:
    items = [
        ChartPackSummary(
            chart_pack_id=chart_pack.chart_pack_id,
            title=chart_pack.title,
            created_at=chart_pack.created_at,
            generated_at=chart_pack.generated_at,
            chart_count=len(chart_pack.charts),
            warning_count=len(chart_pack.warnings),
        )
        for chart_pack in list_chart_pack_summaries(root=root)
    ]
    return ChartPackListResponse(items=items, total=len(items))


def _new_chart_id(index: int, template_id: str) -> str:
    suffix = template_id.replace("_", "-")
    return f"chart_{index:02d}_{suffix}"


def _new_chart_pack_id(request: ChartPackRequest, now: datetime) -> str:
    payload = request.model_dump(mode="json", exclude_none=True)
    digest = sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:8]
    return f"chartpack_{now.strftime('%Y%m%dT%H%M%SZ')}_{digest}"


def _default_chart_pack_title(charts: list[ChartDefinition]) -> str:
    if not charts:
        return "Chart pack"
    if len(charts) == 1:
        return f"{charts[0].title} chart pack"
    return f"{charts[0].title} + {len(charts) - 1} more chart pack"


def _collect_caution_notes(
    charts: list[ChartDefinition],
    warnings: list[Any],
) -> list[str]:
    notes = []
    if any(warning.severity in {"warning", "error"} for warning in warnings):
        notes.append("Some charts include warning states; inspect source lineage before reuse.")
    if any(chart.template_id == "reported_vs_computed_p_scatter" for chart in charts):
        notes.append("Reported/computed p charts include only exact numeric pairs and skip approximate values.")
    if any(chart.template_id in {"table_numeric_bar", "table_numeric_line"} for chart in charts):
        notes.append("Document-table charts rely on saved table structure and explicit numeric coercion only.")
    return _dedupe_non_empty_strings(notes)


def _dedupe_source_items(source_items):
    deduped = []
    seen = set()
    for source in source_items:
        key = (
            source.source_kind,
            source.paper_id,
            source.run_id,
            source.table_id,
            source.source_label,
        )
        if key not in seen:
            deduped.append(source)
            seen.add(key)
    return deduped


def _dedupe_warnings(warnings):
    deduped = []
    seen = set()
    for warning in warnings:
        key = (warning.code, warning.severity, warning.message)
        if key not in seen:
            deduped.append(warning)
            seen.add(key)
    return deduped


def _dedupe_non_empty_strings(values: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for raw in values:
        text = str(raw or "").strip()
        if text and text not in seen:
            deduped.append(text)
            seen.add(text)
    return deduped


def _write_chart_pack_handoff_artifacts(
    *,
    chart_pack: ChartPack,
    root: Path | None,
    markdown: str,
    snapshots: dict[str, ChartDataSnapshot],
    data_snapshots: dict[str, str],
    specs: dict[str, Any],
    quality_gate: ChartPackQualityGate,
) -> None:
    markdown_sync_status = _chart_pack_markdown_sync_status(
        chart_pack=chart_pack,
        markdown=markdown,
        snapshots=snapshots,
    )
    try:
        write_chart_pack_handoff_artifacts(
            pack=chart_pack,
            markdown_sync_status=markdown_sync_status,
            data_snapshot_ids=set(data_snapshots),
            spec_ids=set(specs),
            quality_gate=quality_gate,
            root=root,
        )
    except Exception as exc:
        logger.warning(
            "Failed to write Chart Pack handoff artifacts for %s: %s",
            chart_pack.chart_pack_id,
            exc,
        )


def _chart_pack_markdown_sync_status(
    *,
    chart_pack: ChartPack,
    markdown: str,
    snapshots: dict[str, ChartDataSnapshot],
) -> str:
    return "in_sync" if markdown == render_chart_pack_markdown(chart_pack, snapshots) else "drifted"


def _load_chart_pack_quality_gate(
    chart_pack_id: str,
    *,
    root: Path | None = None,
) -> ChartPackQualityGate | None:
    try:
        payload = load_chart_pack_artifact_json(chart_pack_id, "quality_gate.json", root)
    except FileNotFoundError:
        return None
    except ValueError as exc:
        logger.warning(
            "Ignoring unreadable Chart Pack quality gate for %s: %s",
            chart_pack_id,
            exc,
        )
        return None
    try:
        return ChartPackQualityGate(**payload)
    except Exception as exc:
        logger.warning(
            "Ignoring invalid Chart Pack quality gate payload for %s: %s",
            chart_pack_id,
            exc,
        )
        return None
