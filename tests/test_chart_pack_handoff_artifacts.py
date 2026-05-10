from __future__ import annotations

from datetime import datetime, timezone

from src.chart_packs.handoff_artifacts import (
    build_chart_pack_acceptance_contract,
    build_chart_pack_quality_gate,
)
from src.schemas.chart_pack import ChartPack


def _sample_chart_pack(
    *,
    warning: bool = False,
    brief_review_status: str = "pass",
) -> ChartPack:
    payload: dict[str, object] = {
        "chart_pack_id": "chartpack_20260417T023000Z_demo",
        "title": "Chart handoff demo",
        "created_at": datetime(2026, 4, 17, 2, 30, tzinfo=timezone.utc),
        "charts": [
            {
                "chart_id": "chart_1",
                "title": "Verification counts",
                "template_id": "stats_check_status_counts",
                "source_ref": {
                    "source_kind": "stats_report",
                    "paper_id": "paper-001",
                    "run_id": "run-001",
                },
                "field_mappings": [
                    {"target_field": "status", "source_field": "status"},
                    {"target_field": "value", "source_field": "count"},
                ],
                "data_snapshot_ref": {"kind": "data_csv", "path": "data/chart_1.csv"},
                "spec_ref": {"kind": "spec_json", "path": "specs/chart_1.json"},
                "warnings": (
                    [
                        {
                            "code": "stats_warning",
                            "severity": "warning",
                            "message": "Review required before reuse.",
                        }
                    ]
                    if warning
                    else []
                ),
            }
        ],
        "source_items": [
            {
                "source_kind": "stats_report",
                "paper_id": "paper-001",
                "run_id": "run-001",
            }
        ],
        "artifact_brief": {
            "artifact_family": "chart_pack",
            "source_context": {
                "source_items": [
                    {
                        "source_item_id": "chart_source_01",
                        "source_type": "stats_report",
                        "ref": "paper-001/run-001",
                        "role": "canonical",
                        "layer": "review_gate_artifact",
                    }
                ]
            },
            "communicative_intent": {
                "artifact_family": "chart_pack",
                "goal": "Render deterministic verification charts.",
                "audience": "artifact reviewers",
            },
            "plan": {
                "artifact_family": "chart_pack",
                "items": [
                    {
                        "item_id": "chart_1",
                        "kind": "chart",
                        "label": "Verification counts",
                        "support_status": "direct",
                        "source_item_ids": ["chart_source_01"],
                    }
                ],
            },
        },
        "artifact_brief_review": {
            "overall_status": brief_review_status,
            "reason_codes": ["CHART_WARNING_PRESENT"] if brief_review_status == "warn" else [],
            "warnings": (
                ["Saved chart warnings are present and must remain visible in viewers and exports."]
                if brief_review_status == "warn"
                else []
            ),
        },
    }
    if warning:
        payload["warnings"] = [
            {
                "code": "stats_warning",
                "severity": "warning",
                "message": "Review required before reuse.",
            }
        ]
    return ChartPack(**payload)


def test_chart_pack_acceptance_contract_records_expected_outputs() -> None:
    pack = _sample_chart_pack()

    contract = build_chart_pack_acceptance_contract(pack=pack)

    assert contract.workflow == "chart_pack"
    assert contract.chart_pack_id == pack.chart_pack_id
    assert contract.requested_scope["chart_count"] == 1
    assert "data/chart_1.csv" in contract.expected_outputs
    assert "specs/chart_1.json" in contract.expected_outputs
    assert any(check.name == "artifact_brief_persisted" for check in contract.acceptance_checks)


def test_chart_pack_quality_gate_passes_for_clean_chart_bundle() -> None:
    pack = _sample_chart_pack(warning=False, brief_review_status="pass")

    gate = build_chart_pack_quality_gate(
        pack=pack,
        data_snapshot_ids={"chart_1"},
        spec_ids={"chart_1"},
        markdown_sync_status="in_sync",
    )

    assert gate.overall_status == "pass"
    assert gate.bundle_ready is True
    assert gate.handoff_ready is True
    assert gate.reason_codes == []


def test_chart_pack_quality_gate_warns_for_warning_heavy_bundle() -> None:
    pack = _sample_chart_pack(warning=True, brief_review_status="warn")

    gate = build_chart_pack_quality_gate(
        pack=pack,
        data_snapshot_ids={"chart_1"},
        spec_ids={"chart_1"},
        markdown_sync_status="in_sync",
    )

    check_map = {check.name: check for check in gate.checks}
    assert gate.overall_status == "warn"
    assert gate.bundle_ready is True
    assert gate.handoff_ready is False
    assert "CHART_WARNING_PRESENT" in gate.reason_codes
    assert check_map["artifact_brief_review"].status == "warn"
    assert check_map["warning_state_requires_review"].status == "warn"
