#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _schema_contract(root: Path) -> dict[str, object]:
    path = root / "src" / "schemas" / "paper_synthesis.py"
    text = _read_text(path)
    checks = {
        "schema_file_present": path.exists(),
        "artifact_family_present": "artifact_family" in text,
        "template_kind_present": "template_kind" in text,
        "layer_present": 'layer: Literal["compiled_knowledge"]' in text,
        "canonical_status_present": 'canonical_status: Literal["non_canonical"]' in text,
        "source_refs_present": "source_refs: list[PaperSynthesisSourceRef]" in text,
        "lineage_summary_present": "lineage_summary: PaperSynthesisLineageSummary" in text,
        "minimum_source_guard_present": "PaperSynthesis.source_refs must include" in text,
        "readiness_guard_present": "evidence_backed cannot coexist with warnings or uncertainty_notes" in text,
    }
    return {"ready": all(checks.values()), **checks}


def _store_contract(root: Path) -> dict[str, object]:
    path = root / "src" / "paper_syntheses" / "store.py"
    text = _read_text(path)
    checks = {
        "store_file_present": path.exists(),
        "json_filename_present": '"paper_synthesis.json"' in text,
        "markdown_filename_present": '"paper_synthesis.md"' in text,
        "save_bundle_present": "def save_paper_synthesis_bundle(" in text,
        "load_json_present": "def load_paper_synthesis(" in text,
        "load_markdown_present": "def load_paper_synthesis_markdown(" in text,
        "rollback_restore_present": "_restore_optional_text(" in text,
        "cleanup_empty_dir_present": "_remove_empty_dir(" in text,
    }
    return {"ready": all(checks.values()), **checks}


def _renderer_contract(root: Path) -> dict[str, object]:
    path = root / "src" / "paper_syntheses" / "renderer.py"
    text = _read_text(path)
    checks = {
        "renderer_file_present": path.exists(),
        "frontmatter_artifact_family_present": 'f"artifact_family: {synthesis.artifact_family}"' in text,
        "frontmatter_template_kind_present": 'f"template_kind: {synthesis.template_kind}"' in text,
        "frontmatter_layer_present": 'f"layer: {synthesis.layer}"' in text,
        "frontmatter_canonical_status_present": 'f"canonical_status: {synthesis.canonical_status}"' in text,
        "frontmatter_source_refs_present": '"source_refs:"' in text,
        "layer_contract_section_present": '"## Layer contract"' in text,
        "promotion_guardrail_present": '"## Promotion guardrail"' in text,
    }
    return {"ready": all(checks.values()), **checks}


def _route_contract(root: Path) -> dict[str, object]:
    path = root / "backend" / "routers" / "paper_syntheses.py"
    text = _read_text(path)
    checks = {
        "router_file_present": path.exists(),
        "compatibility_route_present": '@router.get(\n    "/{synthesis_id}"' in text,
        "manifest_route_present": '@router.get(\n    "/{synthesis_id}/manifest"' in text,
        "markdown_route_present": '@router.get(\n    "/{synthesis_id}/markdown"' in text,
        "preferred_manifest_header_present": '"PaperPipe-Preferred-Manifest-Route"' in text,
        "preferred_markdown_header_present": '"PaperPipe-Preferred-Markdown-Route"' in text,
        "compatibility_route_logging_present": "deprecated_bundle_read" in text,
    }
    return {"ready": all(checks.values()), **checks}


def _guardrail_contract(root: Path) -> dict[str, object]:
    service_test_path = root / "tests" / "test_paper_synthesis_service.py"
    api_test_path = root / "tests" / "test_paper_syntheses_api.py"
    allowlist_test_path = root / "tests" / "test_no_new_paper_synthesis_bundle_route_usage.py"
    audit_script_path = root / "scripts" / "check_paper_synthesis_bundle_route_usage.py"
    readiness_script_path = root / "scripts" / "check_paper_synthesis_bundle_route_removal_readiness.py"

    service_test_text = _read_text(service_test_path)
    api_test_text = _read_text(api_test_path)
    allowlist_test_text = _read_text(allowlist_test_path)

    checks = {
        "service_test_present": service_test_path.exists(),
        "api_test_present": api_test_path.exists(),
        "allowlist_test_present": allowlist_test_path.exists(),
        "audit_script_present": audit_script_path.exists(),
        "readiness_script_present": readiness_script_path.exists(),
        "lineage_summary_assertions_present": "lineage_summary" in service_test_text and "lineage_summary" in api_test_text,
        "manifest_route_assertion_present": "/manifest" in api_test_text,
        "allowlist_guard_assertion_present": "compatibility bundle route should not spread outside allowlist" in allowlist_test_text,
    }
    return {"ready": all(checks.values()), **checks}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize whether the current repo still satisfies the bounded paper-synthesis manifest conformance contract."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to inspect. Default: current working directory.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    schema_contract = _schema_contract(root)
    store_contract = _store_contract(root)
    renderer_contract = _renderer_contract(root)
    route_contract = _route_contract(root)
    guardrail_contract = _guardrail_contract(root)

    ready = all(
        contract["ready"]
        for contract in (
            schema_contract,
            store_contract,
            renderer_contract,
            route_contract,
            guardrail_contract,
        )
    )

    summary = {
        "root": str(root),
        "artifact_family": "paper_synthesis",
        "conformant": ready,
        "schema_contract": schema_contract,
        "store_contract": store_contract,
        "renderer_contract": renderer_contract,
        "route_contract": route_contract,
        "guardrail_contract": guardrail_contract,
    }
    print(json.dumps(summary, indent=2))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
