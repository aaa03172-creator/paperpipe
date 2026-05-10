#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

RESOLVER_RUNNER="$(command -v python3 || command -v python)"
if [[ -z "${RESOLVER_RUNNER}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi

PYTHON_BIN="$("${RESOLVER_RUNNER}" "${ROOT_DIR}/scripts/resolve_verification_python.py" --require-module pytest)"

FIRST_PAPER_TARGETS=(
  tests/test_readme_first_paper_smoke.py
  tests/test_cli_import_pdf.py
  tests/test_cli_watch_commands.py
  tests/test_paper_notes_api.py
)

"${PYTHON_BIN}" -m pytest -q "${FIRST_PAPER_TARGETS[@]}" -k "first_paper or import_pdf or doctor or demo_first_paper"
