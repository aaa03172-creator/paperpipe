# Codex Next Actions (2026-02-17)

## Current Completed Work
- PR#1 code prepared on branch `codex/pr1-indexer-only`
  - commit: `fe10f70`
  - files:
    - `src/indexer.py`
    - `tests/test_indexer.py`
  - test: `.venv/bin/python -m pytest -q tests/test_indexer.py` (3 passed)

- PR#2 code prepared on branch `codex/pr2-exporter-deeplinks`
  - commit: `d86aa9b`
  - files:
    - `src/exporter.py`
    - `tests/test_exporter.py`
    - `tests/fixtures/exporter_with_links_example.md`
  - test: `.venv/bin/python -m pytest -q tests/test_exporter.py` (4 passed)

## Blocker
- Network/DNS blocked in this environment:
  - `Could not resolve host: github.com`
- As a result, push/PR creation from here is blocked.

## Immediate Next Steps (when network is available)
1. Push PR#1 branch
   - `git push -u origin codex/pr1-indexer-only`
2. Push PR#2 branch
   - `git push -u origin codex/pr2-exporter-deeplinks`
3. Open PR#1 (base: master)
4. Open PR#2 (base: master)

## After Merge
1. Re-check main tests:
   - `.venv/bin/python -m pytest -q tests/test_indexer.py tests/test_exporter.py`
2. Then handle deferred ops ticket:
   - hansson FAILED retry path (Ollama/OpenAI connectivity restored)
