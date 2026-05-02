# OpenAI Privacy Filter Intake Review

Status: completed intake review
Date: 2026-04-23
Owner: Repository maintainers
Lane: privacy / security / evaluation-only

## Current bottleneck

PaperPipe already has path masking, browser secret removal, API-key protection, beta gate, request audit, and inference payload classification. The remaining privacy bottleneck is that we do not yet have a repo-grounded way to evaluate PII and secret redaction quality before using a redaction model in logs, exports, indexing, or external inference payload gates.

## Classification

`direct candidate`

OpenAI Privacy Filter is a direct candidate for a bounded PaperPipe privacy pilot because it targets the missing capability directly, can run locally, has an Apache 2.0 license, and can be inserted additively as an evaluation or preflight layer. It should not become a production enforcement default until PaperPipe-specific false positive and false negative behavior is measured.

Official references:
- [OpenAI announcement](https://openai.com/index/introducing-openai-privacy-filter/)
- [OpenAI Privacy Filter GitHub repository](https://github.com/openai/privacy-filter)
- [OpenAI Privacy Filter Hugging Face model card](https://huggingface.co/openai/privacy-filter)
- [OpenAI Privacy Filter model card PDF](https://cdn.openai.com/pdf/c66281ed-b638-456a-8ce1-97e9f5264a90/OpenAI-Privacy-Filter-Model-Card.pdf)

## Safest insertion point

The safest insertion point is an evaluation harness under `scripts/eval/`, not a runtime FastAPI route, schema migration, parser replacement, or default redaction pass.

The first pilot should compare Privacy Filter span predictions against PaperPipe policy fixtures that explicitly distinguish:
- spans to redact, such as private emails, phone numbers, addresses, account numbers, and secrets
- spans to preserve, such as public paper authors, journals, DOIs, trial IDs, institutions, and provenance-critical dates
- ambiguous spans that need human review before enforcement

## Do not rewrite these parts

Do not rewrite or replace:
- FastAPI route protection and browser `/api/*` boundary
- `src/services/path_masking.py`
- `src/db_utils.py` runtime state ownership
- paper/job/run/artifact Pydantic contracts
- parser, extraction, grounding, or note/export pipelines
- inference routing defaults or `local_only` / `lab_allowed` / `external_allowed` policy docs

## Main risks

- Over-redaction can remove public biomedical metadata and break evidence lineage.
- Under-redaction can miss uncommon personal names, regional naming patterns, project-specific tokens, or split secrets.
- The model is not an anonymization, compliance, or legal guarantee.
- Default operating points may not match PaperPipe's policy boundary without in-domain evaluation.
- Running OPF can download model weights if a local checkpoint is absent, so CI and repo tests should not require OPF execution.

## Smallest pilot

This PR adds `scripts/eval/evaluate_privacy_filter_intake.py`, an evaluation-only harness that can:
- read PaperPipe privacy-policy fixtures from JSONL
- read saved OPF predictions from JSONL for CI-safe tests
- optionally call a local `opf` CLI when an operator has installed OpenAI Privacy Filter
- optionally add PaperPipe deterministic secret/path/signed-URL rules with `--include-deterministic-scanner`
- optionally suppress trusted public metadata and placeholder predictions with `--apply-paperpipe-preserve-rules`
- optionally add manual-review routing for unresolved privacy risk signals with `--apply-paperpipe-manual-review-gate`
- report true positives, false negatives, unexpected predictions, and preserve conflicts
- write both JSON and Markdown review artifacts

The first PaperPipe policy fixture lives at `tests/fixtures/privacy_filter_intake/paperpipe_policy_fixture.jsonl`
with a short fixture note at `tests/fixtures/privacy_filter_intake/README.md`.
It intentionally mixes private-beta user data, logs, env/config snippets, local paths, citation metadata,
Korean contact examples, public author metadata, DOI URLs, and trial identifiers so the pilot measures both
missed redactions and over-redaction of provenance-critical public scientific metadata.

Current fixture shape:
- 20 records
- all eight OpenAI Privacy Filter labels represented
- both `redact` and `preserve` policies represented

## Pilot observation

On 2026-04-23, the fixture was run locally with OpenAI Privacy Filter in an isolated working-file venv and CPU mode. OPF was not added to PaperPipe runtime dependencies.

Run shape:
- fixture: `tests/fixtures/privacy_filter_intake/paperpipe_policy_fixture.jsonl`
- prediction artifact: `.codex/work/2026-04-23_openai_privacy_filter_intake/generated/opf_predictions.jsonl`
- evaluation artifact: `.codex/work/2026-04-23_openai_privacy_filter_intake/generated/opf_eval.md`

Observed summary:
- records: 20
- expected redact spans: 22
- expected preserve spans: 16
- predicted spans: 25
- true positives: 15
- false negatives: 7
- unexpected predictions: 1
- preserve conflicts: 6

Strong spots:
- private beta person/email/phone examples were detected
- Korean private contact example was detected
- private dates and bank account numbers were detected
- public paper author/date metadata in one citation example was correctly left alone

Weak spots:
- OPF missed a Basic-auth-like beta credential string
- OPF missed an `sk-proj-*`-style API key in an env snippet
- OPF missed a signed private URL and its signature token
- OPF missed a short subject identifier (`JL-042`)
- OPF detected public author contact emails, public author names, and a clinical trial ID that PaperPipe would often need to preserve

Interpretation:
- This confirms the original recommendation: OPF is useful as a privacy scan layer, but not safe as a standalone production enforcement layer.
- PaperPipe should combine OPF with deterministic secret scanners, existing path masking, allow/preserve rules for scientific metadata, and human review for high-sensitivity exports.
- The next runtime pilot, if any, should be an explicit preflight gate for export/external-inference payloads, not silent mutation of canonical state.

## Deterministic scanner observation

After adding the PaperPipe deterministic scanner to the same saved OPF predictions, the combined evaluation produced:

- records: 20
- expected redact spans: 22
- expected preserve spans: 16
- predicted spans: 32
- true positives: 21
- false negatives: 1
- unexpected predictions: 1
- preserve conflicts: 6

The deterministic scanner closed most of the OPF-only misses:

- Basic-auth-like beta credential strings
- `sk-*` and `sk-proj-*` style keys
- local filesystem paths
- signed private URLs and signature query tokens
- short subject IDs when they appear in an explicit subject/participant context

The remaining false negative was a single first name in a clinical appointment sentence. The remaining preserve conflicts were public scientific metadata and documentation placeholders, not scanner misses. That means the next adoption problem is not only better detection. PaperPipe also needs a preserve-rule layer that distinguishes public provenance metadata from private user/operator content.

## Preserve-rule observation

After applying the PaperPipe preserve-rule layer to the OPF plus deterministic scanner output, the evaluation produced:

- records: 20
- expected redact spans: 22
- expected preserve spans: 16
- predicted spans: 26
- true positives: 21
- false negatives: 1
- unexpected predictions: 1
- preserve conflicts: 0

The preserve-rule layer is intentionally narrow. It only suppresses predictions in trusted public/provenance surfaces:

- public paper and citation metadata for author names, publication dates, public author emails, affiliations, DOI IDs, and DOI URLs
- clinical registry IDs on the `clinical_metadata` surface
- synthetic placeholders on the `docs` surface
- Zotero-derived identifiers and internal paper PDF routes on the `obsidian_note` surface

It does not suppress private beta payloads, operator notes, raw logs, local paths, request audit data, or note-body subject identifiers. The remaining review queue after this layer is therefore more focused: a short private first name (`Maya`) and one over-wide OPF prediction around a local path key-value string.

## Manual-review gate observation

After applying the manual-review gate to the OPF plus deterministic scanner plus preserve-rule output, the evaluation produced:

- records: 20
- expected redact spans: 22
- expected preserve spans: 16
- predicted spans: 26
- true positives: 21
- false negatives: 1
- unexpected predictions: 1
- preserve conflicts: 0
- manual review records: 2
- manual review reasons: 3

The manual-review gate does not mutate predictions or text. It only routes unresolved risk for human review:

- missed expected redactions
- unexpected detector spans
- short possessive names near clinical or personal event cues on private/operator surfaces

For the current fixture, that leaves only two records in the review queue:

- `clinical-appointment-date-redact`, because a short private first name was missed near a clinical appointment cue
- `local-path-redact`, because OPF emitted an over-wide local-path key-value span

## Preflight contract

Before any runtime pilot, the privacy preflight output contract is fixed in `src/schemas/privacy_preflight.py`.

Contract summary:

- schema: `privacy_preflight.v1`
- mode: `off`, `report_only`, or `block_on_review`
- rollback flag: `LATTICE_PRIVACY_PREFLIGHT_MODE`
- default and rollback value: `off`
- first pilot mutation posture: `mutation_applied=false`
- first pilot status options: `disabled`, `pass`, `review_required`, `blocked`

Operational rule:

- `off` disables the pilot.
- `report_only` may emit findings and manual-review routing, but must not block or mutate text.
- `block_on_review` may block export or external inference when manual-review items exist, but must not silently rewrite canonical state.

## Runtime pilot wiring

The first runtime wiring is intentionally narrow:

- path: deep-read `clinical_extraction` external-inference payload in `backend/services/job_runner.py`
- default: `LATTICE_PRIVACY_PREFLIGHT_MODE=off`
- report-only behavior: record `run_meta.inference_lanes.clinical_extraction.privacy_preflight`
- block behavior: skip only `clinical_extraction.json` generation when review items exist
- payload minimization: local filesystem paths and signed private URLs are dropped from the provider-facing `link` field
- read-only API visibility: artifact bundle responses expose the preflight report under `inference_summary.lanes.clinical_extraction.privacy_preflight`

This does not add OPF as a runtime dependency and does not enable automatic canonical-state mutation.

Example fixture line:

```json
{"id":"paperpipe-privacy-001","text":"Email clinician@example.org but preserve Park et al.","expected_spans":[{"label":"private_email","text":"clinician@example.org","policy":"redact"},{"label":"private_person","text":"Park et al.","policy":"preserve"}]}
```

Example saved prediction line:

```json
{"id":"paperpipe-privacy-001","detected_spans":[{"label":"private_email","text":"clinician@example.org"},{"label":"private_person","text":"Park et al."}]}
```

Example CI-safe run:

```bash
python3 scripts/eval/evaluate_privacy_filter_intake.py \
  --input-jsonl privacy_policy.jsonl \
  --predictions-jsonl opf_predictions.jsonl \
  --output-json privacy_eval.json \
  --output-md privacy_eval.md
```

Example combined OPF plus deterministic scanner run:

```bash
python3 scripts/eval/evaluate_privacy_filter_intake.py \
  --input-jsonl privacy_policy.jsonl \
  --predictions-jsonl opf_predictions.jsonl \
  --include-deterministic-scanner \
  --output-json privacy_eval.json \
  --output-md privacy_eval.md
```

Example combined OPF plus deterministic scanner plus preserve-rule run:

```bash
python3 scripts/eval/evaluate_privacy_filter_intake.py \
  --input-jsonl privacy_policy.jsonl \
  --predictions-jsonl opf_predictions.jsonl \
  --include-deterministic-scanner \
  --apply-paperpipe-preserve-rules \
  --output-json privacy_eval.json \
  --output-md privacy_eval.md
```

Example full intake run with manual-review routing:

```bash
python3 scripts/eval/evaluate_privacy_filter_intake.py \
  --input-jsonl privacy_policy.jsonl \
  --predictions-jsonl opf_predictions.jsonl \
  --include-deterministic-scanner \
  --apply-paperpipe-preserve-rules \
  --apply-paperpipe-manual-review-gate \
  --output-json privacy_eval.json \
  --output-md privacy_eval.md
```

Example local OPF run:

```bash
python3 scripts/eval/evaluate_privacy_filter_intake.py \
  --input-jsonl privacy_policy.jsonl \
  --use-opf \
  --opf-command opf \
  --opf-extra-arg=--device \
  --opf-extra-arg=cpu \
  --output-json privacy_eval.json \
  --output-md privacy_eval.md
```

## Adoption gate

Before any production enforcement, require:
- at least one PaperPipe fixture set covering paper metadata, notes, logs, request audit payloads, local file paths, and code-like secrets
- a measured preserve-conflict rate for public scientific metadata
- a measured false-negative rate for secrets and contact details
- a documented operating point and rollback flag
- human-review routing for high-sensitivity medical, legal, financial, or private beta user content
