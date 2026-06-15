# APOE4-to-APOE2 Paper Workflow Comparison

Status: Review note
Date: 2026-05-26
Scope: Compare one program-run PaperPipe workflow with one manual analyst workflow for the same open-access paper.
Paper: Golden LR, Siano DS, Stephens IO, et al. "APOE4 to APOE2 allelic switching in mice improves Alzheimer's disease-related metabolic signatures, neuropathology and cognition." Nature Neuroscience 28, 2461-2475 (2025).
DOI: https://doi.org/10.1038/s41593-025-02094-y

## Boundary

This is a dated review note, not a canonical runtime spec.

Layer classification:

- Raw source: Nature article/PDF.
- Canonical structured state: the runtime-promoted `.pp/<slug>/state.json` from the program run.
- Review/gate artifacts: deep-read quality gate, acceptance contract, visual evidence ledger.
- Compiled knowledge: generated paper synthesis and this comparison note.
- User-facing artifact/export: any note or report prepared for human review.

This note should not directly change the FastAPI API surface, schemas, DB/state layer, or artifact contract.

## Source Paper Takeaway

The paper is best understood as a preclinical proof-of-concept for APOE allele replacement. The central scientific message is not simply that APOE2 is protective, but that replacing APOE4 with APOE2, especially from astrocytes, can reshape AD-relevant lipid, transcriptomic, neuropathology, and cognition-related phenotypes in mice.

Important caution: the paper supports mouse-model mechanism and therapeutic plausibility. It does not establish human therapeutic efficacy or clinical safety for APOE editing.

## Program Run Summary

Program workflow used:

1. Downloaded the official open-access PDF.
2. Imported it via `paperpipe import-pdf`.
3. Ran the deep-read backend job with local inference.
4. Promoted structured state and generated a paper synthesis bundle.

Observed runtime outputs:

- `paper_id`: `userpdf-306e8a10fb3b6f1f`
- `run_id`: `codex_apoe4_apoe2_20260526_r1`
- parser backend: `fitz_pdfplumber`
- inference boundary: `local_only`
- run status: `succeeded`
- resolved claims: `3`
- evidence spans: `3`
- quality gate: `review_ready=true`, no hard fail codes
- statistical verification: not run
- visual evidence replay: 8 entries, 5 partial and 3 unknown

Artifact paths:

- `storage/artifacts/userpdf-306e8a10fb3b6f1f/codex_apoe4_apoe2_20260526_r1/run_meta.json`
- `storage/artifacts/userpdf-306e8a10fb3b6f1f/codex_apoe4_apoe2_20260526_r1/bootstrap_meta.json`
- `storage/artifacts/userpdf-306e8a10fb3b6f1f/codex_apoe4_apoe2_20260526_r1/claimset.resolved.json`
- `storage/artifacts/userpdf-306e8a10fb3b6f1f/codex_apoe4_apoe2_20260526_r1/quality_gate.json`
- `storage/artifacts/userpdf-306e8a10fb3b6f1f/codex_apoe4_apoe2_20260526_r1/acceptance_contract.json`
- `storage/artifacts/userpdf-306e8a10fb3b6f1f/codex_apoe4_apoe2_20260526_r1/visual_evidence_ledger.json`
- `storage/paper_syntheses/papersynth_apoe4-to-apoe2-allelic-switching-in-mice-improves-alzheimer-s-disease-related-me-306e8a10_codex_apoe4_apoe2_20260526_r1_e82f8718e8/paper_synthesis.md`

The three extracted claims were all transcriptomic:

1. Full-body switching drives AD-relevant transcriptomic changes.
2. Astrocyte-only APOE4-to-APOE2 switching produces transcriptomic changes similar to the full-body transition.
3. Replacement of E4 with E2 in adult mice changes multiple CNS cell types, especially astrocytes and immune/metabolism pathways.

## Manual Analyst Summary

The manual pass produced a broader claim map:

1. APOE4s2 enables inducible in vivo APOE4-to-APOE2 switching.
2. Whole-body switching creates E2-like metabolic and lipid signatures.
3. E4-to-E2 switching acutely alters AD-relevant CNS transcriptomic pathways.
4. Astrocyte-targeted switching reproduces much of the CNS transcriptomic effect.
5. Astrocyte-specific switching reduces amyloid pathology and gliosis in 5xFAD mice.
6. Cognitive benefit is selective: associative memory improves, while spatial memory is not clearly improved.
7. Translational promise remains bounded by mouse-model, lipid-safety, ancestry, and tauopathy limitations.

Manual evidence anchors:

| Manual claim | Source anchor | Why it matters |
|---|---|---|
| APOE4s2 enables inducible in vivo APOE4-to-APOE2 switching. | Abstract; main section `APOE 'switch' mice efficiently transition from E4 to E2`; Fig. 1 and Extended Data Fig. 1. | Establishes the model validity before interpreting downstream phenotypes. |
| Whole-body switching creates E2-like metabolic and lipid signatures. | Main section `Whole-body switch results in an 'E2-like' metabolic profile`; Fig. 2 and Extended Data Fig. 2. | Covers the metabolic-signature part of the title that the program claimset missed. |
| E4-to-E2 switching acutely alters AD-relevant CNS transcriptomic pathways. | Main section `Full-body switching drives AD-relevant transcriptomic changes`; Fig. 3 and Extended Data Fig. 3-4. | Confirms the family captured by the program run and connects it to cell-type data. |
| Astrocyte-targeted switching reproduces much of the CNS transcriptomic effect. | Astrocyte-selective APOE4s2 model/results sections; Extended Data Fig. 5 and related transcriptomic comparisons. | Separates whole-body replacement from the more translationally relevant CNS/cell-source question. |
| Astrocyte-specific switching reduces amyloid pathology and gliosis in 5xFAD mice. | 5xFAD astrocyte-specific switching pathology results; Fig. 5 for amyloid plaque load and memory, Fig. 6 for plaque-associated gliosis, and Fig. 7 for reactive microglia/plaque-associated ApoE. | Covers the neuropathology axis that was absent from the program claimset. |
| Cognitive benefit is selective. | 5xFAD behavioral results, including fear conditioning and Morris water maze. | Prevents overclaiming broad cognitive rescue. |
| Translational promise remains bounded by model and safety limits. | Discussion limitations on lipid liability, ancestry effects, tauopathy/model scope, and delivery/editing implications. | Keeps the synthesis preclinical and avoids clinical overreach. |

## Comparison

| Dimension | Program workflow | Manual workflow | Interpretation |
|---|---|---|---|
| Provenance | Strong. Runtime artifacts, run metadata, claimset, quality gate, and synthesis lineage were saved. | Weak to moderate. Human-readable source references, but no structured locator artifact. | Program wins on reproducibility and auditability. |
| Scientific coverage | Narrow. It captured transcriptomic claims but missed major title-level axes. | Broad. It covered allelic-switch validation, metabolism, neuropathology, cognition, and translational limits. | Manual pass wins on semantic coverage. |
| Evidence discipline | Strong for extracted claims; bbox-backed evidence was present. | Stronger interpretive balance, but less machine-checkable. | The best workflow needs both locator discipline and expert coverage review. |
| Failure visibility | Good. Visual/table uncertainty and not-run statistical verification were explicit. | Depends on reviewer habits. | Program-generated uncertainty sidecars are valuable. |
| Reuse readiness | Good for the three extracted transcriptomic claims only. | Good for human briefing, not enough for canonical promotion. | Manual notes should be treated as reviewer input, not canonical state. |
| Main risk | False sense of completeness because quality gate passed despite narrow claim coverage. | Selection bias and weak audit trail. | Coverage gates should be separate from claim-level grounding gates. |

## Main Finding

The program run produced a valid, review-ready artifact bundle for the claims it found, but it did not produce a complete paper understanding. The quality gate answered "are the extracted claims grounded?" more than "did we cover the paper's main scientific payload?"

This distinction matters. For this paper, a reader would expect at least four top-level evidence families:

- allelic-switch validation
- metabolic/lipid signatures
- CNS transcriptomic and cell-state effects
- neuropathology and cognition in the 5xFAD background

The runtime claimset captured only the transcriptomic family.

## Workflow Implications

### 1. Add a Coverage Contract

Deep-read should have a paper-level coverage contract separate from claim grounding.

For biomedical mechanism papers, a minimum family checklist could include:

- model/system validation
- intervention or perturbation
- primary molecular/cellular readouts
- pathology or phenotype readouts
- behavioral or functional readouts, when present
- safety/translational caveats
- methods and population/model limits

The claimset can pass grounding while still failing coverage.

### 2. Treat Manual Analyst Output as Reviewer Handoff

The manual pass should not replace canonical state. It should become a reviewer handoff artifact or gold-review candidate that can drive a repair loop.

Recommended shape:

- manual claim family checklist
- missing-family findings
- suggested additional claims
- source section anchors
- confidence and promotion warnings

### 3. Add a Coverage Repair Pass

After initial deep-read, run a targeted repair pass when coverage is incomplete.

For this case, repair should add candidate claims for:

- efficient APOE4-to-APOE2 switch validation
- E2-like systemic and cerebral lipid changes
- amyloid reduction
- gliosis reduction
- plaque-associated ApoE reduction
- associative memory improvement
- Morris water maze non-improvement or mixed cognition result
- translational limitation from peripheral lipid liability

### 4. Keep Visual/Table Claims Behind Replay Gates

The visual evidence ledger correctly warned that several table entries were partial or unknown. Any claim depending on figure/table-derived quantitative values should stay in review until replay confirms the visual evidence.

### 5. Preserve Local-First Inference Boundaries

The successful run used `payload_class=local_only`. That is aligned with the PaperPipe inference boundary. If external inference is introduced for coverage repair, the payload should be explicitly classified and minimized.

## Scientific Implications From The Paper

1. The translationally interesting target is astrocyte APOE state replacement, not whole-body APOE2 conversion.
2. APOE2-like biology may be protective for AD phenotypes while creating peripheral lipid liabilities.
3. Astrocytes are likely a leverage point for non-cell-autonomous remodeling of AD-relevant glial and plaque biology.
4. Behavioral benefit is promising but selective; the paper should not be summarized as broad cognitive rescue.
5. The work supports therapeutic plausibility for APOE editing strategies, but only at a preclinical, model-system level.

## Recommended Follow-Up Lane

Recommendation: keep this document as a dated review note. Do not promote it directly into a runtime spec.

Follow-up should split into three lanes:

1. Runtime proposal lane: draft a small RFC or scoped PR plan for a paper-level coverage report artifact that lists expected claim families and marks each as present, missing, or not applicable.
2. Gold/review fixture lane: add this APOE4-to-APOE2 paper as a gold-review candidate or reviewer-handoff fixture to test whether runtime deep-read captures metabolism, neuropathology, and cognition, not only transcriptomics.
3. Non-code process lane: use manual analyst outputs as reviewer handoff artifacts, not canonical replacements, until a coverage repair service exists.

Recommended first action: start with the gold/review fixture lane. It is the least invasive way to preserve the observed gap and can later drive a smaller, better-scoped runtime coverage artifact PR.

Gold-review candidate created:

- `goldset/reviews/apoe4_apoe2_gold_review_candidate/golden_2025_apoe4_apoe2.paper_understanding_gold_candidate.json`
- `goldset/reviews/apoe4_apoe2_gold_review_candidate/README.md`

This candidate remains non-canonical review material. It should not be promoted to accepted fixed gold until a reviewer confirms the source locators and decides whether figure-derived pathology claims need visual replay or bbox-backed evidence.

Deferred runtime action: add a coverage repair command or service path only after the expected claim-family schema and fixture expectations are reviewed. That service should write additive candidate claims without replacing canonical state blindly.

## Verification Notes

No code change is proposed in this note.

Checks from the program-run experiment:

- Runtime import succeeded.
- Deep-read run completed successfully.
- Quality gate was review-ready with no hard fail codes.
- Paper synthesis bundle was generated and listed.

Residual risks:

- Statistical verification was not run.
- Visual/table replay remains partial.
- This comparison is based on one paper and should be treated as a focused workflow signal, not a general benchmark result.
