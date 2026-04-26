import asyncio
import ast
from contextlib import nullcontext
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import types

import scripts.bootstrap as bootstrap
from rich.console import Console

from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2, SpanV2
from src.schemas import BiomedicalClinicalExtraction
from src.schemas.agent_artifacts import ClaimSet, ScientificClaim
from src.timeout_policy import StepTimeoutError


def test_bootstrap_teacher_review_uses_configured_provider_and_repairs_wrapped_json(monkeypatch):
    class FakeProvider:
        def __init__(self):
            self.calls = []

        def is_available(self):
            return True

        def review_claimset_bundle(self, *, prompt: str, system_prompt: str | None = None):
            self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
            return json.dumps(
                {
                    "claimset": {
                        "doc_id": "doc:test",
                        "claims": [
                            {
                                "claim_id": "CLM-1",
                                "type": "efficacy",
                                "statement": "The treatment improved the outcome.",
                                "evidence_spans": [
                                    {
                                        "raw_text": "The treatment improved the outcome.",
                                        "quote": "The treatment improved the outcome.",
                                        "rationale": "Direct support from the provided excerpt.",
                                    }
                                ],
                                "limitations": [],
                                "confidence": 0.5,
                            }
                        ],
                    }
                }
            )

    provider = FakeProvider()
    monkeypatch.setattr(bootstrap, "load_config", lambda: SimpleNamespace(llm=SimpleNamespace()))
    monkeypatch.setattr(bootstrap, "get_llm_provider", lambda _cfg: provider)

    result = asyncio.run(
        bootstrap.run_teacher_review(
            {"doc_id": "doc:test", "claims": []},
            "The treatment improved the outcome.",
            "Biomedical Paper Analysis",
        )
    )

    assert result is not None
    assert result.doc_id == "doc:test"
    assert len(result.claims) == 1
    assert result.claims[0].evidence_spans[0].raw_text == "The treatment improved the outcome."
    assert provider.calls and "Biomedical Paper Analysis" in provider.calls[0]["prompt"]


def test_run_batch_script_executes_without_scripts_import_failure(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_batch.py"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0
    assert "ModuleNotFoundError" not in combined
    assert "Zotero export not found" in combined


def test_backend_api_smoke_script_runs_legacy_alias_audit() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_backend_api_smoke.sh"

    content = script_path.read_text(encoding="utf-8")

    assert 'scripts/resolve_verification_python.py" --require-module pytest' in content
    assert '"${PYTHON_BIN}" scripts/check_legacy_trial_extraction_alias.py --root .' in content


def test_verify_wrappers_use_resolved_python_runner() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_expectations = {
        "run_agents_smoke.sh": ["--require-module pytest", "--require-module langgraph", '"${PYTHON_BIN}" -m pytest -q'],
        "run_backend_api_smoke.sh": ["--require-module pytest", '"${PYTHON_BIN}" -m pytest -q'],
        "run_escalation_judge_verify.sh": ["--require-module pytest", '"${PYTHON_BIN}" -m pytest -q'],
        "run_meeting_pack_verify.sh": ["--require-module pytest", '"${PYTHON_BIN}" -m pytest -q'],
    }

    for script_name, snippets in script_expectations.items():
        content = (repo_root / "scripts" / script_name).read_text(encoding="utf-8")
        assert 'RESOLVER_RUNNER="$(command -v python3 || command -v python)"' in content
        assert 'scripts/resolve_verification_python.py' in content
        for snippet in snippets:
            assert snippet in content


def test_talk_pack_render_smoke_wrapper_uses_resolved_python_runner() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "scripts" / "run_talk_pack_render_smoke.sh").read_text(encoding="utf-8")

    assert 'RESOLVER_RUNNER="$(command -v python3 || command -v python)"' in content
    assert 'scripts/resolve_verification_python.py" --require-module yaml' in content
    assert '"${PYTHON_BIN}" scripts/check_talk_pack_render_smoke.py "$@"' in content


def test_talk_pack_verify_wrapper_uses_resolved_python_runner() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "scripts" / "run_talk_pack_verify.sh").read_text(encoding="utf-8")

    assert 'RESOLVER_RUNNER="$(command -v python3 || command -v python)"' in content
    assert 'scripts/resolve_verification_python.py" --require-module pytest --require-module yaml' in content
    assert 'ruff check "${RUFF_TARGETS[@]}" --select F,E701,E9' in content
    assert '"${PYTHON_BIN}" -m pytest -q "${PYTEST_TARGETS[@]}"' in content
    assert '"${PYTHON_BIN}" scripts/check_talk_pack_render_smoke.py --root "${TALK_PACK_SMOKE_ROOT}"' in content
    assert 'TALK_PACK_IMAGE_EVIDENCE_SMOKE_ROOT="tmp/talk_pack_render_smoke_image_evidence"' in content
    assert '--talk-pack-id "talkpack_smoke_render_image_evidence_demo"' in content
    assert '--visual-source image_evidence' in content


def test_production_code_keeps_legacy_generate_deep_read_helper_out_of_runtime_callers() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    offenders: list[str] = []

    for path in sorted(src_root.rglob("*.py")):
        if path.name == "llm_provider.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "generate_deep_read":
                offenders.append(f"{path.relative_to(repo_root)}:{node.lineno}")
            elif isinstance(func, ast.Name) and func.id == "generate_deep_read":
                offenders.append(f"{path.relative_to(repo_root)}:{node.lineno}")

    assert offenders == []


def test_macos_personal_runtime_local_proof_wrapper_uses_resolved_python_and_packaged_probes() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_macos_personal_runtime_local_proof.sh"

    content = script_path.read_text(encoding="utf-8")

    assert 'scripts/resolve_verification_python.py" --require-module yaml --require-module fastapi --require-module uvicorn' in content
    assert 'RELEASE_CMD=("${PYTHON_BIN}" "${ROOT_DIR}/scripts/release_macos_personal_runtime.py" --release-dir "${RELEASE_DIR}")' in content
    assert 'RELEASE_CMD+=("${BUILD_ARGS[@]}")' in content
    assert '"${RELEASE_CMD[@]}"' in content
    assert 'PAPERPIPE_CONFIG_PATH="${CONFIG_PATH}" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/lattice self-test --json' in content
    assert 'PAPERPIPE_CONFIG_PATH="${CONFIG_PATH}" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/Lattice.app/Contents/MacOS/Lattice self-test --json' in content
    assert 'pkill -TERM -P "${APP_PID}" 2>/dev/null || true' in content
    assert 'kill -KILL "${APP_PID}" 2>/dev/null || true' in content
    assert 'curl -sS -o "${RELEASE_DIR}/ui.html" -w \'%{http_code}\' "http://127.0.0.1:${PORT}/ui"' in content
    assert '"${ROOT_DIR}/.venv/bin/python"' not in content


def test_macos_personal_runtime_gatekeeper_prereq_wrapper_uses_resolved_python_and_release_check() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_macos_personal_runtime_gatekeeper_prereqs.sh"

    content = script_path.read_text(encoding="utf-8")

    assert 'PYTHON_BIN="$("${RESOLVER_RUNNER}" "${ROOT_DIR}/scripts/resolve_verification_python.py")"' in content
    assert 'OUTPUT_BASENAME="$(mktemp /tmp/lattice-gatekeeper-prereqs.XXXXXX)"' in content
    assert 'OUTPUT_PATH="${OUTPUT_BASENAME}.json"' in content
    assert 'mktemp /tmp/lattice-gatekeeper-prereqs.XXXXXX.json' not in content
    assert 'CHECK_CMD=("${PYTHON_BIN}" "${ROOT_DIR}/scripts/release_macos_personal_runtime.py" --check-prereqs)' in content
    assert 'CHECK_CMD+=("--identity" "${IDENTITY}")' in content
    assert 'CHECK_CMD+=("--notary-profile" "${NOTARY_PROFILE}")' in content
    assert 'report_path=${OUTPUT_PATH}' in content
    assert '"${ROOT_DIR}/.venv/bin/python"' not in content


def test_legacy_trial_extraction_alias_audit_script_flags_legacy_yaml(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "config.yaml").write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
    slot_classification:
      enabled: false
    one_liner:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_legacy_trial_extraction_alias.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["offender_count"] == 1
    assert payload["offenders"] == ["config.yaml"]
    assert payload["removal_date"] == "2026-06-30"


def test_legacy_trial_extraction_alias_audit_script_ignores_generated_and_specialty_configs(tmp_path):
    workspace = tmp_path / "workspace"
    generated_dir = workspace / "storage" / "artifacts" / "run-1" / "snapshots"
    generated_dir.mkdir(parents=True)
    (generated_dir / "config.yaml").write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )
    (workspace / "config.yaml").write_text(
        """
llm:
  features:
    specialty_trial_extraction:
      enabled: false
    slot_classification:
      enabled: false
    one_liner:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_legacy_trial_extraction_alias.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["offender_count"] == 0
    assert payload["offenders"] == []
    assert payload["preserved_historical_snapshot_count"] == 0


def test_legacy_trial_extraction_alias_migration_script_rewrites_legacy_yaml(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = workspace / "config.yaml"
    config_path.write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
    slot_classification:
      enabled: false
    one_liner:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "migrate_legacy_trial_extraction_alias.py"

    dry_run = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    dry_payload = json.loads(dry_run.stdout)
    assert dry_run.returncode == 2
    assert dry_payload["mode"] == "dry_run"
    assert dry_payload["rewritten_files"] == ["config.yaml"]
    assert "trial_extraction:" in config_path.read_text(encoding="utf-8")

    apply_run = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace), "--apply"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    apply_payload = json.loads(apply_run.stdout)
    updated = config_path.read_text(encoding="utf-8")
    assert apply_run.returncode == 0
    assert apply_payload["mode"] == "apply"
    assert apply_payload["rewritten_files"] == ["config.yaml"]
    assert "specialty_trial_extraction:" in updated
    assert "\n    trial_extraction:" not in f"\n{updated}"


def test_legacy_trial_extraction_alias_migration_script_skips_generated_dirs_by_default(tmp_path):
    workspace = tmp_path / "workspace"
    generated_dir = workspace / "storage" / "artifacts" / "run-1" / "snapshots"
    generated_dir.mkdir(parents=True)
    generated_config = generated_dir / "config.yaml"
    generated_config.write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "migrate_legacy_trial_extraction_alias.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace), "--apply"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["rewritten_count"] == 0
    assert payload["rewritten_files"] == []
    assert "trial_extraction:" in generated_config.read_text(encoding="utf-8")


def test_legacy_trial_extraction_alias_audit_script_preserves_historical_snapshots_when_including_generated(tmp_path):
    workspace = tmp_path / "workspace"
    snapshot_dir = workspace / "storage" / "artifacts" / "paper-1" / "run-1" / "snapshots"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "config.yaml").write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_legacy_trial_extraction_alias.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace), "--include-generated"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["offender_count"] == 0
    assert payload["preserved_historical_snapshot_count"] == 1
    assert payload["preserved_historical_snapshots"] == ["storage/artifacts/paper-1/run-1/snapshots/config.yaml"]


def test_legacy_trial_extraction_alias_migration_script_preserves_historical_snapshots_by_default(tmp_path):
    workspace = tmp_path / "workspace"
    snapshot_dir = workspace / "storage" / "artifacts" / "paper-1" / "run-1" / "snapshots"
    snapshot_dir.mkdir(parents=True)
    snapshot_config = snapshot_dir / "config.yaml"
    snapshot_config.write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "migrate_legacy_trial_extraction_alias.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--root", str(workspace), "--include-generated", "--apply"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["rewritten_count"] == 0
    assert payload["preserved_historical_snapshot_count"] == 1
    assert payload["preserved_historical_snapshots"] == ["storage/artifacts/paper-1/run-1/snapshots/config.yaml"]
    assert "trial_extraction:" in snapshot_config.read_text(encoding="utf-8")


def test_legacy_trial_extraction_alias_migration_script_can_rewrite_historical_snapshots_with_explicit_override(tmp_path):
    workspace = tmp_path / "workspace"
    snapshot_dir = workspace / "storage" / "artifacts" / "paper-1" / "run-1" / "snapshots"
    snapshot_dir.mkdir(parents=True)
    snapshot_config = snapshot_dir / "config.yaml"
    snapshot_config.write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "migrate_legacy_trial_extraction_alias.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--root",
            str(workspace),
            "--include-generated",
            "--include-historical-snapshots",
            "--apply",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    updated = snapshot_config.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert payload["rewritten_count"] == 1
    assert payload["rewritten_files"] == ["storage/artifacts/paper-1/run-1/snapshots/config.yaml"]
    assert payload["preserved_historical_snapshot_count"] == 0
    assert "specialty_trial_extraction:" in updated
    assert "\n    trial_extraction:" not in f"\n{updated}"


def test_legacy_trial_extraction_alias_sweep_script_audits_sibling_paperpipe_roots(tmp_path):
    base_dir = tmp_path / "roots"
    target_a = base_dir / "paperpipe-a"
    target_b = base_dir / "paperpipe-b"
    other = base_dir / "not-paperpipe"
    target_a.mkdir(parents=True)
    target_b.mkdir(parents=True)
    other.mkdir(parents=True)
    (target_a / "config.example.yaml").write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )
    (target_b / "config.example.yaml").write_text(
        """
llm:
  features:
    specialty_trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )
    (other / "config.example.yaml").write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "sweep_legacy_trial_extraction_aliases.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--base-dir", str(base_dir)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["root_count"] == 2
    roots = {Path(item["root"]).name: item for item in payload["roots"]}
    assert set(roots) == {"paperpipe-a", "paperpipe-b"}
    assert roots["paperpipe-a"]["audit"]["offender_count"] == 1
    assert roots["paperpipe-b"]["audit"]["offender_count"] == 0


def test_legacy_trial_extraction_alias_sweep_script_can_apply_to_sibling_paperpipe_roots(tmp_path):
    base_dir = tmp_path / "roots"
    target = base_dir / "paperpipe-a"
    target.mkdir(parents=True)
    config_path = target / "config.example.yaml"
    config_path.write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "sweep_legacy_trial_extraction_aliases.py"

    result = subprocess.run(
        [sys.executable, str(script_path), "--base-dir", str(base_dir), "--apply"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    updated = config_path.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert payload["root_count"] == 1
    root_payload = payload["roots"][0]
    assert root_payload["migrate"]["rewritten_files"] == ["config.example.yaml"]
    assert root_payload["audit"]["offender_count"] == 0
    assert "specialty_trial_extraction:" in updated


def test_legacy_trial_extraction_alias_removal_readiness_reports_clean_but_window_closed(tmp_path):
    base_dir = tmp_path / "roots"
    current_root = base_dir / "current-repo"
    sibling_root = base_dir / "paperpipe-a"
    current_root.mkdir(parents=True)
    sibling_root.mkdir(parents=True)
    (current_root / "config.yaml").write_text(
        """
llm:
  features:
    specialty_trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )
    (sibling_root / "config.example.yaml").write_text(
        """
llm:
  features:
    specialty_trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_legacy_trial_extraction_removal_readiness.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--current-root",
            str(current_root),
            "--base-dir",
            str(base_dir),
            "--today",
            "2026-03-28",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["active_surface_ready"] is True
    assert payload["removal_window_open"] is False
    assert payload["ready_to_remove_alias_now"] is False
    assert payload["current_repo"]["offender_count"] == 0
    assert payload["sibling_sweep"]["root_count"] == 1


def test_legacy_trial_extraction_alias_removal_readiness_flags_active_blockers(tmp_path):
    base_dir = tmp_path / "roots"
    current_root = base_dir / "current-repo"
    sibling_root = base_dir / "paperpipe-a"
    current_root.mkdir(parents=True)
    sibling_root.mkdir(parents=True)
    (current_root / "config.yaml").write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )
    (sibling_root / "config.example.yaml").write_text(
        """
llm:
  features:
    trial_extraction:
      enabled: false
""".strip(),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check_legacy_trial_extraction_removal_readiness.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--current-root",
            str(current_root),
            "--base-dir",
            str(base_dir),
            "--today",
            "2026-07-01",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["active_surface_ready"] is False
    assert payload["removal_window_open"] is True
    assert payload["ready_to_remove_alias_now"] is False
    assert payload["current_repo"]["offender_count"] == 1
    assert payload["sibling_blocker_roots"] == [str(sibling_root.resolve())]


def test_cli_workflow_falls_back_from_docling_and_reports_reader_timeout(monkeypatch, tmp_path):
    import src.services.cli_workflows as workflows

    pdf_path = tmp_path / "paper_docling.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    config = SimpleNamespace(
        agents=SimpleNamespace(enabled=True, main_model="mock-reader"),
        llm=SimpleNamespace(timeout_seconds=15),
        ingest=SimpleNamespace(
            parser_backend="docling",
            enable_docling=False,
            enable_ocr_fallback=False,
            ocr_lang="eng",
            ocr_min_text_chars=200,
            enable_table_pass2_ocr=False,
            enable_cloud_table_fallback=False,
            cloud_table_page_budget=2,
            cloud_table_model="gpt-4o-mini",
            cloud_table_base_url=None,
            cloud_table_api_key=None,
            cloud_table_timeout_seconds=30,
        ),
        paths=SimpleNamespace(
            library_dir=tmp_path,
            obsidian_vault=tmp_path,
            index_all="missing.csv",
        ),
    )

    ingest_calls: dict[str, object] = {}

    class FakeIngestAgent:
        def __init__(self, **kwargs):
            ingest_calls.update(kwargs)

        def process_v2(self, _path: str):
            return SimpleNamespace(
                pages=[object(), object(), object()],
                tables=[object()],
                meta=SimpleNamespace(title="Mock Paper"),
            )

    class FakeIndexerAgent:
        def __init__(self, **_kwargs):
            pass

        def process(self, _doc):
            return SimpleNamespace(chunk_count=3)

    class FakeReaderAgent:
        def __init__(self, **_kwargs):
            self.model_name = "mock-reader"

        def analyze(self, _doc):
            raise StepTimeoutError("step_timeout:99s")

    class FakeFeedbackRetriever:
        def query_relevant_feedback(self, *_args, **_kwargs):
            return []

    monkeypatch.setattr(workflows, "load_config", lambda: config)
    monkeypatch.setattr(
        workflows,
        "get_paper_by_id",
        lambda _identifier: {"local_path": str(pdf_path), "pdf_path": str(pdf_path)},
    )
    monkeypatch.setattr(workflows, "default_reader_timeout_base_seconds", lambda _llm_timeout: 90)
    monkeypatch.setattr(workflows, "estimate_reader_timeout_seconds", lambda *_args, **_kwargs: 123)
    monkeypatch.setattr(workflows, "time_limit", lambda _seconds: nullcontext())

    fake_ingest_module = types.ModuleType("src.agents.ingest_agent")
    fake_ingest_module.IngestAgent = FakeIngestAgent
    fake_indexer_module = types.ModuleType("src.agents.indexer_agent")
    fake_indexer_module.IndexerAgent = FakeIndexerAgent
    fake_reader_module = types.ModuleType("src.agents.reader_agent")
    fake_reader_module.ReaderAgent = FakeReaderAgent
    fake_feedback_module = types.ModuleType("src.agents.feedback_retriever")
    fake_feedback_module.FeedbackRetriever = FakeFeedbackRetriever

    monkeypatch.setitem(sys.modules, "src.agents.ingest_agent", fake_ingest_module)
    monkeypatch.setitem(sys.modules, "src.agents.indexer_agent", fake_indexer_module)
    monkeypatch.setitem(sys.modules, "src.agents.reader_agent", fake_reader_module)
    monkeypatch.setitem(sys.modules, "src.agents.feedback_retriever", fake_feedback_module)

    console = Console(record=True, width=120)
    workflows.run_deepread_workflow("paper_docling", verify=False, console=console)

    output = console.export_text()
    assert ingest_calls["parser_backend"] == "fitz_pdfplumber"
    assert "Reader timeout after 123s" in output


def test_cli_workflow_reuses_bounded_clinical_extraction_block_for_clinical_notes(monkeypatch, tmp_path):
    import src.services.cli_workflows as workflows

    pdf_path = tmp_path / "paper_clinical_cli.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    note_path = tmp_path / "Inbox" / "paper_clinical_cli.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "---\n"
        "type: clinical_paper\n"
        "slot: clinical\n"
        "---\n\n"
        "# Paper\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "paper_collection.csv"
    index_path.write_text(
        "Paper_ID,DOI,Title,Note_Path\n"
        "paper_clinical_cli,10.1000/cli,Clinical CLI Note,Inbox/paper_clinical_cli.md\n",
        encoding="utf-8",
    )

    config = SimpleNamespace(
        agents=SimpleNamespace(enabled=True, main_model="mock-reader"),
        llm=SimpleNamespace(
            timeout_seconds=15,
            features=SimpleNamespace(specialty_trial_extraction=SimpleNamespace(enabled=True)),
        ),
        ingest=SimpleNamespace(
            parser_backend="fitz_pdfplumber",
            enable_docling=False,
            enable_ocr_fallback=False,
            ocr_lang="eng",
            ocr_min_text_chars=200,
            enable_table_pass2_ocr=False,
            enable_cloud_table_fallback=False,
            cloud_table_page_budget=2,
            cloud_table_model="gpt-4o-mini",
            cloud_table_base_url=None,
            cloud_table_api_key=None,
            cloud_table_timeout_seconds=30,
        ),
        paths=SimpleNamespace(
            library_dir=tmp_path,
            obsidian_vault=tmp_path,
            index_all="paper_collection.csv",
        ),
        entity_aliases={},
    )

    class FakeIngestAgent:
        def __init__(self, **_kwargs):
            pass

        def process_v2(self, _path: str):
            return DocumentArtifactV2(
                document_id="paper_clinical_cli",
                meta=ArtifactMetaV2(title="Clinical CLI Note", authors=["Kim"], source_ref=str(pdf_path)),
                pages=[
                    PageV2(
                        page_index=0,
                        width=595.0,
                        height=842.0,
                        blocks=[
                            BlockV2(
                                block_id="b1",
                                lines=[
                                    LineV2(
                                        line_id="l1",
                                        text="Clinical abstract text describing an ulcerative colitis trial.",
                                        spans=[SpanV2(span_id="s1", text="Clinical abstract text describing an ulcerative colitis trial.")],
                                    )
                                ],
                            )
                        ],
                    )
                ],
                tables=[],
            )

    class FakeIndexerAgent:
        def __init__(self, **_kwargs):
            pass

        def process(self, _doc):
            return SimpleNamespace(chunk_count=1)

    class FakeReaderAgent:
        def __init__(self, **_kwargs):
            self.model_name = "mock-reader"

        def analyze(self, _doc):
            return ClaimSet(
                doc_id="paper_clinical_cli",
                claims=[
                    ScientificClaim(
                        claim_id="c1",
                        type="efficacy",
                        statement="The therapy improved remission rates.",
                        confidence=0.91,
                    )
                ],
            )

    class FakeFeedbackRetriever:
        def query_relevant_feedback(self, *_args, **_kwargs):
            return []

    class FakeProvider:
        def is_available(self):
            return True

        def extract_biomedical_clinical_data(self, _paper_payload, _methods_snippet=""):
            return BiomedicalClinicalExtraction(
                paper_id="paper_clinical_cli",
                citation={
                    "title": "Clinical CLI Note",
                    "authors_first": "Kim",
                    "year": 2026,
                    "journal_or_server": "Clinical Journal",
                    "doi": None,
                    "url": None,
                },
                population={"condition": "Ulcerative colitis", "n_total": 48},
                intervention={"category": "biologic", "name": "Monoclonal antibody"},
                outcomes={"primary": [{"name": "Clinical remission", "domain": "primary"}]},
                eligibility_flags={"followup_tag": "therapeutic"},
            )

    provider_calls = {"count": 0}

    def _fake_get_llm_provider(*_args, **_kwargs):
        provider_calls["count"] += 1
        return FakeProvider()

    monkeypatch.setattr(workflows, "load_config", lambda: config)
    monkeypatch.setattr(
        workflows,
        "get_paper_by_id",
        lambda _identifier: {"local_path": str(pdf_path), "pdf_path": str(pdf_path)},
    )
    monkeypatch.setattr(workflows, "time_limit", lambda _seconds: nullcontext())
    monkeypatch.setattr(workflows, "get_llm_provider", _fake_get_llm_provider)

    fake_ingest_module = types.ModuleType("src.agents.ingest_agent")
    fake_ingest_module.IngestAgent = FakeIngestAgent
    fake_indexer_module = types.ModuleType("src.agents.indexer_agent")
    fake_indexer_module.IndexerAgent = FakeIndexerAgent
    fake_reader_module = types.ModuleType("src.agents.reader_agent")
    fake_reader_module.ReaderAgent = FakeReaderAgent
    fake_feedback_module = types.ModuleType("src.agents.feedback_retriever")
    fake_feedback_module.FeedbackRetriever = FakeFeedbackRetriever

    monkeypatch.setitem(sys.modules, "src.agents.ingest_agent", fake_ingest_module)
    monkeypatch.setitem(sys.modules, "src.agents.indexer_agent", fake_indexer_module)
    monkeypatch.setitem(sys.modules, "src.agents.reader_agent", fake_reader_module)
    monkeypatch.setitem(sys.modules, "src.agents.feedback_retriever", fake_feedback_module)

    console = Console(record=True, width=120)
    workflows.run_deepread_workflow("paper_clinical_cli", verify=False, console=console)

    note_text = note_path.read_text(encoding="utf-8")
    output = console.export_text()
    assert provider_calls["count"] == 1
    assert "Clinical extraction summary prepared." in output
    assert "## 🤖 Agent Deep Read" in note_text
    assert "### 🏥 Clinical Extraction" in note_text
    assert "Ulcerative colitis, n=48" in note_text
    assert "Monoclonal antibody, Biologic" in note_text


def test_cli_workflow_keeps_main_deepread_on_reader_agent_lane_for_nonclinical_notes(monkeypatch, tmp_path):
    import src.services.cli_workflows as workflows

    pdf_path = tmp_path / "paper_mechanism_cli.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    note_path = tmp_path / "Inbox" / "paper_mechanism_cli.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "---\n"
        "type: mechanism_paper\n"
        "slot: mechanism\n"
        "---\n\n"
        "# Paper\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "paper_collection.csv"
    index_path.write_text(
        "Paper_ID,DOI,Title,Note_Path\n"
        "paper_mechanism_cli,10.1000/mech,Mechanism CLI Note,Inbox/paper_mechanism_cli.md\n",
        encoding="utf-8",
    )

    config = SimpleNamespace(
        agents=SimpleNamespace(enabled=True, main_model="mock-reader"),
        llm=SimpleNamespace(
            timeout_seconds=15,
            features=SimpleNamespace(specialty_trial_extraction=SimpleNamespace(enabled=True)),
        ),
        ingest=SimpleNamespace(
            parser_backend="fitz_pdfplumber",
            enable_docling=False,
            enable_ocr_fallback=False,
            ocr_lang="eng",
            ocr_min_text_chars=200,
            enable_table_pass2_ocr=False,
            enable_cloud_table_fallback=False,
            cloud_table_page_budget=2,
            cloud_table_model="gpt-4o-mini",
            cloud_table_base_url=None,
            cloud_table_api_key=None,
            cloud_table_timeout_seconds=30,
        ),
        paths=SimpleNamespace(
            library_dir=tmp_path,
            obsidian_vault=tmp_path,
            index_all="paper_collection.csv",
        ),
        entity_aliases={},
    )

    class FakeIngestAgent:
        def __init__(self, **_kwargs):
            pass

        def process_v2(self, _path: str):
            return DocumentArtifactV2(
                document_id="paper_mechanism_cli",
                meta=ArtifactMetaV2(title="Mechanism CLI Note", authors=["Kim"], source_ref=str(pdf_path)),
                pages=[
                    PageV2(
                        page_index=0,
                        width=595.0,
                        height=842.0,
                        blocks=[
                            BlockV2(
                                block_id="b1",
                                lines=[
                                    LineV2(
                                        line_id="l1",
                                        text="Mechanistic results showed pathway inhibition after treatment.",
                                        spans=[SpanV2(span_id="s1", text="Mechanistic results showed pathway inhibition after treatment.")],
                                    )
                                ],
                            )
                        ],
                    )
                ],
                tables=[],
            )

    class FakeIndexerAgent:
        def __init__(self, **_kwargs):
            pass

        def process(self, _doc):
            return SimpleNamespace(chunk_count=1)

    class FakeReaderAgent:
        def __init__(self, **_kwargs):
            self.model_name = "mock-reader"

        def analyze(self, _doc):
            return ClaimSet(
                doc_id="paper_mechanism_cli",
                claims=[
                    ScientificClaim(
                        claim_id="c1",
                        type="mechanism",
                        statement="The intervention suppressed the target pathway.",
                        confidence=0.88,
                    )
                ],
            )

    class FakeFeedbackRetriever:
        def query_relevant_feedback(self, *_args, **_kwargs):
            return []

    provider_calls = {"count": 0}

    def _unexpected_get_llm_provider(*_args, **_kwargs):
        provider_calls["count"] += 1
        raise AssertionError("main deep-read workflow should stay on ReaderAgent for non-clinical notes")

    monkeypatch.setattr(workflows, "load_config", lambda: config)
    monkeypatch.setattr(
        workflows,
        "get_paper_by_id",
        lambda _identifier: {"local_path": str(pdf_path), "pdf_path": str(pdf_path)},
    )
    monkeypatch.setattr(workflows, "time_limit", lambda _seconds: nullcontext())
    monkeypatch.setattr(workflows, "get_llm_provider", _unexpected_get_llm_provider)

    fake_ingest_module = types.ModuleType("src.agents.ingest_agent")
    fake_ingest_module.IngestAgent = FakeIngestAgent
    fake_indexer_module = types.ModuleType("src.agents.indexer_agent")
    fake_indexer_module.IndexerAgent = FakeIndexerAgent
    fake_reader_module = types.ModuleType("src.agents.reader_agent")
    fake_reader_module.ReaderAgent = FakeReaderAgent
    fake_feedback_module = types.ModuleType("src.agents.feedback_retriever")
    fake_feedback_module.FeedbackRetriever = FakeFeedbackRetriever

    monkeypatch.setitem(sys.modules, "src.agents.ingest_agent", fake_ingest_module)
    monkeypatch.setitem(sys.modules, "src.agents.indexer_agent", fake_indexer_module)
    monkeypatch.setitem(sys.modules, "src.agents.reader_agent", fake_reader_module)
    monkeypatch.setitem(sys.modules, "src.agents.feedback_retriever", fake_feedback_module)

    console = Console(record=True, width=120)
    workflows.run_deepread_workflow("paper_mechanism_cli", verify=False, console=console)

    note_text = note_path.read_text(encoding="utf-8")
    assert provider_calls["count"] == 0
    assert "## 🤖 Agent Deep Read" in note_text
    assert "The intervention suppressed the target pathway." in note_text
    assert "### 🏥 Clinical Extraction" not in note_text
