## Mock or fixture risk: Fake worker hides real deepread runner contract

Status: Confirmed
Test file/line: `frontend/scripts/run_fake_worker_for_e2e.py:185`; `frontend/scripts/run_backend_for_e2e.sh:2344`
Mock/fixture involved: fake E2E worker replacing `worker_mod.run_deepread_job`
Related production behavior: Browser/API/job queue/worker/artifact flow
Mismatch or risk: Fake worker writes synthetic successful artifacts rather than running production ingest/index/read/artifact generation.
Evidence: Fake worker monkeypatches the runner and backend launcher starts it when `E2E_ENABLE_FAKE_WORKER=1`.
Why it matters: Browser-visible job success can pass while real job runner is broken.
Suggested fix: Keep fake worker for UX E2E, but add separate real-worker contract smoke with narrow network/model fakes.
Suggested test improvement: Assert fake-worker tests are labeled as simulated; add one real-worker integration test.
Confidence: High

## Mock or fixture risk: Worker tests accept old-signature runner fakes

Status: Confirmed
Test file/line: `tests/test_worker_heartbeat.py:29`; `tests/test_jobs_api_smoke.py:543`
Mock/fixture involved: fake `run_deepread_job`
Related production behavior: `Worker.process_job` argument contract
Mismatch or risk: Fake signatures omit current kwargs such as `reasoning_persona`, `profile_id`, `parser_backend`, and `clean_reindex`.
Evidence: Production worker passes these fields; broad TypeError compatibility retry strips them.
Why it matters: Tests can hide argument contract drift or real TypeError failures.
Suggested fix: Update fakes to exact current signature and add signature guard.
Suggested test improvement: Use `inspect.signature` or assertions in fakes for all expected kwargs.
Confidence: High

## Mock or fixture risk: Partial SimpleNamespace config bypasses AppConfig validation

Status: Confirmed
Test file/line: `tests/test_job_runner_clinical_extraction.py:116`, `:247`, `:385`
Mock/fixture involved: `SimpleNamespace` replacement for `load_config()`
Related production behavior: Job runner config loading and privacy/LLM feature behavior
Mismatch or risk: Partial namespace skips Pydantic defaults/validators and required sections.
Evidence: Production `load_config()` returns `AppConfig`; tests replace it with local namespaces.
Why it matters: Config schema/default changes can break production but not tests.
Suggested fix: Use minimal valid `AppConfig` factory.
Suggested test improvement: Assert factory mirrors production defaults and only stubs external providers deliberately.
Confidence: High

## Mock or fixture risk: Candidate ranking fixtures bypass Paper schema

Status: Likely
Test file/line: `tests/test_processor_candidate_selection.py:29`; `scripts/eval/audit_processor_candidate_selection_fixture.py:46`
Mock/fixture involved: `SimpleNamespace` candidate papers
Related production behavior: Daily slot ranking/candidate scoring
Mismatch or risk: Production scoring has branches for actual `Paper` objects and schema-coerced fields.
Evidence: Bibliometric scoring applies only when all candidates are `Paper` instances.
Why it matters: Fixture audit may validate synthetic ranking while real schema/ranking behavior regresses.
Suggested fix: Build fixture candidates with `src.schemas.core.Paper`.
Suggested test improvement: Include one bibliometrics-enabled and one disabled ranking case.
Confidence: Medium

## Mock or fixture risk: Paper note index mocks are not schema-valid responses

Status: Likely
Test file/line: `tests/test_papers_api.py:1813`, `:5832`, `:6300`
Mock/fixture involved: `_build_index` patched with `SimpleNamespace(items=...)`
Related production behavior: Paper listing and paper-note index cache
Mismatch or risk: Real `_build_index()` returns `PaperNoteListResponse` with totals/pagination/filter metadata.
Evidence: Schema requires fields beyond `.items`.
Why it matters: Route code can depend on metadata without tests catching invalid mock shape.
Suggested fix: Use schema-backed minimal response helper.
Suggested test improvement: Validate helper through `PaperNoteListResponse.model_validate`.
Confidence: Medium

## Mock or fixture risk: Mock-mode frontend data can hide backend response shape drift

Status: Confirmed
Test file/line: `frontend/playwright.mock.config.ts:22`; `frontend/src/app/lib/api.ts:645`
Mock/fixture involved: forced frontend mock data
Related production behavior: Frontend routes and API fetch wrappers
Mismatch or risk: Synthetic mock payloads may not match current FastAPI/Pydantic response models.
Evidence: `fetchJson<T>` casts JSON directly; mock fallback returns local data without schema validation.
Why it matters: UI can pass mock E2E and fail on real backend payloads.
Suggested fix: Add OpenAPI/payload contract tests and periodically validate mock payloads against backend schemas.
Suggested test improvement: Separate mock UX tests from backend contract tests in reporting.
Confidence: High

## Mock or fixture risk: Unpaywall/PubMed mocks are too minimal

Status: Likely
Test file/line: `tests/test_downloader.py:80`; `tests/test_fetch_providers.py:8`
Mock/fixture involved: minimal HTTP mocks and provider selection tests
Related production behavior: External scholarly metadata/PDF provider contracts
Mismatch or risk: Mocks do not cover realistic malformed, empty, rate-limited, or nested provider payloads.
Evidence: Production PubMed parses NCBI JSON/XML; downloader tests mainly assert router sequencing and a narrow `best_oa_location` shape.
Why it matters: Upstream shape drift or failure classes can slip through.
Suggested fix: Add fixture-backed provider contract tests.
Suggested test improvement: Store representative provider responses under `tests/fixtures/provider_contracts/`.
Confidence: High
