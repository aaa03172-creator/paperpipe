# M4 Local Optimization Audit

Status: Bounded implementation and rollout note
Date: 2026-06-11
Layer: review/gate artifact
Canonical: no

Related implementation anchors:
- `backend/services/job_runner.py`
- `src/services/performance_profile.py`
- `src/agents/adapter.py`
- `src/agents/indexer_agent.py`
- `src/config.py`
- `config.example.yaml`
- `tests/test_performance_profile.py`
- `tests/test_config_performance.py`
- `tests/test_indexer_agent_embedding_batch.py`
- `tests/test_worker_job_runner_chain.py`

## Host Profile

- Machine: Mac mini
- Chip: Apple M4
- CPU: 10 cores, reported as 4 performance cores and 6 efficiency cores
- GPU: 10-core integrated Apple GPU, Metal 4 capable
- Memory: 16 GB unified memory
- Display load observed during audit: one 4K display at 60 Hz

## Optimization Fit

The safest immediate optimization is measurement-first local acceleration, not a new heavyweight ML runtime. The current default dependency set does not include `torch`, `sentence-transformers`, or `transformers`, but `src/indexer.py` already supports a lazy SentenceTransformer path for local biomedical embeddings. That makes hardware-aware device selection a narrow change: it improves operators who have the optional stack installed while preserving CPU-only and minimal installs.

The Deep Read runtime also had a separate local bottleneck: `src/agents/indexer_agent.py` embedded chunks one at a time through Ollama, and `backend/services/job_runner.py` did not persist stage timing in a compact performance profile. The M4 host can benefit from batching and Metal-owned local model execution, but the next concurrency/GPU decisions should be driven by observed `run_meta.performance` data rather than static machine specs alone.

Inference payload class: `local_only`. The change does not widen external inference paths, send new excerpts to cloud providers, or alter persisted paper/artifact schemas.

## Implemented

### Local Biomedical Indexer Device Selection

- `src/indexer.py` now resolves the local embedding device from `--device`, `PAPERPIPE_INDEXER_DEVICE`, or auto detection.
- Auto detection uses Apple MPS only when `torch.backends.mps.is_available()` is true.
- `--device cpu`, `--device mps`, `--device cuda`, `--device cuda:0`, and `--device default` are supported without introducing new dependencies.
- If MPS initialization fails for a model, the indexer falls back to CPU instead of aborting the local indexing run.

### Deep Read Runtime Profiling

- `backend/services/job_runner.py` now writes additive `performance_profile.v1` metadata into `run_meta.performance`.
- The profile records stage timings for `ingest`, `index`, `reader`, and `verify` when those stages run.
- `bootstrap_meta.performance_summary` mirrors a compact summary for UI/API surfaces that only need totals.
- `src/services/performance_profile.py` owns the small `StageTimer` and `summarize_stage_timings` helpers.

### Ollama Embedding Batch Path

- `src/agents/adapter.py` now exposes `OllamaModelAdapter.embed_batch()`.
- The adapter uses Ollama's batch `embed` API when available and falls back to existing single embedding calls for older clients.
- `src/agents/indexer_agent.py` now builds chunk ids, metadata, documents, and `DocumentChunk` records first, then embeds document chunks as a batch before Chroma upsert.
- Deterministic `chunk_id`, `vector_id`, `last_index_attempted_chunks`, `last_index_skipped_chunks`, and clean reindex behavior are preserved.

### Performance Config Defaults

- `src/config.py` now has `PerformanceConfig`.
- `config.example.yaml` documents safe Apple Silicon defaults:
  - `embedding_batch_size: 16`
  - `reader_max_context_chars: 16000`
  - `max_concurrent_jobs: 1`
  - `local_gpu_backend: "ollama_metal"`
- `backend/services/job_runner.py` passes `reader_max_context_chars` into `ReaderAgent` and records it in run/bootstrap metadata.

## Why This Matches The M4

The M4 has a capable integrated GPU and unified memory, but only 16 GB total memory. Local embedding batches can benefit from MPS when the optional PyTorch/SentenceTransformer stack is present, and Ollama generally owns Metal acceleration for its local models. PaperPipe should therefore batch work and observe stage timings before increasing concurrency or adding heavier dependencies.

The current safe default is still `max_concurrent_jobs: 1`. Raising it before measuring Reader memory pressure, SQLite/artifact write contention, and same-paper duplicate behavior would create correctness risk for a local-first runtime.

## Consolidated Implementation Plan

The previous standalone `docs/superpowers/plans/2026-06-11-paperpipe-performance-optimization.md` has been folded into this report. Its implementation lane is now tracked here:

| Lane | Status | Notes |
| --- | --- | --- |
| Baseline profiling contract | implemented | Additive `run_meta.performance` and `bootstrap_meta.performance_summary`. |
| Local embedding batching | implemented | `OllamaModelAdapter.embed_batch()` plus batched `IndexerAgent.process()`. |
| Reader context cap config | implemented | `PerformanceConfig.reader_max_context_chars`, default `16000`. |
| Worker concurrency guard | deferred | Keep default `1`; revisit only after real stage timing runs. |
| GPU/MLX/PyTorch-MPS adoption | deferred | Keep behind local-only benchmark and dependency review. |

## Deferred Candidates

- Add a runtime-readiness probe that reports local embedding capability: optional `sentence-transformers`, `torch`, MPS availability, and current `PAPERPIPE_INDEXER_DEVICE`.
- Add an Ollama/local-model readiness panel or CLI report. Ollama usually owns Metal acceleration itself, so PaperPipe should detect availability rather than force GPU behavior.
- Evaluate bounded PDF ingest parallelism separately. M4 has enough CPU cores for some local extraction concurrency, but the current job queue, SQLite writes, and artifact writes need a dedicated failure-path review before raising concurrency defaults.
- Keep Docling/OCR GPU experiments behind explicit opt-in. They are heavier dependency surfaces and should not become default based only on this host profile.
- Run three representative Deep Read jobs, then compare `run_meta.performance.summary` for short, medium, and long PDFs before changing concurrency defaults.
- Adopt a GPU/ML backend only if it improves p50 Reader or Index time by at least 25% on the benchmark set without reducing claim grounding quality or increasing failed runs.

## Verification

- `.venv314/bin/python -m pytest -q tests/test_indexer.py`
- Result: 11 passed
- `uv run pytest tests/test_performance_profile.py tests/test_config_performance.py tests/test_indexer_agent_embedding_batch.py tests/test_worker_job_runner_chain.py tests/test_job_runner_ingest_backend.py tests/test_config_env_override.py -q`
- Result: 49 passed
