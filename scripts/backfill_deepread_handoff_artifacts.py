from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _ensure_package(name: str, path: Path) -> types.ModuleType:
    module = sys.modules.get(name)
    if isinstance(module, types.ModuleType):
        return module
    module = types.ModuleType(name)
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = module
    return module


def _load_module(module_name: str, path: Path) -> types.ModuleType:
    existing = sys.modules.get(module_name)
    if isinstance(existing, types.ModuleType):
        return existing
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_load_failed={module_name} path={path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_deepread_handoff_artifacts_module() -> types.ModuleType:
    _ensure_package("src", REPO_ROOT / "src")
    schemas_pkg = _ensure_package("src.schemas", REPO_ROOT / "src" / "schemas")
    services_pkg = _ensure_package("src.services", REPO_ROOT / "src" / "services")
    skills_pkg = _ensure_package("src.skills", REPO_ROOT / "src" / "skills")
    deepread_schema = _load_module(
        "src.schemas.deepread_handoff",
        REPO_ROOT / "src" / "schemas" / "deepread_handoff.py",
    )
    skills_schema = _load_module(
        "src.schemas.skills",
        REPO_ROOT / "src" / "schemas" / "skills.py",
    )
    meeting_pack_schema = _load_module(
        "src.schemas.meeting_pack",
        REPO_ROOT / "src" / "schemas" / "meeting_pack.py",
    )
    fixture_visibility = _load_module(
        "src.services.fixture_visibility",
        REPO_ROOT / "src" / "services" / "fixture_visibility.py",
    )
    storage_module = _load_module(
        "src.skills.storage",
        REPO_ROOT / "src" / "skills" / "storage.py",
    )
    setattr(schemas_pkg, "deepread_handoff", deepread_schema)
    setattr(schemas_pkg, "skills", skills_schema)
    setattr(schemas_pkg, "meeting_pack", meeting_pack_schema)
    setattr(services_pkg, "fixture_visibility", fixture_visibility)
    setattr(skills_pkg, "storage", storage_module)
    service_module = _load_module(
        "src.services.deepread_handoff_artifacts",
        REPO_ROOT / "src" / "services" / "deepread_handoff_artifacts.py",
    )
    setattr(services_pkg, "deepread_handoff_artifacts", service_module)
    return service_module


_DEEPREAD_HANDOFF_ARTIFACTS = _load_deepread_handoff_artifacts_module()
build_deepread_acceptance_contract = _DEEPREAD_HANDOFF_ARTIFACTS.build_deepread_acceptance_contract
build_deepread_context_manifest = _DEEPREAD_HANDOFF_ARTIFACTS.build_deepread_context_manifest
build_deepread_quality_gate = _DEEPREAD_HANDOFF_ARTIFACTS.build_deepread_quality_gate


@dataclass(frozen=True)
class BackfillStats:
    runs_scanned: int
    runs_needing_update: int
    runs_updated: int
    acceptance_contract_needing_update: int
    quality_gate_needing_update: int
    context_manifest_needing_update: int
    acceptance_contract_updated: int
    quality_gate_updated: int
    context_manifest_updated: int


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def _load_manifest_run_dirs(manifest_path: Path) -> list[Path]:
    payload = _load_json(manifest_path)
    if str(payload.get("schema_version") or "") != "deepread_handoff_manifest.v1":
        raise RuntimeError(f"unsupported_manifest_schema={manifest_path}")
    runs = payload.get("runs")
    if not isinstance(runs, list):
        raise RuntimeError(f"manifest_runs_missing={manifest_path}")

    run_dirs: list[Path] = []
    for index, item in enumerate(runs):
        if not isinstance(item, dict):
            raise RuntimeError(f"manifest_run_invalid={manifest_path} index={index}")
        raw_run_dir = str(item.get("run_dir") or "").strip()
        if not raw_run_dir:
            raise RuntimeError(f"manifest_run_dir_missing={manifest_path} index={index}")
        run_dirs.append(Path(raw_run_dir).expanduser().resolve())
    return run_dirs


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _collect_run_dirs(artifacts_root: Path, *, paper_ids: set[str] | None = None) -> list[Path]:
    if not artifacts_root.exists():
        return []
    run_dirs: list[Path] = []
    for path in sorted(artifacts_root.rglob("quality_gate.json")):
        run_dir = path.parent
        if paper_ids and run_dir.parent.name not in paper_ids:
            continue
        run_dirs.append(run_dir)
    return run_dirs


def resolve_run_dirs(
    *,
    artifacts_root: Path,
    manifest_paths: list[Path] | None = None,
    explicit_run_dirs: list[Path] | None = None,
    paper_ids: set[str] | None = None,
) -> list[Path]:
    normalized_manifest_paths = manifest_paths or []
    normalized_explicit_run_dirs = explicit_run_dirs or []
    resolved: list[Path] = []
    for manifest_path in normalized_manifest_paths:
        for run_dir in _load_manifest_run_dirs(manifest_path):
            if paper_ids and run_dir.parent.name not in paper_ids:
                continue
            resolved.append(run_dir)
    for run_dir in normalized_explicit_run_dirs:
        if paper_ids and run_dir.parent.name not in paper_ids:
            continue
        resolved.append(run_dir)
    if not normalized_manifest_paths and not normalized_explicit_run_dirs:
        resolved.extend(_collect_run_dirs(artifacts_root, paper_ids=paper_ids))

    unique_run_dirs: list[Path] = []
    seen: set[Path] = set()
    for run_dir in resolved:
        normalized = run_dir.expanduser().resolve()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_run_dirs.append(normalized)
    return unique_run_dirs


def _expected_handoff_payloads(run_dir: Path) -> dict[str, dict[str, Any]]:
    run_meta = _load_json(run_dir / "run_meta.json")
    bootstrap_meta = _load_json(run_dir / "bootstrap_meta.json")
    paper_id = str(run_meta.get("paper_id") or bootstrap_meta.get("paper_id") or run_dir.parent.name).strip()
    run_id = str(run_meta.get("run_id") or bootstrap_meta.get("run_id") or run_dir.name).strip()

    contract = build_deepread_acceptance_contract(
        paper_id=paper_id,
        run_id=run_id,
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )
    quality_gate = build_deepread_quality_gate(
        paper_id=paper_id,
        run_id=run_id,
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )
    context_manifest = build_deepread_context_manifest(
        paper_id=paper_id,
        run_id=run_id,
        run_meta=run_meta,
        bootstrap_meta=bootstrap_meta,
    )

    payloads = {
        "acceptance_contract.json": json.loads(contract.model_dump_json()),
        "quality_gate.json": json.loads(quality_gate.model_dump_json()),
    }
    if context_manifest is not None:
        payloads["context_manifest.json"] = json.loads(context_manifest.model_dump_json())
    return payloads


def _payload_needs_update(path: Path, expected_payload: dict[str, Any]) -> bool:
    if not path.exists():
        return True
    try:
        current_payload = _load_json(path)
    except Exception:
        return True
    return current_payload != expected_payload


def run_backfill(
    *,
    run_dirs: list[Path],
    apply_changes: bool,
) -> BackfillStats:
    runs_scanned = 0
    runs_needing_update = 0
    runs_updated = 0
    acceptance_contract_needing_update = 0
    quality_gate_needing_update = 0
    context_manifest_needing_update = 0
    acceptance_contract_updated = 0
    quality_gate_updated = 0
    context_manifest_updated = 0

    for run_dir in run_dirs:
        runs_scanned += 1
        expected_payloads = _expected_handoff_payloads(run_dir)
        changed_files: list[str] = []
        for filename, payload in expected_payloads.items():
            path = run_dir / filename
            if not _payload_needs_update(path, payload):
                continue
            changed_files.append(filename)
            if filename == "acceptance_contract.json":
                acceptance_contract_needing_update += 1
            elif filename == "quality_gate.json":
                quality_gate_needing_update += 1
            elif filename == "context_manifest.json":
                context_manifest_needing_update += 1

        if not changed_files:
            continue

        runs_needing_update += 1
        print(f"[UPDATE] {run_dir} files={','.join(changed_files)}")
        if not apply_changes:
            continue

        for filename in changed_files:
            _write_json(run_dir / filename, expected_payloads[filename])
            if filename == "acceptance_contract.json":
                acceptance_contract_updated += 1
            elif filename == "quality_gate.json":
                quality_gate_updated += 1
            elif filename == "context_manifest.json":
                context_manifest_updated += 1
        runs_updated += 1

    return BackfillStats(
        runs_scanned=runs_scanned,
        runs_needing_update=runs_needing_update,
        runs_updated=runs_updated,
        acceptance_contract_needing_update=acceptance_contract_needing_update,
        quality_gate_needing_update=quality_gate_needing_update,
        context_manifest_needing_update=context_manifest_needing_update,
        acceptance_contract_updated=acceptance_contract_updated,
        quality_gate_updated=quality_gate_updated,
        context_manifest_updated=context_manifest_updated,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill derived deep-read handoff artifacts from saved run_meta/bootstrap_meta payloads."
    )
    parser.add_argument(
        "--artifacts-root",
        default="storage/artifacts",
        help="Root directory containing paper/run artifacts (default: storage/artifacts).",
    )
    parser.add_argument("--manifest", action="append", default=[], help="Optional manifest of deep-read run directories.")
    parser.add_argument("--run-dir", action="append", default=[], help="Explicit run directory to backfill.")
    parser.add_argument("--paper-id", action="append", default=[], help="Optional paper_id filter. Repeat as needed.")
    parser.add_argument("--apply", action="store_true", help="Write updated derived artifacts to disk. Default is dry-run.")
    args = parser.parse_args()

    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    manifest_paths = [Path(item).expanduser().resolve() for item in args.manifest if str(item).strip()]
    explicit_run_dirs = [Path(item).expanduser().resolve() for item in args.run_dir if str(item).strip()]
    paper_ids = {item.strip() for item in args.paper_id if item.strip()} or None
    run_dirs = resolve_run_dirs(
        artifacts_root=artifacts_root,
        manifest_paths=manifest_paths,
        explicit_run_dirs=explicit_run_dirs,
        paper_ids=paper_ids,
    )
    if not run_dirs:
        raise SystemExit("no_run_dirs_provided")

    stats = run_backfill(run_dirs=run_dirs, apply_changes=bool(args.apply))
    print(f"[SUMMARY] runs_scanned={stats.runs_scanned}")
    print(f"[SUMMARY] runs_needing_update={stats.runs_needing_update}")
    print(f"[SUMMARY] runs_updated={stats.runs_updated}")
    print(f"[SUMMARY] acceptance_contract_needing_update={stats.acceptance_contract_needing_update}")
    print(f"[SUMMARY] quality_gate_needing_update={stats.quality_gate_needing_update}")
    print(f"[SUMMARY] context_manifest_needing_update={stats.context_manifest_needing_update}")
    print(f"[SUMMARY] acceptance_contract_updated={stats.acceptance_contract_updated}")
    print(f"[SUMMARY] quality_gate_updated={stats.quality_gate_updated}")
    print(f"[SUMMARY] context_manifest_updated={stats.context_manifest_updated}")
    if not args.apply:
        print("[SUMMARY] dry-run complete (no files written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
