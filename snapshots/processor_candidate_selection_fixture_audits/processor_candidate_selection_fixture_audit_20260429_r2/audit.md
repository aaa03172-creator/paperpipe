# Processor Candidate Selection Fixture Audit

Run ID: `processor_candidate_selection_fixture_audit_20260429_r2`
Fixture: `/Users/jangseongjin/paperpipe/tests/fixtures/processor_candidate_selection_pools_20260429.json`

## Metrics

- Pool count: `3`
- Matched count: `3`
- Mismatch count: `0`
- Accuracy: `1.0`

## Pools

### clinical_pubmed_metadata_beats_preprint_freshness

- Status: `PASS`
- Slot: `clinical`
- Expected Top1: `pmid:clinical-guideline`
- Observed Top1: `pmid:clinical-guideline`
- Rationale: Clinical slots should stay conservative when a PubMed candidate has DOI/PDF support even if an arXiv candidate is fresher.

### methods_recent_preprint_beats_weak_pubmed

- Status: `PASS`
- Slot: `methods`
- Expected Top1: `arxiv:methods-benchmark-preprint`
- Observed Top1: `arxiv:methods-benchmark-preprint`
- Rationale: Methods slots should be able to surface a fresh preprint when the PubMed candidate lacks DOI/PDF and recency support.

### mechanism_manual_signal_beats_fresh_preprint

- Status: `PASS`
- Slot: `mechanism`
- Expected Top1: `pmid:mechanism-manual-signal`
- Observed Top1: `pmid:mechanism-manual-signal`
- Rationale: Mechanism slots should preserve a strong upstream/manual ranking signal over pure freshness.
