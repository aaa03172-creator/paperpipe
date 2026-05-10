from pathlib import Path
import re


ALIAS_PATTERN = re.compile(r"(?<!specialty_)trial_extraction\b")

# Allowed remaining surfaces:
# - runtime compatibility layer and specialty task owner
# - explicit backward-compat tests
# - specialty-lane regression fixtures/tests
# - shipped config/spec migration notes
ALLOWED = {
    "src/legacy_trial_extraction_constants.py",
    "src/config.py",
    "src/llm_provider.py",
    "scripts/check_legacy_trial_extraction_alias.py",
    "scripts/check_legacy_trial_extraction_removal_readiness.py",
    "scripts/migrate_legacy_trial_extraction_alias.py",
    "scripts/sweep_legacy_trial_extraction_aliases.py",
    "scripts/eval/compare_extraction_outputs.py",
    "tests/test_config_env_override.py",
    "tests/test_llm_provider_task_temperature.py",
    "tests/test_llm_provider_canonical_language.py",
    "tests/test_extraction_regression_eval.py",
    "tests/test_obsidian_institutional_block.py",
    "tests/test_runtime_shell_scripts.py",
    "tests/test_shipped_biomedical_defaults.py",
    "tests/test_no_new_trial_extraction_alias.py",
    "config.yaml",
    "config.example.yaml",
    "docs/Lattice_v3_Master_Spec.md",
}

SKIP_PREFIXES = (
    ".codex/",
    "build/",
    "dist/",
    "docs/reports/",
    "storage/",
    "frontend/.e2e-backend-runtime/",
    "tests/fixtures/",
)

TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml"}


def test_no_new_trial_extraction_alias_outside_allowlist() -> None:
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if rel in ALLOWED or any(rel.startswith(prefix) for prefix in SKIP_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if ALIAS_PATTERN.search(text):
            offenders.append(rel)

    assert not offenders, f"Deprecated trial_extraction alias should not spread outside allowlist. Offenders: {offenders}"
