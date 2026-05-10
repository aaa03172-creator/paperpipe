from __future__ import annotations

from pathlib import Path

from src.chart_packs.store import save_chart_pack_artifact_json
from src.schemas.chart_pack import ChartPack
from src.schemas.chart_pack_handoff import (
    ChartPackAcceptanceCheck,
    ChartPackAcceptanceContract,
    ChartPackQualityGate,
    ChartPackQualityGateCheck,
)


def build_chart_pack_acceptance_contract(
    *,
    pack: ChartPack,
) -> ChartPackAcceptanceContract:
    expected_outputs = ["chart_pack.json", "chart_pack.md"]
    expected_outputs.extend(
        chart.data_snapshot_ref.path
        for chart in pack.charts
        if chart.data_snapshot_ref is not None
    )
    expected_outputs.extend(
        chart.spec_ref.path
        for chart in pack.charts
        if chart.spec_ref is not None
    )
    checks = [
        ChartPackAcceptanceCheck(
            name="chart_pack_bundle_written",
            source="storage/chart_packs/<chart_pack_id>/chart_pack.{json,md}",
            description="Primary bundle-local manifest and markdown summary were persisted.",
        ),
        ChartPackAcceptanceCheck(
            name="source_items_persisted",
            source="chart_pack.json.source_items[]",
            description="Named saved source artifacts were persisted for downstream review.",
        ),
        ChartPackAcceptanceCheck(
            name="data_snapshot_refs_persisted",
            source="chart_pack.json.charts[].data_snapshot_ref + data/<chart_id>.csv",
            description="Each chart keeps a saved tabular snapshot ref for deterministic review and export.",
        ),
        ChartPackAcceptanceCheck(
            name="spec_refs_persisted",
            source="chart_pack.json.charts[].spec_ref + specs/<chart_id>.json",
            description="Each chart keeps a saved deterministic render spec ref for downstream reuse.",
        ),
        ChartPackAcceptanceCheck(
            name="artifact_brief_persisted",
            required=False,
            source="chart_pack.json.artifact_brief + artifact_brief_review",
            description="Saved source-context vs communicative-intent review metadata exists for bounded downstream handoff.",
        ),
        ChartPackAcceptanceCheck(
            name="markdown_synced_at_write",
            source="deterministic render at bundle write time",
            description="Saved markdown matched the deterministic render when artifacts were written.",
        ),
    ]
    return ChartPackAcceptanceContract(
        chart_pack_id=pack.chart_pack_id,
        requested_scope={
            "title": pack.title,
            "chart_count": len(pack.charts),
            "charts": [
                {
                    "chart_id": chart.chart_id,
                    "template_id": chart.template_id,
                    "source_kind": chart.source_ref.source_kind,
                    "paper_id": chart.source_ref.paper_id,
                    "run_id": chart.source_ref.run_id,
                    "table_id": chart.source_ref.table_id,
                }
                for chart in pack.charts
            ],
        },
        expected_outputs=expected_outputs,
        acceptance_checks=checks,
        operator_contract={
            "review_rule": "bundle ready plus explicit warning/brief review inspection before downstream reuse",
            "owner": "current Chart Pack runtime; additive review-gate metadata only",
        },
    )


def build_chart_pack_quality_gate(
    *,
    pack: ChartPack,
    data_snapshot_ids: set[str],
    spec_ids: set[str],
    markdown_sync_status: str,
) -> ChartPackQualityGate:
    source_items_persisted = bool(pack.source_items)
    data_snapshot_refs_complete = all(
        chart.data_snapshot_ref is not None and chart.chart_id in data_snapshot_ids
        for chart in pack.charts
    )
    spec_refs_complete = all(
        chart.spec_ref is not None and chart.chart_id in spec_ids
        for chart in pack.charts
    )
    markdown_synced = markdown_sync_status == "in_sync"
    brief_review = pack.artifact_brief_review
    brief_reason_codes = list(brief_review.reason_codes) if brief_review is not None else []
    brief_review_required = bool(brief_review is not None and brief_review.overall_status != "pass")
    warning_present = bool(pack.warnings) or any(chart.warnings for chart in pack.charts)

    checks = [
        ChartPackQualityGateCheck(
            name="source_items_persisted",
            status="pass" if source_items_persisted else "fail",
            detail=str(source_items_persisted).lower(),
        ),
        ChartPackQualityGateCheck(
            name="data_snapshot_refs_complete",
            status="pass" if data_snapshot_refs_complete else "fail",
            detail=str(data_snapshot_refs_complete).lower(),
        ),
        ChartPackQualityGateCheck(
            name="spec_refs_complete",
            status="pass" if spec_refs_complete else "fail",
            detail=str(spec_refs_complete).lower(),
        ),
        ChartPackQualityGateCheck(
            name="markdown_synced_at_write",
            status="pass" if markdown_synced else "fail",
            detail=markdown_sync_status,
        ),
        ChartPackQualityGateCheck(
            name="artifact_brief_review",
            status="warn" if brief_review_required else "pass",
            detail=(
                "missing"
                if brief_review is None
                else "; ".join(brief_reason_codes) or brief_review.overall_status
            ),
        ),
        ChartPackQualityGateCheck(
            name="warning_state_requires_review",
            status="warn" if warning_present else "pass",
            detail=str(warning_present).lower(),
        ),
    ]

    reason_codes: list[str] = []
    if not source_items_persisted:
        reason_codes.append("SOURCE_ITEMS_MISSING")
    if not data_snapshot_refs_complete:
        reason_codes.append("DATA_SNAPSHOT_REFS_INCOMPLETE")
    if not spec_refs_complete:
        reason_codes.append("SPEC_REFS_INCOMPLETE")
    if not markdown_synced:
        reason_codes.append("MARKDOWN_DRIFT_AT_WRITE")
    if brief_review_required:
        reason_codes.extend(brief_reason_codes or ["ARTIFACT_BRIEF_WARN"])
    if warning_present:
        reason_codes.append("CHART_WARNING_PRESENT")
    reason_codes = list(dict.fromkeys(reason_codes))

    bundle_ready = (
        source_items_persisted
        and data_snapshot_refs_complete
        and spec_refs_complete
        and markdown_synced
    )
    handoff_ready = bundle_ready and not brief_review_required and not warning_present

    if handoff_ready:
        overall_status: str = "pass"
    elif bundle_ready:
        overall_status = "warn"
    else:
        overall_status = "fail"

    return ChartPackQualityGate(
        chart_pack_id=pack.chart_pack_id,
        overall_status=overall_status,  # type: ignore[arg-type]
        bundle_ready=bundle_ready,
        handoff_ready=handoff_ready,
        reason_codes=reason_codes,
        checks=checks,
    )


def write_chart_pack_handoff_artifacts(
    *,
    pack: ChartPack,
    markdown_sync_status: str,
    data_snapshot_ids: set[str],
    spec_ids: set[str],
    quality_gate: ChartPackQualityGate | None = None,
    root: Path | None = None,
) -> dict[str, str]:
    contract = build_chart_pack_acceptance_contract(pack=pack)
    resolved_quality_gate = quality_gate or build_chart_pack_quality_gate(
        pack=pack,
        data_snapshot_ids=data_snapshot_ids,
        spec_ids=spec_ids,
        markdown_sync_status=markdown_sync_status,
    )
    contract_path = save_chart_pack_artifact_json(
        pack.chart_pack_id,
        "acceptance_contract.json",
        contract.model_dump(mode="json", exclude_none=True),
        root=root,
    )
    quality_gate_path = save_chart_pack_artifact_json(
        pack.chart_pack_id,
        "quality_gate.json",
        resolved_quality_gate.model_dump(mode="json", exclude_none=True),
        root=root,
    )
    return {
        "acceptance_contract_path": str(contract_path),
        "quality_gate_path": str(quality_gate_path),
    }
