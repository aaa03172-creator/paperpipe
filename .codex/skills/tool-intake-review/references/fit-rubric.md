# Fit Rubric

## Current Bottleneck

Write one short sentence first:
- what is failing or missing today
- where that behavior currently lives
- why the external tool is being considered

If you cannot point to a real bottleneck, default toward `defer`.

## Classification Rules

### `direct candidate`
Use only when all are true:
- the candidate addresses a real current bottleneck
- it can be inserted additively
- it does not require a first-step rewrite of parser, storage, orchestration, or output contracts
- operational complexity is acceptable

### `reference only`
Use when:
- the ideas are useful but the runtime overlap is high
- local implementation should remain the primary path
- the tool is best used for patterns, eval ideas, prompt structure, or implementation hints

### `dataset only`
Use when:
- the data, benchmarks, fixtures, or examples are valuable
- the runtime code is not a good fit

### `defer`
Use when:
- the bottleneck is weak or speculative
- the candidate introduces migration risk, lock-in, licensing issues, or dependency sprawl
- the insertion point is unclear or unsafe

## Safest Insertion Point Checklist

Prefer, in order:
1. evaluation harness or benchmark fixture
2. sidecar artifact generator
3. optional route, admin path, or explicit tool action
4. behind-flag runtime pilot

Avoid recommending:
- full subsystem replacement
- storage migration as intake work
- schema replacement without a specific adopted RFC

## Protected PaperPipe Areas

Be cautious around:
- FastAPI API surface
- `src/schemas/` contracts
- `src/db_utils.py` runtime DB/state behavior
- parser/retrieval/extraction/grounding ownership in `src/agents/`, `src/ingest/`, and `src/services/`
- idempotent note/export behavior
- skills policy boundaries in `config/skills_policy.yaml` and `src/skills/`

## Risk Categories

Always consider:
- contract risk
- migration risk
- dependency or ops risk
- license or policy risk
- user-facing regression risk
