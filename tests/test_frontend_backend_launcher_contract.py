from __future__ import annotations

import re
from pathlib import Path


def test_frontend_e2e_backend_launcher_template_uses_specialty_trial_extraction() -> None:
    script_path = Path("frontend/scripts/run_backend_for_e2e.sh").resolve()

    content = script_path.read_text(encoding="utf-8")

    assert "specialty_trial_extraction:" in content
    legacy_key_pattern = re.compile(r"(?m)^\\s*trial" r"_extraction:")
    assert legacy_key_pattern.search(content) is None


def test_frontend_e2e_backend_launcher_anchors_runtime_paths_to_repo_root() -> None:
    script_path = Path("frontend/scripts/run_backend_for_e2e.sh").resolve()

    content = script_path.read_text(encoding="utf-8")

    assert 'E2E_RUNTIME_DIR="${REPO_ROOT}/frontend/.e2e-backend-runtime"' in content
    assert 'E2E_VAULT_PATH="${E2E_RUNTIME_DIR}/obsidian"' in content
    assert 'export PAPERPIPE_CONFIG_PATH="${E2E_CONFIG_PATH}"' in content
    assert 'export PAPERPIPE_DB_PATH="${E2E_DB_PATH}"' in content
    assert 'obsidian_vault: "${E2E_VAULT_PATH}"' in content
    assert 'pdf_storage_dir: "${E2E_PDF_STORAGE_PATH}"' in content
    assert "./frontend/.e2e-backend-runtime/" not in content
