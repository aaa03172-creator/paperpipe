# Local Batch Validation Full (2026-03-09, sample=30)

- Scope: ingest + reader + stats + anchor context (step-level timeout worker)
- Sample size: 30
- Per-doc timeout base: 240s
- Timeout policy: adaptive
- Timeout page weight: 10.0s/page
- Timeout retry limit: 2
- Effective doc timeout range: 292~840s
- Completed: 29
- Partial: 1
- Timeout: 0
- Timeout recovered by retry: 0
- Error: 0
- Ingest failed: 0
- Total checks: 65
- no_api ratio (completed+partial): 100.00%
- no_table_data ratio (completed+partial): 47.69%
- doc_id DOI ratio (completed+partial): 100.00%
- anchor no_doi ratio (completed+partial): 0.00%

## Reader Status Distribution
- ok: 30

## Stats Status Distribution
- error: 1
- ok: 29

## Anchor API Status Distribution
- ok: 29
- unavailable: 1

## Table Failure Taxonomy Counts
- DEGENERATE_SHAPE: 14
- NO_TABLE_FOUND: 14

## Per-Document
- 1411.2441.pdf: status=completed, elapsed=58.482s, doc_timeout=676s, retries=0, reader=ok, stats=ok, checks=2, api=unavailable
- Arnsten 등 - 2012 - Neuromodulation of Thought Flexibilities and Vulnerabilities in Prefrontal Cortical Network Synapse.pdf: status=completed, elapsed=90.101s, doc_timeout=503s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Barulli 및 Stern - 2013 - Efficiency, capacity, compensation, maintenance, plasticity emerging concepts in cognitive reserve.pdf: status=completed, elapsed=88.707s, doc_timeout=343s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Benedict 등 - 2020 - Cognitive impairment in multiple sclerosis clinical management, MRI, and therapeutic avenues.pdf: status=completed, elapsed=282.796s, doc_timeout=414s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Bialystok 등 - 2012 - Bilingualism consequences for mind and brain.pdf: status=completed, elapsed=89.201s, doc_timeout=377s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Chandra 등 - 2023 - The gut microbiome in Alzheimer’s disease what we know and what remains to be explored.pdf: status=completed, elapsed=76.835s, doc_timeout=526s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Chiaravalloti 및 DeLuca - Cognitive impairment in multiple sclerosis.pdf: status=completed, elapsed=77.826s, doc_timeout=392s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Colombo 등 - 2021 - Microbiota-derived short chain fatty acids modulate microglia and promote Aβ plaque deposition.pdf: status=completed, elapsed=151.922s, doc_timeout=585s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Coric 등 - 2015 - Targeting Prodromal Alzheimer Disease With Avagacestat A Randomized Clinical Trial.pdf: status=completed, elapsed=245.167s, doc_timeout=362s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Craft 등 - 2020 - Safety, Efficacy, and Feasibility of Intranasal Insulin for the Treatment of Mild Cognitive Impairme.pdf: status=completed, elapsed=208.022s, doc_timeout=374s, retries=0, reader=ok, stats=ok, checks=1, api=ok
- DeCarli - 2003 - Mild cognitive impairment prevalence, prognosis, aetiology, and treatment.pdf: status=completed, elapsed=69.207s, doc_timeout=332s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Dubois 등 - 2024 - Alzheimer Disease as a Clinical-Biological Construct—An International Working Group Recommendation.pdf: status=completed, elapsed=271.687s, doc_timeout=342s, retries=0, reader=ok, stats=ok, checks=1, api=ok
- Dubois 및 Albert - 2004 - Amnestic MCI or prodromal Alzheimer's disease.pdf: status=completed, elapsed=71.443s, doc_timeout=292s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Dubois 등 - 2021 - Clinical diagnosis of Alzheimer's disease recommendations of the International Working Group.pdf: status=completed, elapsed=196.764s, doc_timeout=392s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Fenton 등 - 2018 - Advances in Biomaterials for Drug Delivery.pdf: status=completed, elapsed=50.81s, doc_timeout=812s, retries=0, reader=ok, stats=ok, checks=1, api=ok
- Finn 등 - 2018 - A Single Administration of CRISPRCas9 Lipid Nanoparticles Achieves Robust and Persistent In Vivo Ge.pdf: status=completed, elapsed=42.131s, doc_timeout=402s, retries=0, reader=ok, stats=ok, checks=1, api=ok
- Fowler 등 - 2025 - Tau filaments are tethered within brain extracellular vesicles in Alzheimer’s disease.pdf: status=completed, elapsed=149.56s, doc_timeout=840s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Furtado 등 - 2018 - Overcoming the Blood–Brain Barrier The Role of Nanomaterials in Treating Neurological Diseases.pdf: status=completed, elapsed=54.33s, doc_timeout=840s, retries=0, reader=ok, stats=ok, checks=1, api=ok
- Grande 등 - 2025 - Blood-based biomarkers of Alzheimer’s disease and incident dementia in the community.pdf: status=completed, elapsed=395.864s, doc_timeout=709s, retries=0, reader=ok, stats=ok, checks=1, api=ok
- Hansson 등 - 2022 - The Alzheimer's Association appropriate use recommendations for blood biomarkers in Alzheimer's dise.pdf: status=completed, elapsed=164.383s, doc_timeout=454s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Hansson 등 - 2023 - Blood biomarkers for Alzheimer’s disease in clinical practice and trials.pdf: status=completed, elapsed=427.498s, doc_timeout=466s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Hansson 등 - 2018 - CSF biomarkers of Alzheimer's disease concord with amyloid‐β PET and predict clinical progression A.pdf: status=completed, elapsed=258.022s, doc_timeout=425s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Hu 등 - 2025 - Poly(Lactic Acid) Recent Stereochemical Advances and New Materials Engineering.pdf: status=completed, elapsed=68.744s, doc_timeout=503s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Jessen 등 - 2020 - The characterisation of subjective cognitive decline.pdf: status=completed, elapsed=238.292s, doc_timeout=357s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Johnson 등 - 2022 - Large-scale deep multi-layer analysis of Alzheimer’s disease brain reveals strong proteomic disease-.pdf: status=completed, elapsed=390.705s, doc_timeout=840s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Karikari 등 - 2020 - Blood phosphorylated tau 181 as a biomarker for Alzheimer's disease a diagnostic performance and pr.pdf: status=completed, elapsed=272.381s, doc_timeout=463s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Kistemaker 등 - 2025 - Vascularized human brain organoids current possibilities and prospects.pdf: status=partial, elapsed=372.619s, doc_timeout=387s, retries=0, reader=ok, stats=error, checks=0, api=ok
- Kowalski 및 Mulak - 2019 - Brain-Gut-Microbiota Axis in Alzheimer’s Disease.pdf: status=completed, elapsed=347.79s, doc_timeout=392s, retries=0, reader=ok, stats=ok, checks=3, api=ok
- Lee 등 - 2022 - Deep learning-based brain age prediction in normal aging and dementia.pdf: status=completed, elapsed=362.945s, doc_timeout=840s, retries=0, reader=ok, stats=ok, checks=2, api=ok
- Liu 등 - 2020 - Gut Microbiota and Dysbiosis in Alzheimer’s Disease Implications for Pathogenesis and Treatment.pdf: status=completed, elapsed=83.717s, doc_timeout=479s, retries=0, reader=ok, stats=ok, checks=2, api=ok
