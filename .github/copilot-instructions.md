# Copilot / AI Agent Instructions for paperpipe

Purpose: Help AI coding agents be immediately productive in the repository by describing the architecture, essential workflows, conventions, integration points, and known gotchas.

## Quick snapshot (what this project does) ✅
- Paper discovery and daily processing pipeline that fetches papers (PubMed, ArXiv), selects one per "slot" (mechanism, clinical, methods), optionally runs LLM-powered extraction/summary, writes Obsidian notes, and records state in a SQLite DB.
- Key entrypoints: `src/main.py` (Typer CLI) and `src/processor.py` (pipeline implementation).

## Quickstart — developer commands ⚙️
- Install dependencies: `python -m pip install -e .` (pyproject.toml lists runtime deps).
- Config: edit `config.yaml`. The loader in `src/config.py` defines the actual shape; prefer checking that file when in doubt.
- Required env var: `OPENAI_API_KEY` (used by `src/config.load_config()` — it overrides any file-based key).
- Run the CLI: `python -m src.main doctor|test_fetch|process_test`
  - `doctor` checks config and DB.
  - `test_fetch` runs simple fetchers (PubMed/ArXiv).
  - `process_test` runs `process_daily_slots()` and prints a short report.

## Important files to inspect 📁
- `src/config.py` — authoritative configuration schema and how API keys are loaded.
- `config.yaml` — example config & search slot definitions; note that the file may contain legacy keys/comments.
- `src/processor.py` — core pipeline (search -> select -> LLM extraction -> save to Obsidian -> DB save).
- `src/llm_provider.py` — LLM interface and concrete OpenAI provider implementation; central place to add other providers.
- `src/schemas.py` — Pydantic models (especially `TrialExtraction`) used to validate and render structured extraction output.
- `src/obsidian.py` — templates for Obsidian notes and CSV indexing logic.
- `src/db.py` — lightweight SQLite helpers; DB is `state.db` by default.

## Project-specific patterns & conventions 🔍
- Search slots: `config.search.slots` contains named slots (e.g., `mechanism`, `clinical`, `methods`). The pipeline expects these keys and sets `paper['slot'] = slot_name`.
- LLM interaction:
  - Extraction aims to return strict JSON matching `TrialExtraction` (see `src/schemas.py`). Agents should **preserve the exact JSON-only instruction** style.
  - There are two places where LLMs are invoked: helper class in `src/llm_provider.py` (recommended to use) and a direct call in `processor.extract_trial_data()` (historical/explicit implementation).
- Error handling for LLM responses: pipeline attempts a JSON parse, then a correction prompt retry, then pydantic validation; failed validations often result in downgraded `extraction_quality`.
- Obsidian note creation: written to `<obsidian_vault>/Inbox/<YYYY-MM-DD>/` with a sanitized filename; templates are in `src/obsidian.py`.
- CSV indexing: `00_Index/paper_collection.csv` (path from `config.yaml`) — the project writes a single index CSV and uses the `slot` column to differentiate clinical vs others.

## Known gotchas & important implementation notes ⚠️
- Slot name mismatch (critical): `processor.py` sets `paper['slot'] = 'clinical'` (lowercase) for the clinical slot, and the rest of the code checks for `'clinical'`. However, `src/obsidian.py` currently checks `if paper.get('slot') == 'Clinical'` (capitalized) to decide which template to use. This will prevent clinical `TrialExtraction` data from being embedded into the clinical template. When editing, prefer using lowercase `'clinical'` (or normalize `paper['slot'].lower()` in `obsidian.py`).
- Config schema drift: `config.yaml` contains convenience keys and comments (e.g., `model_override`, `enable_trial_extraction`) while `src/config.py` declares the authoritative pydantic model shape. When adding features, update the pydantic models in `src/config.py` accordingly.
- LLM API key handling: `src/config.load_config()` prioritizes `OPENAI_API_KEY`. Do not store the key in `config.yaml` in the repository.
- Database and logs are created relative to the working directory (DB `state.db` and log `logs/paperpipe.log`). For tests or CI, use temp paths or a temporary working directory.

## Common changes and where to implement them 🔧
- Add a new search slot: edit `config.yaml` -> `search.slots` and ensure any code that reads slot keys is case-consistent (all lower-case preferred).
- Add a new LLM provider: extend `LLMProvider` in `src/llm_provider.py` and update `get_llm_provider()` to return your provider when `config.llm.provider` matches.
- Change extraction model or parameters: update `src/config.py` / `config.yaml` model names, then check usage in `llm_provider._get_model()` and `processor.extract_trial_data()`.
- Improve note templates: edit `src/obsidian.py` — templates are simple f-strings and should produce valid Markdown/Obsidian frontmatter.

## Debugging tips 🐞
- Check `logs/paperpipe.log` for runtime info (configured in `src/main.py`).
- Inspect `state.db` using `sqlite3 state.db` to check `runs` and `papers` tables.
- If LLM JSON parsing fails often, inspect the actual `raw` assistant content returned (search logs in llm provider or add temporary prints) and validate against `TrialExtraction.model_json_schema()`.

## Tests / CI
- There are no unit tests in the repo currently. Prefer adding small unit tests for:
  - JSON extraction/validation with `TrialExtraction` (edge cases, missing fields)
  - `save_paper_to_obsidian` template rendering and filename generation
  - `processor.process_daily_slots` slot selection (with mocked network/LLM calls)

---
If anything is unclear or you want these instructions to include a suggested code patch (e.g., the slot-name mismatch fix), say so and I can open a PR with the change and unit tests. 🙋‍♂️
