# PaperPipe ML Quality Improvement Implementation Plan

Status: implementation plan / non-canonical
Date: 2026-06-14
Layer: compiled knowledge / review-gate artifact
Canonical: no
Owner: PaperPipe local optimization and evidence-quality lane

## Purpose

This document combines the local GPU/M4 optimization work, the fine-tuning discussion, and the Notion reference review into one implementation plan.

The central decision is:

- Keep `ollama_metal` as the immediate local GPU fast path for inference and embeddings.
- Do not start with broad model fine-tuning.
- First create schema-backed, source-traceable training/evaluation artifacts from PaperPipe's own review loops.
- Train or tune only narrow components where fixed benchmarks show measurable improvement.

This plan is not a canonical runtime spec. It is a bounded roadmap for PR-sized implementation lanes. Any persisted schema, API, or artifact contract promoted from this plan must update the owning canonical docs and tests.

## Execution Goal Contract

Goal:

- Build a source-traceable ML quality loop for PaperPipe that can improve parsing, evidence linking, and correction quality without weakening evidence lineage, local-first payload boundaries, or schema-backed runtime truth.

Primary outcome:

- PaperPipe can produce reviewed, schema-backed training and evaluation examples from its own runs, then use those examples to evaluate narrow ML candidates before any model, reranker, or fine-tuned adapter is promoted into runtime use.

This goal is complete only when all of the following are true:

1. `training_example.v1`, `evidence_rerank_example.v1`, and `correction_review_example.v1` have Pydantic contracts with targeted tests.
2. At least one local exporter can write reviewed examples from existing PaperPipe artifacts without storing full private PDFs, full notes, raw memory, local paths, or unclassified payloads.
3. A fixed baseline eval can compare current behavior against a candidate for at least one task: evidence reranking, structured extraction normalization, or correction classification.
4. Eval output records source refs, payload class, baseline metrics, candidate metrics, failure taxonomy, and promotion recommendation.
5. No candidate model or tuned component is allowed to replace runtime behavior until it beats baseline on a fixed manifest and does not increase unsupported or untraceable claims.

Current phase:

- Phase 0 local GPU/inference performance work is already in progress under the M4 optimization lane.
- Phase 1 foundation is implemented as non-canonical training example contracts and a local JSONL sidecar writer.
- Phase 2 foundation is implemented as a fixed eval manifest/report gate.
- Phase 3 candidate paths are implemented as non-runtime pilot sidecars for evidence reranking, extraction normalization, and correction calibration.
- Phase 4 LoRA work is limited to an experiment gate. No tuned adapter is promoted into runtime behavior.

Scope:

- Add non-canonical review/gate artifacts for training examples and eval outputs.
- Use existing PaperPipe paper/run/artifact/source-span concepts instead of creating a parallel truth store.
- Prefer local-only generation and evaluation for private paper content.
- Make future fine-tuning possible by creating clean data contracts first.

Non-goals:

- Do not fine-tune a broad reader model as the first step.
- Do not add a global graph, Neo4j-style runtime truth, or hosted discovery dependency.
- Do not make generated examples canonical state.
- Do not send private PDFs, full notes, local paths, or unpublished context to external training providers.
- Do not commit model weights, large training outputs, or local runtime artifacts.

Decision criteria for future work:

- A task belongs in this goal if it improves one of: structured extraction fidelity, evidence span linking, unsupported/overclaim detection, correction quality, or evaluation reproducibility.
- A task does not belong if it is only general inference speed, UI polish, external discovery expansion, or broad product positioning without training/eval artifacts.
- If a proposed change touches persisted shapes, it must include schema updates, compatibility notes, and targeted tests.
- If a proposed change touches inference payloads, it must classify the payload as `local_only`, `lab_allowed`, or `external_allowed` before implementation.

First PR-sized sprint contract:

- Add schemas for `training_example.v1`, `evidence_rerank_example.v1`, and `correction_review_example.v1`.
- Add tests that prove source refs, payload class, review status, and generated-vs-reviewed separation are required or validated.
- Add one local writer/exporter for correction or evidence-linking examples from existing artifacts.
- Add a short report or fixture showing one exported example shape with private content minimized.

First sprint done means:

- The schema tests pass.
- The exporter writes deterministic, source-traceable examples.
- The output is marked non-canonical and payload-classified.
- The implementation does not alter current Deep Read runtime behavior.

Implementation checkpoint, 2026-06-14:

- Added `src/schemas/ml_training_examples.py` and `src/services/ml_training_examples.py`.
- Added `src/schemas/ml_quality_eval.py` and `src/services/ml_quality_eval.py`.
- Added `src/schemas/ml_evidence_reranking.py` and `src/services/ml_evidence_reranking.py`.
- Added `src/schemas/ml_extraction_normalization.py` and `src/services/ml_extraction_normalization.py`.
- Added `src/schemas/ml_correction_calibration.py` and `src/services/ml_correction_calibration.py`.
- Added `src/schemas/ml_lora_experiment_gate.py` and `src/services/ml_lora_experiment_gate.py`.
- Added targeted tests under `tests/test_ml_*`.
- Focused verification: `28 passed` across training examples, quality eval, evidence reranking, extraction normalization, correction calibration, and LoRA experiment gate tests.
- Lint verification: `ruff check` passed for the new ML schema/service/test files.
- Runtime status: candidate paths remain non-canonical review/gate artifacts and are not wired into reader, classifier, extractor, or API runtime behavior.

Promotion gates:

- Data capture gate: reviewed examples preserve source refs and separate candidate output from reviewed output.
- Eval gate: candidate metrics are compared against a fixed baseline manifest.
- Safety gate: unsupported claim rate, untraceable claim rate, and payload-boundary violations do not increase.
- Runtime gate: runtime behavior changes only after schema, API, docs, and tests for the owning surface are updated.

Stop conditions:

- Source/evidence lineage is missing.
- Payload class is ambiguous.
- A model improves wording while reducing traceability.
- The implementation requires external training on private content before redaction policy exists.
- The implementation creates a second canonical truth store for paper/evidence state.

## Inputs Reviewed

Local implementation context:

- `docs/reports/M4_Local_Optimization_Audit_2026-06-11.md`
- `src/services/performance_profile.py`
- `src/agents/adapter.py`
- `src/agents/indexer_agent.py`
- `src/indexer.py`
- `src/config.py`
- `config.example.yaml`

Notion reference pages:

- PaperPipe Project Knowhow (2026-06-07): source/evidence lineage, schema-backed truth, goldset provenance, lane discipline.
- Moro Reference Map (2026-06-07): reviewed candidates and usage feedback before durable memory or training adoption.
- SciAtlas Reference Fit Review (2026-05-26): tri-path retrieval, graph/ranking sidecars, reproducible non-canonical artifacts.

Host capability observed:

- Apple M4 Mac mini, 10 CPU cores, 10-core Apple GPU, 16 GB unified memory.
- Ollama `0.30.7` installed.
- `qwen3.5:4b` was observed loaded as `100% GPU` through Ollama.

## Guiding Rules

1. If it cannot trace back to source/evidence, it is not evidence-backed.
2. If it is not schema-backed, it is not canonical runtime truth.
3. Generated examples start as draft-like or non-canonical.
4. Training data must preserve source span, claim, evidence link, adjudication state, and payload class.
5. Local-first means ownership and inspectability. It does not require every experiment to be local-only, but ambiguous payloads default stricter.
6. Fine-tuning is allowed only after a fixed eval baseline exists.
7. A model is promoted only when it improves measured quality without increasing unsupported claims or losing evidence lineage.

## Target Quality Problems

### Parsing And Structured Extraction

Current opportunity:

- Reader/extractor outputs can vary in field coverage, section boundaries, JSON stability, numeric fidelity, and unit preservation.

Best ML fit:

- Supervised extraction or normalization dataset:
  - input: bounded paper excerpt, section text, table text, or reader context
  - target: schema JSON, normalized fields, missing-field reason, source spans

Likely first model type:

- Small local extractor/normalizer model or LoRA adapter.
- Only after schema and eval fixtures are stable.

### Evidence Linking

Current opportunity:

- Claim-to-evidence matching is closer to retrieval/ranking than free-form generation.

Best ML fit:

- Reranker or embedding fine-tuning:
  - query: claim, clinical field, or extracted assertion
  - positives: exact supporting sentence/table/figure-caption spans
  - hard negatives: nearby but non-supporting spans, contradictory spans, approximate-only spans

Likely first model type:

- Cross-encoder reranker or sentence-transformer style embedding/reranker tuning.
- This should be the first serious training candidate.

### Correction And Calibration

Current opportunity:

- Claims may overstate evidence, omit uncertainty, mismatch numeric details, or cite weak support.

Best ML fit:

- Verifier/corrector classifier:
  - input: claim + evidence span + metadata
  - target: supported, weak, unsupported, overclaim, numeric mismatch, location missing, uncertainty missing
  - optional target: minimal correction candidate

Likely first model type:

- Small classifier or instruction-tuned verifier.
- Keep automatic rewrite behind review gates.

### Reader / Classifier / Extractor End-To-End LoRA

Current opportunity:

- End-to-end quality may improve after enough reviewed examples exist.

Best ML fit:

- LoRA or adapter tuning on narrow tasks only:
  - structured biomedical extraction
  - slot classification hard cases
  - claim quality classification

Likely timing:

- Later. Do not start here.

## Proposed Artifact Contracts

### `training_example.v1`

Layer: review/gate artifact, non-canonical until promoted.

Purpose:

- Store adjudicated examples that can feed evals, rerankers, classifiers, or future fine-tuning.

Minimum fields:

- `example_id`
- `paper_id`
- `run_id`
- `artifact_id`
- `task_type`: `extraction`, `evidence_linking`, `correction`, `slot_classification`, `reader_quality`
- `payload_class`: `local_only`, `lab_allowed`, or `external_allowed`
- `input_ref`: pointer to source artifact and bounded excerpt coordinates
- `source_spans`: page, block, line, char offsets where available
- `candidate_output`
- `reviewed_output`
- `review_status`: `draft`, `reviewed`, `accepted`, `rejected`
- `failure_taxonomy`
- `reviewer_notes`
- `created_at`
- `schema_version`

Non-goals:

- Do not store full private PDFs or full notes in training examples.
- Do not make generated examples canonical truth.
- Do not export examples to external providers unless payload class explicitly allows it.

### `evidence_rerank_example.v1`

Purpose:

- Support evidence-linking training and evaluation.

Minimum fields:

- `claim_id`
- `claim_text`
- `positive_span_ids`
- `hard_negative_span_ids`
- `candidate_span_pool_ref`
- `ranking_source`: keyword, semantic, title/reference, graph-like sidecar, or hybrid
- `adjudication_status`

### `correction_review_example.v1`

Purpose:

- Support verifier/corrector training.

Minimum fields:

- `claim_text`
- `evidence_text_ref`
- `observed_issue`
- `expected_label`
- `minimal_correction`
- `must_preserve_terms`
- `must_not_infer`

## Implementation Phases

### Phase 0: Keep The Local GPU Fast Path

Goal:

- Stabilize current performance work before adding model-training complexity.

Implementation:

- Keep `performance.local_gpu_backend: "ollama_metal"` as the default local fast path.
- Keep Ollama batch embeddings in `OllamaModelAdapter.embed_batch()`.
- Keep MPS-aware local biomedical indexer device selection opt-in through `--device` and `PAPERPIPE_INDEXER_DEVICE`.
- Use `run_meta.performance` to collect baseline stage timings.

Acceptance:

- Deep Read jobs write `performance_profile.v1`.
- Indexing path preserves deterministic chunk IDs and vector IDs.
- No external payload path is widened.

### Phase 1: Training Example Capture

Goal:

- Convert existing review/correction/evidence artifacts into durable, source-traceable training examples.

Likely files:

- `src/schemas/`
- `src/services/`
- `backend/routers/`
- `tests/`
- `docs/`

Implementation:

- Add Pydantic schemas for `training_example.v1`, `evidence_rerank_example.v1`, and `correction_review_example.v1`.
- Add writer helpers that create JSONL or JSON sidecars under the relevant run/artifact directory.
- Add a CLI or API export command that gathers reviewed examples from completed runs.
- Mark all exports with payload class and non-canonical status.

Acceptance:

- Every example can trace to a paper/run/artifact/source span.
- Generated candidates and reviewed outputs are separate fields.
- Tests cover schema validation and source-span preservation.

### Phase 2: Fixed Eval Harness

Goal:

- Make quality measurable before training.

Implementation:

- Build fixed manifests for:
  - extraction JSON exactness and field coverage
  - evidence span recall and precision
  - unsupported/overclaim detection
  - correction precision
- Compare current baseline against any new model or reranker.
- Store eval outputs as non-canonical review/gate artifacts.

Metrics:

- extraction field F1
- JSON validity
- source-span recall
- hard-negative rejection rate
- unsupported claim rate
- overclaim detection precision
- correction acceptance rate
- operator review burden

Acceptance:

- A candidate cannot be promoted without a baseline comparison.
- Eval output states what it measures and what it does not.

### Phase 3: Evidence Reranker Pilot

Goal:

- Improve claim-to-evidence linking before touching broad generation.

Implementation:

- Generate candidate span pools using a tri-path strategy:
  - keyword anchors
  - semantic retrieval
  - title/reference/table/figure anchors where available
- Train or tune a small reranker from reviewed positives and hard negatives.
- Keep reranker output as a sidecar until proven.

Candidate outputs:

- `evidence_rerank_eval.json`
- `evidence_rerank_sidecar.json`
- `evidence_rerank_training_examples.jsonl`

Promotion gate:

- Improve evidence span recall or hard-negative rejection by at least 20 percent on the fixed manifest.
- Do not increase unsupported claim acceptance.
- Do not require private raw notes or full PDFs to leave the local machine.

### Phase 4: Extraction Normalizer / Parser Fine-Tuning

Goal:

- Reduce malformed JSON, field omissions, unit loss, and section-boundary errors.

Implementation:

- Start with normalizer-style training:
  - candidate extraction plus source excerpt in
  - corrected schema JSON plus reasons out
- Keep output schema-backed.
- Compare against current extractor baseline.

Promotion gate:

- Improve schema-valid extraction and field coverage on the fixed manifest.
- Preserve numeric and unit fidelity.
- Do not reduce evidence-span traceability.

### Phase 5: Correction And Calibration Model

Goal:

- Improve review safety by classifying and minimally correcting unsupported, weak, or overstated claims.

Implementation:

- Train a verifier/corrector on reviewed claim/evidence pairs.
- Output labels and minimal correction candidates.
- Keep automatic application behind human review.

Promotion gate:

- High precision on unsupported/overclaim labels.
- Low false-positive burden.
- Corrections remain source-grounded and minimal.

### Phase 6: Reader / Extractor LoRA Experiment

Goal:

- Only after Phases 1-5 produce stable data, test whether a LoRA adapter improves end-to-end reader/extractor quality.

Implementation:

- Use small local models first, likely 3B-4B class on the M4 host.
- Keep 7B experiments opt-in due to 16 GB unified memory limits.
- Train on bounded excerpts and reviewed targets, not full private notes.
- Keep model artifacts out of git unless a small fixture is explicitly approved.

Promotion gate:

- Beat baseline on fixed manifests.
- Keep inference latency acceptable under `run_meta.performance`.
- Do not increase hallucinated or unsupported claims.

## Data Governance And Payload Classes

Default classification:

- Raw PDFs and full notes: `local_only`
- Source excerpts with private/local context: `local_only`
- Public abstracts/titles/metadata: possibly `external_allowed` if no private context is attached
- Reviewed examples with source spans: default `local_only` until explicitly redacted

Rules:

- Do not send full notes, local paths, raw memory, unpublished lab context, or full PDFs to external providers.
- Prefer source refs and bounded excerpts over full text.
- Training exports must include payload class.
- External training requires a separate approval and redaction review.

## PR-Sized Sequence

1. Add `training_example.v1` schemas and tests.
2. Add local writer/exporter for reviewed extraction and correction examples.
3. Add evidence-linking example exporter with positive and hard-negative spans.
4. Add fixed eval manifests and baseline reporting.
5. Add tri-path candidate span pool sidecar.
6. Pilot local reranker evaluation.
7. Pilot extraction normalizer evaluation.
8. Only then evaluate LoRA or MLX/MPS training experiments.

## Risks

- Fine-tuning on weak generated data can amplify existing errors.
- Training without source spans can improve style while degrading truth.
- A broad reader LoRA can hide failure modes behind fluent output.
- Large local training can exceed M4 16 GB memory limits.
- External training can violate local-first payload boundaries if examples are not classified and redacted.

## Hard Stops

- No fixed eval baseline.
- No source/evidence lineage in training examples.
- No separation between generated candidate and reviewed target.
- Payload class is ambiguous.
- Model improves wording but increases unsupported claims.
- Training requires committing large model artifacts, private PDFs, raw notes, or local paths.

## Immediate Recommendation

The next implementation lane should be:

`training_example.v1` plus an evidence-linking/correction example exporter.

That is the smallest step that makes future fine-tuning real. It creates the supervised data and eval substrate needed for rerankers, verifiers, extraction normalizers, and later LoRA experiments without prematurely changing PaperPipe's runtime behavior.
