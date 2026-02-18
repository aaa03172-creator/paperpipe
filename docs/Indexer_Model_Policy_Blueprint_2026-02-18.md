# Indexer Model Policy Blueprint (2026-02-18)

## 1) Current Snapshot (as-is)
- Branch/HEAD: `master` @ `d61cdd2`
- `src/indexer.py` default model is currently `NeuML/pubmedbert-base-embeddings` (working tree policy realignment).
- Collection versioning is implemented via `--version` and `paper_pipe_bio__{model_slug}__v{N}`.
- Existing indexer tests: `tests/test_indexer.py` (expanded policy tests).

## 2) Why Old Prompt Is Outdated
The previously drafted prompt assumed a greenfield indexer build and a frozen default of `NeuML/pubmedbert-base-embeddings`.
Current repo already has:
- implemented indexer
- merged model default switch to BAAI
- active Phase 3/4 architecture and frontend integrations

So the correct task is **policy realignment + controlled rollout**, not new implementation from scratch.

## 3) Goal (state-aware)
Create a stable, auditable policy for biomedical embedding defaults without breaking current operations.

Primary goals:
1. Preserve production safety (versioned collections, rollback path).
2. Make default-model policy explicit and testable.
3. Keep licensing/performance constraints documented.

## 4) Decision Surface
We need one explicit decision for default model policy:
- Option A: Keep default = `BAAI/bge-small-en` (current behavior)
- Option B: Revert default = `NeuML/pubmedbert-base-embeddings` (PDF-driven biomedical priority)

Non-default options remain available through `--model` either way.

## 5) Codex Execution Plan (I will implement)

### Phase A — Policy Codification (safe, no behavior change)
Scope:
- `docs/indexer.md` (new)
- `docs/Indexer_Model_Policy_Blueprint_2026-02-18.md` (this file)
- `tests/test_indexer.py` (add policy assertions only)

Actions:
1. Add explicit policy section to docs:
- current default model
- allowed alternatives
- non-commercial model warning
- rollback commands
2. Add tests that verify:
- collection naming rule remains stable
- `--version` affects collection name correctly
- metadata includes `collection_version`

Acceptance:
- existing indexer tests pass + new policy tests pass

### Phase B — Default Model Switch (conditional)
Trigger: only after user confirms Option A or B.

Scope:
- `src/indexer.py` (default model constants in constructor + CLI)
- `docs/indexer.md` update

Actions:
1. Apply chosen default model in one place and keep constructor/CLI defaults consistent.
2. Keep rollback commands in docs for the opposite model.

Acceptance:
- `tests/test_indexer.py` pass
- smoke command examples in docs are executable

### Phase C — Post-switch Validation
1. Reindex candidate collection (`--version N`).
2. Run 10-query comparison report (`v1 vs vN`).
3. Record recommendation: keep/conditional-switch/switch.

## 6) Commands (baseline)
```bash
# Tests
.venv/bin/python -m pytest -q tests/test_indexer.py

# Index
python -m src.indexer --db state.db --model "<MODEL>" --version <N> index --all

# Search
python -m src.indexer --db state.db --model "<MODEL>" --version <N> search "<QUERY>" --k 5
```

## 7) Risks / Constraints
- SentenceTransformer model downloads are large; first run latency is expected.
- Evaluation quality is dataset-size sensitive; small corpora can overfit perceived gains.
- License-sensitive models must not be set as implicit default without policy approval.

## 8) Immediate Next Step
Start Phase A now (policy codification + test hardening), then request explicit Option A/B decision before Phase B.
