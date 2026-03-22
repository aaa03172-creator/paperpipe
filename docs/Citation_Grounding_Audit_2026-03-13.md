# Citation Grounding Audit

Status: Working infrastructure audit  
Date: 2026-03-13  
Scope: claim evidence policy, citation-link generation, review queue escalation, and actual grounding behavior in the current deepread path

## 0. Executive Summary

The current repository does have citation-related safeguards, but they are not the strict evidence-resolver model discussed in the H0/H2 planning.

What exists today:

1. evidence-first claim policy
2. unknown-marking when evidence or location metadata is missing
3. review queue escalation for claims that lack location metadata
4. page-based citation link generation for Zotero PDF jumps
5. artifact/meta readiness flags that expose whether claims were produced

What does not exist today:

1. deterministic chunk-based grounding in the active deepread path
2. a `quote in chunk_text` resolver
3. explicit `grounded` / `resolution` status in the claim contract
4. a canonical citation-jump contract built around verified chunk ids

Current judgment:

- the system currently enforces "do not trust unsupported claims"
- it does not yet enforce "trust only machine-verified evidence locations"
- the present runtime is closer to page/location sufficiency than to true grounded citation resolution

## 1. Current Grounding Policy

### 1.1 Evidence is mandatory

`/Users/jangseongjin/paperpipe/src/quality/claimset_policy.py` enforces an evidence-first policy.

Current rules:

- no evidence spans -> claim becomes `unknown=true`, reason `EVIDENCE_MISSING`
- evidence exists but no location metadata -> claim becomes `unknown=true`, reason `EVIDENCE_LOCATION_MISSING`
- claims with location metadata remain eligible as known claims

Assessment:

- this is a real safety policy
- it is a claim-quality gate, not a citation resolver

### 1.2 What counts as a "location"

Current acceptable location signals include any of:

- `page`
- `source_span`
- `char_start` + `char_end`
- `bbox_pdf`
- `bbox_pct`
- `table_id` + `cell_id`

Assessment:

- the policy is intentionally permissive
- page or approximate span is enough to avoid unknown-marking
- this is useful operationally, but weaker than the desired chunk-verified grounding model

### 1.3 Highlight source is inferred, not validated

The same policy layer infers `highlight_source` as:

- `bbox`
- `text_match`
- `approx`

Assessment:

- highlight quality is classified
- evidence truth is not actually verified against document chunks

## 2. Reader Output Behavior

### 2.1 Reader prompt still allows page/source-span grounding

`/Users/jangseongjin/paperpipe/src/agents/reader_agent.py` instructs the model that every claim must include:

- `quote/raw_text`
- a location hint such as `page` or `source_span`

Assessment:

- this is not the same as requiring deterministic `chunk_id + quote`
- current prompt contract still tolerates approximate location strategies

### 2.2 Synthetic chunk ids are still generated

The active reader normalization path synthesizes chunk ids when missing, for example:

- `ev_{idx}`
- `ev_fallback`
- `heuristic_{idx}`

The indexer also currently generates chunk ids with `uuid4()` in `/Users/jangseongjin/paperpipe/src/agents/indexer_agent.py`.

Assessment:

- `chunk_id` exists in shape, but is not trustworthy as a deterministic anchor yet
- current citation grounding cannot depend on chunk identity

### 2.3 Heuristic fallback explicitly creates approximate evidence

When reader extraction fails, the heuristic path still creates claims with:

- sentence-derived evidence
- synthetic chunk id
- `highlight_source="text_match"`
- `unknown=true`

Assessment:

- this is a pragmatic fallback
- it is correctly marked as uncertain
- it reinforces that the active system is evidence-aware, not strictly grounded

## 3. Citation Jump Reality In The Current Product

### 3.1 Exporter builds page-based jumps

`/Users/jangseongjin/paperpipe/src/exporter.py` generates Zotero links from `EvidenceSpan.page`.

Current behavior:

- `EvidenceSpan.page` is treated as 0-indexed
- exporter converts it to Zotero `page={page + 1}`
- markdown renders `quote="..."`, `page_num=...`, and optional Zotero open-pdf link

Assessment:

- current citation jump is explicitly page-centric
- this aligns with the present product reality better than any chunk-verified interpretation

### 3.2 Missing location metadata escalates to review queue

Exporter follow-up logic pushes `NEEDS_EVIDENCE_LINK` when claims have evidence but location metadata is missing.

Assessment:

- this is the main current operational safeguard for citation quality
- the system does not auto-resolve the citation; it escalates it

### 3.3 Obsidian/deepread rendering still uses first evidence span + page

Primary rendering surfaces still do:

- choose `claim.evidence_spans[0]`
- display quote/raw_text
- display page or section hint

Assessment:

- citation UX is optimized around first-span summary, not resolver confidence

## 4. What The Current System Actually Guarantees

### 4.1 It guarantees unsupported claims are downgraded

This is the strongest current guarantee.

If a claim has no evidence or no location metadata, it is:

- marked `unknown`
- confidence-capped
- eligible for review queue escalation

### 4.2 It does not guarantee evidence-location correctness

A claim can stay non-unknown if it has any acceptable location shape, even if:

- `chunk_id` is synthetic
- `page` was guessed or normalized by the model
- `quote` was shortened heuristically
- there was no post-hoc text match against chunks

Assessment:

- this is the central gap between current implementation and the planned grounding contract

### 4.3 It does not guarantee deterministic citation jumps

Because chunk ids are not deterministic and no resolver verifies quote membership, current citation links rely on whatever location metadata survived extraction.

Assessment:

- page jumps can work and are already useful
- they are not the same as verified evidence jumps

## 5. What Tests Confirm Today

Verified surfaces include:

- `/Users/jangseongjin/paperpipe/tests/test_claimset_policy.py`
- `/Users/jangseongjin/paperpipe/tests/test_claimset_export_review_queue_qa.py`
- `/Users/jangseongjin/paperpipe/tests/test_deepread_note_writer.py`
- `/Users/jangseongjin/paperpipe/tests/test_exporter.py`

These tests confirm:

- evidence-free claims become `unknown`
- location-free claims become `unknown`
- exporter emits page-based Zotero links when page is present
- review queue receives `NEEDS_EVIDENCE_LINK` for missing location metadata
- deepread markdown shows evidence text and page/section hints

What they do not confirm:

- deterministic chunk grounding
- quote validation against chunk text
- `grounded/resolution` semantics
- stable citation jumps across reruns

## 6. Main Gaps Relative To The Planned Model

### 6.1 No deterministic chunk contract in the active path

The current indexer and reader path do not provide a stable chunk identity backbone for citation grounding.

Priority: P0

### 6.2 No evidence resolver

There is no active function that takes:

- claim evidence
- chunk set
- quote text

and returns:

- verified page
- `grounded=true/false`
- `resolution=...`

Priority: P0

### 6.3 Citation readiness is inferred from presence, not verification

`claimset_readiness` and related badges in bootstrap metadata reflect whether claims exist, not whether citations were machine-verified.

Priority: P1

### 6.4 UX surfaces still imply stronger grounding than the system actually provides

Because the product already shows quotes, pages, and PDF links, users can reasonably assume those anchors were verified more strongly than they were.

Priority: P1

## 7. Recommended Next Sequence

### Step 1. Keep current conservative policy

Do not remove the current unknown-marking and review-queue safeguards.

They are the main working defense today.

### Step 2. Make chunk ids deterministic before resolver work

Without deterministic chunk ids, a grounding resolver cannot become reliable.

### Step 3. Add a resolver layer on top of current claimsets

Recommended minimum resolver behavior:

- load chunk text by chunk id
- verify `quote` membership in chunk text
- fall back to normalized match only if necessary
- emit `grounded` and `resolution`
- derive page from chunk, not from model text

### Step 4. Make citation UX reflect certainty explicitly

Once resolver semantics exist, viewer/export surfaces should distinguish:

- verified grounding
- approximate page hint
- unresolved citation

## 8. Final Judgment

Current citation grounding is pragmatic but not yet rigorous.

The most accurate description of the present system is:

- evidence-required
- location-aware
- page-link capable
- review-queue backed
- not yet chunk-verified

This means the next citation-grounding PR should focus on introducing a resolver and deterministic chunk ids, not on adding more page-link UX alone.
