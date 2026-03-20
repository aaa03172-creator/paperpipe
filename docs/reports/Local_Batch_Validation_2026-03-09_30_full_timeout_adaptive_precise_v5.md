# Local Batch Validation Full (2026-03-09, sample=30)

- Scope: ingest + reader + stats + anchor context (step-level timeout worker)
- Sample size: 30
- Per-doc timeout base: 240s
- Timeout policy: adaptive
- Timeout retry limit: 2
- Effective doc timeout range: 262~720s
- Completed: 22
- Partial: 6
- Timeout: 2
- Timeout recovered by retry: 0
- Error: 0
- Ingest failed: 0
- Total checks: 49
- no_api ratio (completed+partial): 100.00%
- no_table_data ratio (completed+partial): 59.18%
- doc_id DOI ratio (completed+partial): 100.00%
- anchor no_doi ratio (completed+partial): 0.00%

## Reader Status Distribution
- error: 4
- ok: 24

## Stats Status Distribution
- error: 6
- ok: 18
- skipped_no_claims: 4

## Anchor API Status Distribution
- ok: 27
- unavailable: 1

## Table Failure Taxonomy Counts
- DEGENERATE_SHAPE: 13
- NO_TABLE_FOUND: 14

## Per-Document
- 1411.2441.pdf: status=completed, elapsed=71.363s, doc_timeout=396s, retries=0, reader=ok, stats=ok, checks=2, api=unavailable
- Arnsten 등 - 2012 - Neuromodulation of Thought Flexibilities and Vulnerabilities in Prefrontal Cortical Network Synapse.pdf: status=completed, elapsed=58.427s, doc_timeout=333s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Barulli 및 Stern - 2013 - Efficiency, capacity, compensation, maintenance, plasticity emerging concepts in cognitive reserve.pdf: status=completed, elapsed=81.954s, doc_timeout=263s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Benedict 등 - 2020 - Cognitive impairment in multiple sclerosis clinical management, MRI, and therapeutic avenues.pdf: status=timeout, elapsed=294.012s, doc_timeout=294s, retries=0, reader=ok, stats=not_run, checks=0, api=not_run
- Bialystok 등 - 2012 - Bilingualism consequences for mind and brain.pdf: status=completed, elapsed=86.619s, doc_timeout=267s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Chandra 등 - 2023 - The gut microbiome in Alzheimer’s disease what we know and what remains to be explored.pdf: status=completed, elapsed=46.229s, doc_timeout=316s, retries=0, reader=ok, stats=ok, checks=1, api=ok
- Chiaravalloti 및 DeLuca - Cognitive impairment in multiple sclerosis.pdf: status=completed, elapsed=73.783s, doc_timeout=262s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Colombo 등 - 2021 - Microbiota-derived short chain fatty acids modulate microglia and promote Aβ plaque deposition.pdf: status=completed, elapsed=239.754s, doc_timeout=355s, retries=0, reader=ok, stats=ok, checks=4, api=ok
- Coric 등 - 2015 - Targeting Prodromal Alzheimer Disease With Avagacestat A Randomized Clinical Trial.pdf: status=partial, elapsed=237.706s, doc_timeout=262s, retries=0, reader=ok, stats=error, checks=0, api=ok
- Craft 등 - 2020 - Safety, Efficacy, and Feasibility of Intranasal Insulin for the Treatment of Mild Cognitive Impairme.pdf: status=partial, elapsed=214.834s, doc_timeout=264s, retries=0, reader=ok, stats=error, checks=0, api=ok
- DeCarli - 2003 - Mild cognitive impairment prevalence, prognosis, aetiology, and treatment.pdf: status=completed, elapsed=79.555s, doc_timeout=262s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Dubois 등 - 2024 - Alzheimer Disease as a Clinical-Biological Construct—An International Working Group Recommendation.pdf: status=partial, elapsed=221.287s, doc_timeout=262s, retries=0, reader=ok, stats=error, checks=0, api=ok
- Dubois 및 Albert - 2004 - Amnestic MCI or prodromal Alzheimer's disease.pdf: status=completed, elapsed=97.091s, doc_timeout=262s, retries=0, reader=error, stats=skipped_no_claims, checks=0, api=ok
- Dubois 등 - 2021 - Clinical diagnosis of Alzheimer's disease recommendations of the International Working Group.pdf: status=completed, elapsed=240.985s, doc_timeout=262s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Fenton 등 - 2018 - Advances in Biomaterials for Drug Delivery.pdf: status=completed, elapsed=80.634s, doc_timeout=522s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Finn 등 - 2018 - A Single Administration of CRISPRCas9 Lipid Nanoparticles Achieves Robust and Persistent In Vivo Ge.pdf: status=completed, elapsed=92.664s, doc_timeout=302s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Fowler 등 - 2025 - Tau filaments are tethered within brain extracellular vesicles in Alzheimer’s disease.pdf: status=partial, elapsed=269.361s, doc_timeout=720s, retries=0, reader=ok, stats=error, checks=0, api=ok
- Furtado 등 - 2018 - Overcoming the Blood–Brain Barrier The Role of Nanomaterials in Treating Neurological Diseases.pdf: status=completed, elapsed=70.06s, doc_timeout=720s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Grande 등 - 2025 - Blood-based biomarkers of Alzheimer’s disease and incident dementia in the community.pdf: status=completed, elapsed=156.084s, doc_timeout=519s, retries=0, reader=error, stats=skipped_no_claims, checks=0, api=ok
- Hansson 등 - 2022 - The Alzheimer's Association appropriate use recommendations for blood biomarkers in Alzheimer's dise.pdf: status=completed, elapsed=128.502s, doc_timeout=274s, retries=0, reader=error, stats=skipped_no_claims, checks=0, api=ok
- Hansson 등 - 2023 - Blood biomarkers for Alzheimer’s disease in clinical practice and trials.pdf: status=partial, elapsed=251.161s, doc_timeout=326s, retries=0, reader=ok, stats=error, checks=0, api=ok
- Hansson 등 - 2018 - CSF biomarkers of Alzheimer's disease concord with amyloid‐β PET and predict clinical progression A.pdf: status=partial, elapsed=220.831s, doc_timeout=305s, retries=0, reader=ok, stats=error, checks=0, api=ok
- Hu 등 - 2025 - Poly(Lactic Acid) Recent Stereochemical Advances and New Materials Engineering.pdf: status=completed, elapsed=61.844s, doc_timeout=353s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Jessen 등 - 2020 - The characterisation of subjective cognitive decline.pdf: status=completed, elapsed=220.273s, doc_timeout=277s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Johnson 등 - 2022 - Large-scale deep multi-layer analysis of Alzheimer’s disease brain reveals strong proteomic disease-.pdf: status=completed, elapsed=272.158s, doc_timeout=720s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Karikari 등 - 2020 - Blood phosphorylated tau 181 as a biomarker for Alzheimer's disease a diagnostic performance and pr.pdf: status=completed, elapsed=259.348s, doc_timeout=343s, retries=0, reader=ok, stats=ok, checks=5, api=ok
- Kistemaker 등 - 2025 - Vascularized human brain organoids current possibilities and prospects.pdf: status=timeout, elapsed=277.009s, doc_timeout=277s, retries=0, reader=ok, stats=not_run, checks=0, api=not_run
- Kowalski 및 Mulak - 2019 - Brain-Gut-Microbiota Axis in Alzheimer’s Disease.pdf: status=completed, elapsed=126.985s, doc_timeout=262s, retries=0, reader=error, stats=skipped_no_claims, checks=0, api=ok
- Lee 등 - 2022 - Deep learning-based brain age prediction in normal aging and dementia.pdf: status=completed, elapsed=320.561s, doc_timeout=720s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Liu 등 - 2020 - Gut Microbiota and Dysbiosis in Alzheimer’s Disease Implications for Pathogenesis and Treatment.pdf: status=completed, elapsed=71.445s, doc_timeout=299s, retries=0, reader=ok, stats=ok, checks=2, api=ok
