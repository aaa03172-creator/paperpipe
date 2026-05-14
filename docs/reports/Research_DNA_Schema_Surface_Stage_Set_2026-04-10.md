# Research DNA Progress Read Surface Stage Set

Date: 2026-04-10
Owner: Codex
Status: staged-slice-prep

## Intent

Isolate the Research DNA read/progress surface required by the already-added API and CLI entry points.

## Included scope

- `src/schemas/research_dna.py`
  - import `ResearchDNAScreeningGuidanceIndexArtifact`
  - import `ResearchDNAScreeningProgressReport`
  - add `ResearchDNAScreeningGuidanceIndexEnvelope`
  - add `ResearchDNAScreeningProgressEnvelope`
- `src/profiles/research_dna_schema.py`
  - add `ResearchDNAScreeningProgressReport`
  - add `ResearchDNAScreeningGuidanceFollowSummary`
  - add the guidance/progress fields already referenced by the current Research DNA session/progress flow
- `src/profiles/research_dna_service.py`
  - add loading for latest guidance artifact and guidance history index
  - add screening progress report construction
  - persist guidance-follow telemetry into screening log entries and run-local sidecars
- `src/cli.py`
  - add `research-dna progress`
  - preserve nullable `next_candidate_id` in the CLI payload for completed sessions

## Explicitly excluded

- backend route changes
- unrelated CLI commands
- service-layer logic changes

## Why this is a valid standalone lane

- the missing schema/service surfaces are already referenced by runtime imports and tests
- the lane restores API/CLI/runtime alignment for Research DNA guidance and progress reads
- the CLI payload fix preserves a tested nullable contract instead of changing semantics

## Verification plan

- clean index-export import check: `python3 -c "import backend.main"`
- `pytest -q tests/test_research_dna_api.py::test_research_dna_api_roundtrip_and_pilot tests/test_research_dna_cli.py::test_research_dna_cli_roundtrip`
- `python3 scripts/lint_docs.py`

## Verification results

- current worktree:
  - `pytest -q tests/test_research_dna_api.py::test_research_dna_api_roundtrip_and_pilot tests/test_research_dna_cli.py::test_research_dna_cli_roundtrip`
    - `2 passed, 5 warnings`
  - `python3 scripts/lint_docs.py`
    - `docs lint passed`
- staged index export:
  - `backend.main` import progressed past the earlier Research DNA schema/service gaps
  - clean staged verification is still blocked by a pre-existing `src/cli.py` to `src.services.runtime_readiness` import drift outside this lane
  - when a temporary `config.yaml` is provided, the next blocker is:
    - `ImportError: cannot import name 'collect_structured_state_hygiene_check' from 'src.services.runtime_readiness'`
