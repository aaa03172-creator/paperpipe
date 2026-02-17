# PR Split Plan (2026-02-17)

## PR-A: Gate Engine / Quality Layer
Target files:
- `src/gates.py`
- `src/schemas/gates.py`
- `src/schemas/__init__.py`
- `tests/test_gates.py`
- `tests/test_processor_gate_integration.py`
- `docs/Codex_Hybrid_Working_Context.md`
- `src/processor.py` (GateEngine integration only)

Goal:
- Stable gate contract (decision/reason codes/schema)
- Processor gate path uses GateEngine + schema validation
- Unit/integration tests for gate behavior

## PR-B: Runtime PDF Context
Target files:
- `src/pdf.py`
- `src/llm_provider.py`
- `scripts/extract_pdf_text.py`
- `tests/verify_pdf_extraction.py`
- `docs/development_rules.md` (optional doc PR)

Goal:
- PDF text extraction utility
- Prompt context extension with `full_text`
- Manual verification script

## Current caution
- `.env.example` is staged and should remain out of both PRs unless explicitly intended.
- `src/processor.py` is currently staged; verify staged diff before committing.
