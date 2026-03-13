#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v ruff >/dev/null 2>&1; then
  echo "ruff is required. Install it with: python3 -m pip install ruff" >&2
  exit 127
fi

RUFF_TARGETS=(
  src/agents/adapter.py
  src/agents/deep_reader.py
  src/agents/profile_chat_agent.py
  src/agents/stats_agent.py
  tests/test_deep_reader.py
  tests/test_profile_chat.py
  tests/test_librarian_advanced.py
  tests/test_stats_agent.py
  tests/test_stats_agent_output_parse.py
  tests/test_stats_agent_no_table.py
  tests/test_stats_agent_fallback.py
)

PYTEST_TARGETS=(
  tests/test_deep_reader.py
  tests/test_profile_chat.py
  tests/test_librarian_advanced.py
  tests/test_stats_agent.py
  tests/test_stats_agent_output_parse.py
  tests/test_stats_agent_no_table.py
  tests/test_stats_agent_fallback.py
)

ruff check "${RUFF_TARGETS[@]}" --select F,E701,E9,F541
pytest -q "${PYTEST_TARGETS[@]}"
