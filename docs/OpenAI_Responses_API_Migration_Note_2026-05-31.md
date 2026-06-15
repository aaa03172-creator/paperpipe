# OpenAI Responses API Migration Note

Date: 2026-05-31
Status: Draft migration note
Owner: PaperPipe runtime and inference maintainers

## Purpose

OpenAI now recommends the Responses API for new text generation work while keeping Chat Completions supported. PaperPipe currently uses Chat Completions in `OpenAIProvider`. This note records the safe migration path without changing runtime behavior yet.

This is a planning note, not adoption approval. A runtime change still needs targeted tests and a small feature-flagged implementation PR.

## Sources Checked

- OpenAI migration guide: https://developers.openai.com/api/docs/guides/migrate-to-responses
- OpenAI text generation guide: https://developers.openai.com/api/docs/guides/text
- OpenAI structured outputs guide: https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI models guide: https://developers.openai.com/api/docs/models

## Current PaperPipe State

- `src/llm_provider.py` owns the OpenAI text path through `OpenAIProvider._make_request`.
- The active endpoint is `client.chat.completions.create(...)`.
- JSON-shaped responses use `response_format={"type": "json_object"}` when `is_json` or `schema` is set.
- The `schema` argument is not currently passed as an API-enforced JSON Schema. Upstream extraction prompts include Pydantic schema text and then validate/parse locally.
- Provider behavior already includes task-level temperature handling, timeouts, retries for OpenAI rate-limit/timeout/status exceptions, and model selection with feature override before cloud default.
- Existing local boundary rules still apply: classify inference payloads as `local_only`, `lab_allowed`, or `external_allowed` before widening any request path.

## Implementation Status

- `llm.cloud.openai_api` supports `chat_completions` and `responses`.
- `llm.cloud.openai_json_mode` supports `json_object` and `json_schema`.
- The default remains `chat_completions`.
- Responses requests set `store: false`.
- JSON-shaped outputs default to JSON object mode.
- Schema-enforced Structured Outputs are available only as a separate opt-in compatibility lane for Responses requests with a schema.
- Local Pydantic validation remains the contract boundary after model output.

## Migration Judgment

Do not flip the default provider API in the current tree.

Use an opt-in compatibility lane first:

```yaml
llm:
  cloud:
    openai_api: "chat_completions" # allowed: chat_completions, responses
    openai_json_mode: "json_object" # allowed: json_object, json_schema
```

The default should remain `chat_completions` until parity tests cover text, JSON, schema-bearing extraction, retries, timeouts, and task-level model/temperature behavior.

## Compatibility Matrix

Before enabling Responses by default, prove parity for:

| Surface | Current expectation | Responses migration check |
| --- | --- | --- |
| Plain text tasks | Return string content for one-liner, deep-read, relevance, teaching, and summary style tasks | `output_text` or equivalent extraction returns the same local contract |
| JSON object tasks | JSON-mode prompts produce parseable JSON for escalation, adjudication, tagging, and teacher-review paths | Responses `text.format` or JSON output path keeps parseable local contracts |
| Schema-bearing extraction | Clinical and specialty extraction prompts remain locally validated against Pydantic schemas | Structured Outputs adoption is tested separately from endpoint migration |
| Error handling | Existing retry handling covers rate-limit, timeout, and API status errors | Responses exceptions map to the same retry/failure behavior |
| Timeout behavior | `timeout` config is passed to the OpenAI request | Responses request receives equivalent timeout behavior |
| Task temperature | Per-task temperature remains honored where supported by selected model/API | Unsupported or ignored parameters are detected in tests, not silently accepted |
| Model selection | Feature model override wins before cloud default and fallback | Responses path uses exactly the same `_get_model(task)` result |
| Payload boundary | External inference receives only allowed excerpts and state | Responses path does not introduce stored conversation state or full-note payloads by accident |

## Proposed Implementation Steps

1. Add a typed config field for `llm.cloud.openai_api` with allowed values `chat_completions` and `responses`; default to `chat_completions`.
2. Add tests proving the default stays on Chat Completions and the opt-in value dispatches to a mocked Responses client.
3. Add a private `_make_responses_request(...)` method inside `OpenAIProvider` while preserving the public `_make_request(...)` contract.
4. Translate the current messages shape into Responses input/instructions without enabling stateful conversation storage.
5. Keep existing JSON-mode behavior first. Treat Structured Outputs as a second step after schema contract tests pass.
6. Record the provider API mode in existing run metadata surfaces where available. Do not create a new truth store.
7. After parity passes, decide separately whether PaperPipe should change the default.

## Non-Goals

- No broad provider abstraction rewrite.
- No default endpoint flip in the same change that introduces the compatibility lane.
- No `/api/chat` product activation.
- No frontend API-key handling.
- No Anthropic or Ollama provider migration.
- No eval baseline or goldset rebaseline.
- No adoption of stored conversation state unless a canonical runtime doc explicitly authorizes it.

## Required Verification Before Runtime Adoption

Minimum targeted checks:

```bash
pytest -q tests/test_llm_provider_task_temperature.py
pytest -q tests/test_llm_provider_json.py
pytest -q tests/test_llm_provider_canonical_language.py
pytest -q tests/test_config_env_override.py
pytest -q tests/test_openai_provider_embeddings.py
./scripts/run_backend_api_smoke.sh
```

Add or update focused tests for the new config field and mocked Responses dispatch in the same PR that adds runtime code.

## Rollback

Set `llm.cloud.openai_api` back to `chat_completions`.

The recommended compatibility lane should not require persisted schema, database, artifact, or goldset migrations.
