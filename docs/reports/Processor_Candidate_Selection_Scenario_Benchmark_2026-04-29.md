# Processor Candidate Selection Scenario Benchmark

Status: Evidence-backed selection guardrail
Date: 2026-04-29
Owner: Repository maintainers
Layer: Review/gate artifact
Canonical: No. This report records bounded evaluation evidence and does not replace runtime specs.

## Purpose

Document the synthetic and fixture-backed benchmark that locks the current daily-slot candidate scoring behavior.

This follows the source/candidate-selection work where `feedback_json.selection` became more explainable. The benchmark does not change scoring weights; it preserves the current intended behavior so future weight changes are deliberate.

## Runtime Surface

- Owner: `src/processor.py`
- Selection helpers:
  - `_selection_source_bonus()`
  - `_selection_metadata_components()`
  - `_rank_slot_candidates()`
  - `_candidate_selection_breakdown()`
  - `_build_slot_selection_rationale()`
- Test guardrail: `tests/test_processor_candidate_selection.py`
- Fixture-backed candidate pools: `tests/fixtures/processor_candidate_selection_pools_20260429.json`
- Re-runnable fixture audit: `scripts/eval/audit_processor_candidate_selection_fixture.py`

## Scenarios Locked

The tests run under a fixed clock of `2026-04-29` so recency scoring does not drift over time.

| Scenario | Expected behavior |
| --- | --- |
| Clinical source preference | A PubMed candidate with DOI/PDF beats a fresher arXiv candidate. |
| Methods preprint freshness | A recent arXiv preprint can beat a weak older PubMed methods candidate. |
| Mechanism manual/base priority | A high manual/base score can beat recency/source metadata. |
| Tie-break stability | Equal-score candidates sort by newer publication date, then original fetch order. |

## Fixture Pools

The fixture-backed benchmark stores small expected-Top1 candidate pools outside the test code:

- `clinical_pubmed_metadata_beats_preprint_freshness`
- `methods_recent_preprint_beats_weak_pubmed`
- `mechanism_manual_signal_beats_fresh_preprint`

Each pool includes source, publication date, DOI/PDF metadata, optional manual score, expected Top1, and a short rationale. This makes future scoring changes easier to review because expected outcomes live in a compact data fixture rather than only in Python assertions.

## Interpretation

The benchmark captures current selection policy rather than claiming the weights are globally optimal.

The main operational meaning is:

- Clinical slots remain conservative toward PubMed when DOI/PDF metadata are present.
- Methods slots can still surface fresh preprints when the PubMed candidate lacks metadata support.
- Mechanism slots can preserve upstream/manual ranking signals when those signals are strong.
- Stable fetch order remains the final tie-breaker after score and recency.

## Verification

Focused benchmark:

```bash
.venv/bin/python -m pytest tests/test_processor_candidate_selection.py -q
```

Fixture audit:

```bash
.venv/bin/python scripts/eval/audit_processor_candidate_selection_fixture.py \
  --run-id processor_candidate_selection_fixture_audit_20260429_r2
```

Related selection/reporting bundle:

```bash
.venv/bin/python -m pytest \
  tests/test_processor_candidate_selection.py \
  tests/test_processor_candidate_selection_fixture_audit.py \
  tests/test_processor_institutional_proxy.py \
  tests/test_reporting.py \
  tests/test_cli_daily_slot_report.py \
  tests/test_intake_override_audit.py \
  tests/test_cli_intake_override_audit_show.py \
  -q
```

Latest observed result:

- Focused benchmark: `5 passed`
- Fixture audit: `3/3`, accuracy `1.0`, mismatch `0`
- Latest fixture audit run: `snapshots/processor_candidate_selection_fixture_audits/processor_candidate_selection_fixture_audit_20260429_r2`
- Related bundle: `44 passed`

## Remaining Risk

This is a synthetic and fixture-backed guardrail, not a live retrieval quality benchmark.

It does not prove that the current weights always choose the best real paper. It protects intended selection behaviors and fixture-backed expected Top1 outcomes from accidental drift. A future live benchmark should compare ranked outputs against human-adjudicated daily-slot candidate pools collected from real retrieval runs.
