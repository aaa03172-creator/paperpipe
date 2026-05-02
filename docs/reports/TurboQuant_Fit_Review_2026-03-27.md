# TurboQuant Fit Review

Status: Active evaluation note
Date: 2026-03-27
Owner: Runtime/product maintainers
Canonical parents:
- `docs/Product_Positioning_Principles.md`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

Reference sources:
- [Google Research blog: TurboQuant](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- [TurboQuant paper](https://arxiv.org/abs/2504.19874)

## Purpose

Evaluate whether TurboQuant-style inference optimization is worth adopting for the current PaperPipe runtime.

This is not a proposal to turn PaperPipe into an inference optimization project.

## 1. Current repo inference/runtime summary

### Related current structure

- Product/runtime boundary:
  - `README.md`
  - `docs/Product_Positioning_Principles.md`
  - `docs/Lattice_v3_Master_Spec.md`
  - `docs/reports/First_Shippable_Product_Bar_2026-03-24.md`
- LLM/provider/runtime:
  - `src/config.py`
  - `src/llm_provider.py`
  - `src/agents/adapter.py`
  - `backend/services/job_runner.py`
- Deep-read context path:
  - `src/agents/reader_agent.py`
- Retrieval/index path:
  - `src/agents/indexer_agent.py`

### Repo-confirmed facts

- PaperPipe is currently a local-first, paper-first, job/run/artifact-first biomedical evidence workspace, not a model-serving platform.
- Default LLM mode is `local`, and the default local provider is `ollama`.
- The repo has a provider abstraction for local/cloud/hybrid usage, but the current runtime is not built around a custom serving substrate such as vLLM, TGI, or sglang.
- The deep-read reader path is bounded and chunked:
  - `ReaderAgent` caps `max_context_chars` and creates multiple bounded attempts rather than pushing full-document long-context inference.
  - The local adapter reports a context length of `4096`.
- The retrieval/index path currently uses:
  - `nomic-embed-text`
  - ChromaDB persistent storage
- The launch-facing runtime story and current release risks center on:
  - ingestion
  - extraction quality
  - evidence linkage
  - structured state
  - downstream artifact integrity
  - provenance / uncertainty visibility

### What the current model/runtime layer definitely does

- Calls local Ollama models for generation and embeddings by default.
- Supports cloud mode, but cloud is not the current default product posture.
- Uses bounded chunking and retrieval rather than giant-context whole-document prompting as the standard path.
- Chains model work inside a larger ingest/index/read/verify/grounding/artifact pipeline.

### Actual bottleneck candidates from current repo evidence

- Plausible current bottlenecks:
  - PDF/text ingestion quality
  - parsing and OCR quality
  - structured extraction quality
  - citation/evidence grounding
  - downstream artifact generation and regeneration integrity
  - job orchestration latency
- Not yet established from current repo evidence:
  - KV-cache memory pressure as a core product bottleneck
  - long-context serving memory pressure as a core product bottleneck
  - multi-session serving throughput as a launch-defining bottleneck
  - vector index memory pressure as a current bottleneck

### Explicit unknowns

- There is no repo-grounded proof in this pass that PaperPipe is currently failing because Ollama KV-cache memory is exhausted.
- There is no repo-grounded proof in this pass that long-context inference is the main reason deep-read quality or latency is weak.
- There is no repo-grounded proof in this pass that Chroma vector memory is large enough to justify quantized ANN/index work.

These are not ruled out in principle. They are simply not established yet.

## 2. Fit assessment for TurboQuant

### 2.1 Strong fit

- `Local-first orientation`
  - TurboQuant is conceptually more compatible with a local/self-hosted inference future than a cloud-only product.
  - If PaperPipe later depends on heavier local serving or longer-context local models, lower memory cost could matter.
- `Bounded retrieval/index friendliness`
  - The paper also discusses vector-search quantization, which is at least conceptually adjacent to the current embedding + retrieval layer.

### 2.2 Partial fit

- `Local inference path exists, but is not the whole product`
  - PaperPipe does use local models now.
  - However, the product value is not primarily “serve bigger local LLMs”; it is “produce inspectable biomedical state and downstream artifacts.”
- `Vector quantization ideas may eventually matter`
  - Current retrieval uses Chroma and embeddings.
  - If index size, latency, or memory later become real bottlenecks, vector quantization ideas may become relevant.
  - Right now that remains conditional.
- `Long-context support could matter later`
  - If a future reader path intentionally moves toward much larger local context windows, KV-cache compression could help.
  - The current reader path does not strongly justify that yet.

### 2.3 Mismatch / risk

- `Current repo is not an inference infra project`
  - The product identity is biomedical workflow, structured state, provenance, and artifact generation.
  - Pushing TurboQuant too early would move attention toward low-level infra rather than current product bottlenecks.
- `Current reader path is bounded, not giant-context-first`
  - The repo currently chunks and budgets context instead of assuming a huge context window.
  - That lowers the immediate relevance of KV-cache compression.
- `Serving bottleneck not proven`
  - There is no direct current evidence that KV cache, VRAM, or throughput dominates release readiness.
- `Integration maturity is not yet clear`
  - From the minimal official-source review in this pass, TurboQuant looks research-promising.
  - A production-ready PaperPipe-fit integration path is not established here.
- `Operational complexity risk`
  - Any low-level serving optimization introduces testing, deployment, debugging, and fallback complexity.
  - That cost is hard to justify without measured need.

## 3. Adoption recommendation

### Primary recommendation

- `현재는 보류가 맞음`

### Secondary recommendation

- `일부 아이디어만 차용할 가치가 있음`
- `제한적 파일럿/벤치마크 실험 가치는 조건부로 높음`

### Why

- Current PaperPipe bottlenecks are more credibly in:
  - ingest / OCR / parsing
  - evidence linkage
  - structured extraction reliability
  - artifact/state integrity
- The repo does have local inference and retrieval, so TurboQuant is not irrelevant.
- But the key precondition is missing:
  - a measured inference-memory or retrieval-memory bottleneck tied to current user-facing pain

### Repo fit / conflict summary

- Fits:
  - local-first direction
  - possible future local-serving efficiency work
  - possible future retrieval-memory optimization
- Conflicts:
  - current product priority
  - current runtime maturity
  - current lack of evidence that serving optimization is the main limiter

### Preconditions before any serious pilot

- Measure current local inference latency and memory usage on real deep-read workloads.
- Confirm whether current Ollama/local path is meaningfully constrained by context or KV-cache size.
- Measure current embedding/retrieval storage size and retrieval latency on realistic corpora.
- Define a rollbackable, non-canonical experiment path that does not change product messaging.

Current note:

- `docs/reports/Local_Deep_Read_Runtime_Measurement_2026-03-28.md` now shows reader-phase dominance and a fresh representative rerun with additive `reader_analysis` metrics.
- That newer evidence still supports `measure/prompt-profile first`, not `TurboQuant adoption now`.

## 4. Minimal evaluation or integration path

### Smallest useful step

- Do not integrate TurboQuant into runtime now.
- First add a measurement note and benchmark slice for current local inference and retrieval cost.

### Best existing contact points

- `src/config.py`
  - if later adding experimental runtime flags
- `src/llm_provider.py`
  - if later instrumenting provider timing and model/runtime metadata
- `src/agents/reader_agent.py`
  - if later tightening context-budget accounting
- `src/agents/indexer_agent.py`
  - if later testing retrieval/index compression effects
- `backend/services/job_runner.py`
  - if later recording end-to-end model/runtime timing for deep-read phases

### Lowest-risk path

1. Measure current local deep-read runtime on representative papers.
2. Measure current retrieval/index size and latency on representative corpora.
3. If a clear local inference memory bottleneck appears, run an isolated benchmark outside the canonical runtime.
4. Keep the result as a watchlist or benchmark note unless the improvement is both real and operationally cheap.

### Rollback profile

- Very high rollbackability if kept at benchmark/doc level.
- Much worse rollbackability if it enters provider/runtime code before the bottleneck is proven.

## 5. Suggested measurement / experiment plan

### Measure first

- Deep-read end-to-end wall time by phase:
  - ingest
  - index
  - read
  - verify
  - grounding
  - artifact/state promotion
- Local model runtime details:
  - model name
  - context budget used
  - request count per run
  - retry count
  - timeout count
- Retrieval/index details:
  - chunk count per paper
  - Chroma collection size
  - retrieval latency
  - embedding latency
  - persistent storage size

### Comparison targets

- Current default local Ollama runtime
- If later justified:
  - an experimental alternative local-serving path
  - or an isolated quantized retrieval/index benchmark

### Representative workloads

- `1-3` representative real biomedical papers for deep-read
- a small corpus slice large enough to reveal retrieval/index scaling behavior

### Evaluation criteria

- Does the experiment reduce operator-visible latency on deep-read?
- Does it materially improve local memory headroom?
- Does it preserve extraction/evidence quality and downstream artifact integrity?
- Does it add acceptable operational complexity?

### Success threshold

- Not just lower memory or faster kernels.
- The change must improve real PaperPipe workloads without weakening reviewability, provenance, or runtime simplicity.

### Failure threshold

- Memory/speed gains only on synthetic long-context benchmarks
- unclear integration path
- runtime complexity increase larger than user-visible benefit

## 6. Patch / implementation impact

### If we do nothing now

- No runtime patch needed.
- Best immediate action is documentation + watchlist status.

### If a later bounded pilot is approved

- Likely touch points:
  - `src/config.py`
  - `src/llm_provider.py`
  - `src/agents/reader_agent.py`
  - `src/agents/indexer_agent.py`
  - `backend/services/job_runner.py`
  - a new benchmark script under `scripts/`
  - a follow-up report under `docs/reports/`

### Expected difficulty

- Measurement-only pass: low
- Retrieval/index experimental benchmark: medium
- Actual local serving/runtime integration: high

### Risk level

- Measurement-only: low
- Benchmark-only: low to medium
- Runtime adoption now: medium to high, and not justified by current evidence

## Recommended decision

Current best judgment:

- Do not adopt TurboQuant into the current PaperPipe runtime now.
- Keep it on a technical watchlist.
- If local inference memory/latency becomes a proven bottleneck, start with a bounded benchmark rather than runtime integration.
- Before any low-level quantization work, improve measurement and explicit long-context budget accounting in the current runtime.

In short:

> TurboQuant is technically interesting and plausibly relevant to a future heavier local-serving path, but for the current PaperPipe repo it is not yet a justified adoption target. The right move now is measure-first, then maybe pilot, otherwise hold.
