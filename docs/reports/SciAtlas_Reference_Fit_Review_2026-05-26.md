# SciAtlas Reference Fit Review

Status: Reference intake review
Date: 2026-05-26
Owner: Search/runtime/product maintainers
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Operating note: `docs/PaperPipe_Minimum_Operating_Principles.md`

Reference sources:
- SciAtlas paper: https://arxiv.org/abs/2605.22878
- SciAtlas GitHub: https://github.com/zjunlp/SciAtlas
- Korean summary: https://jkf87.github.io/sciatlas-knowledge-graph-automated-research-2026-05-26

Scope:
- Evaluate SciAtlas as an external reference for PaperPipe/Lattice.
- Decide what, if anything, should influence current product/runtime work.
- Preserve PaperPipe's paper/job/artifact, local-first, schema-backed evidence boundaries.

Non-goals:
- No SciAtlas runtime adoption in this review.
- No dependency install.
- No API token registration.
- No graph database migration.
- No replacement of current parser, reader, grounding, Research DNA, or Obsidian/export paths.

## Executive Summary

SciAtlas is strategically relevant, but not a direct runtime candidate today.

Its strongest idea is that a graph can serve as a cognitive map for scientific navigation. That overlaps with PaperPipe's own instinct: scientific work should not be a pile of opaque LLM answers; it should preserve visible relationships among sources, evidence, review state, downstream artifacts, and operator decisions.

The difference is ownership and layer.

SciAtlas is a global, hosted, OpenAlex-scale academic knowledge graph for discovery. PaperPipe/Lattice is a local-first, paper-centered biomedical evidence workspace whose canonical truth is schema-backed state, run artifacts, and source/evidence lineage.

Current classification:

`reference only`

The right use is to learn from SciAtlas's retrieval topology, author discovery, idea-grounding workflows, and artifact discipline. The wrong use is to turn PaperPipe into a broad external graph platform or to let graph results outrank local canonical evidence.

## Current Bottleneck

PaperPipe already has strong paper-local evidence handling, `Research DNA` search-design state, and bounded rerank/eval sidecars. The current gap is broader scientific map support around a research direction: graph-aware prior-art discovery, related author discovery, idea positioning, and trend synthesis outside the user's current paper set.

This gap currently lives nearest to:
- `Research DNA`: reproducible search design, screening, rerank, and refine loop.
- Paper Notes related papers: local shared tags and structured signals.
- Future retrieval observability: why a source/paper/author was suggested.

It should not be solved by changing canonical paper state first.

## Classification

`reference only`

Why not `direct candidate`:
- The public GitHub repo is mainly a hosted API client/CLI and agent-skill pack, not a self-contained local graph deployment.
- It requires a SciAtlas API token and sends queries to a hosted endpoint.
- The graph backend assumes large Neo4j/OpenAlex-scale infrastructure.
- Its downstream tasks generate useful reports, but the paper itself says downstream benchmarks and quantitative evaluation remain future work.
- It overlaps with PaperPipe's existing `Research DNA` and retrieval lanes enough that direct adoption would risk duplicate ownership.

Why it is still important:
- It sharpens the product language around graph-backed discovery.
- It gives concrete patterns for tri-path recall, graph reranking, author discovery, and idea grounding.
- It validates the direction of turning search intent into reproducible artifacts instead of one-off chat outputs.

## What SciAtlas Actually Is

SciAtlas combines three layers:

1. A large scientific KG
   - 43.30M papers
   - 109.70M authors
   - 3.76M keywords
   - 157M entities total
   - about 3B relations
   - 26 fields, 4 domains, paper/author/institution/keyword/source/topic/field/subfield/domain nodes

2. A graph-aware retrieval method
   - keyword matching: LLM-extracted query keywords plus exact/vector keyword matching
   - semantic matching: query-to-title/abstract embedding retrieval plus reranking
   - title matching: exact/fuzzy title anchors from explicit titles or references
   - local 2-hop subgraph expansion
   - Random Walk with Restart
   - final rank combining initial relevance, graph topological support, and citation importance

3. User-facing CLI/client workflows
   - paper search
   - literature review
   - idea grounding
   - idea evaluation
   - idea generation
   - trend report
   - related author retrieval
   - researcher review/profile
   - JSON/Markdown artifacts under `runs/<run_id>/`

The GitHub repo README frames it as a lightweight client over a hosted SciAtlas API rather than a local Neo4j distribution. The repo also ships portable agent skills that use `search-papers` as the base retrieval primitive and ask the agent to synthesize downstream reports from saved artifacts.

## Current PaperPipe Reality

PaperPipe/Lattice is already intentionally not a broad graph platform.

Current canonical boundaries:
- `docs/Lattice_v3_Master_Spec.md`: paper-first, job/run/artifact-first, FastAPI-first, local-first.
- `docs/PaperPipe_Minimum_Operating_Principles.md`: canonical truth remains schema-backed and paper/job/artifact-scoped.
- `docs/RESEARCH_DNA.md`: search design is a bounded asset with `DRAFT -> PILOT -> LOCKED`, pilot/screening/refine logs, and advisory rerank/gate artifacts.
- `docs/WEB_VIEWER.md`: paper note detail exposes local structured state, related papers, references, and context trace; Research DNA is not currently a viewer route.
- `docs/PaperPipe_UI_GRAMMAR.md`: avoid fake graph truth; prefer source chain, derived from, used by, blocked by, stale impact before broad graph visualization.

Current implementation anchors:
- `src/indexer.py`: local Chroma index over approved/indexed local paper records.
- `backend/routers/paper_notes.py`: related papers are computed from local shared tags and structured signals.
- `src/profiles/research_dna_schema.py`: Research DNA owns search-design state and advisory rerank artifacts.
- `backend/main.py`: Research DNA APIs are thin wrappers around service/store logic.

This means SciAtlas should enter only as an external discovery/reference layer, never as a replacement owner.

## Comparison To PaperPipe

| Dimension | SciAtlas | PaperPipe/Lattice | Judgment |
| --- | --- | --- | --- |
| Primary object | Global academic graph | Local paper/job/artifact state | Complementary, different layer |
| Data source | OpenAlex-scale KG, hosted API | Zotero/PDF/local artifacts/Obsidian mirror | Do not merge ownership |
| Retrieval | Keyword + semantic + title + graph propagation | PubMed/OpenAlex/local search, Research DNA pilot/rerank, local index | Learn from retrieval topology |
| Evidence truth | Graph-backed paper/author/keyword relations | Claim/evidence/source lineage with structured state | PaperPipe truth boundary is stricter |
| Output | Markdown reports and JSON artifacts | Pydantic artifacts, sidecars, review/export surfaces | Artifact discipline overlaps well |
| Operator role | Query and consume reports | Human review, correction, screening, promotion | PaperPipe is more review-heavy |
| Infrastructure | Hosted API, Neo4j backend | Local-first FastAPI/runtime | Direct adoption conflicts |
| Product stage | Broad scientific discovery assistant | Biomedical evidence workspace | Use as discovery/reference layer only |

## What We Should Adopt

### 1. Graph-aware retrieval as an eval-only Research DNA experiment

What to adopt:
- Tri-path retrieval concept: keyword anchors, semantic neighbors, title/reference anchors.
- Graph/topology support as an advisory score component.
- Score breakdowns and path explanations.

Where it fits:
- `Research DNA` rerank/eval sidecar.
- A future `external_discovery_comparison.json` sibling artifact for a pilot run.

Safe shape:
- Input is a public query/topic only.
- Output is non-canonical.
- Original screening queue remains owner.
- SciAtlas result can be compared against existing `include@k`, MRR, MAP, nDCG, precision proxy, or external benchmark recall.

Do not:
- Replace `screening_queue.jsonl`.
- Promote SciAtlas graph ranking as runtime default.
- Send private PDF text, private note text, local paths, or unpublished lab context.

### 2. Related author discovery

What to adopt:
- Author as a first-class discovery result for a research direction.
- Ranking authors by graph proximity plus citation/position signals.
- Support papers per author, not just author names.

Why this is the best first pilot:
- Low blast radius.
- Does not alter paper evidence truth.
- High product value for literature review and collaboration scouting.

Safe PaperPipe lane:
- `Research DNA` read-only companion report: `related_authors_sidecar.json`.
- Human-facing report states: "candidate authors for exploration", not "recommended collaborators" or "authoritative experts".

### 3. Idea grounding and idea positioning

What to adopt:
- Treat an idea as a query and retrieve similar prior work.
- Split output into similar points, different points, and evidence papers.
- Use the result as a novelty/framing aid.

Where it fits:
- Future Research DNA or Project Memory-adjacent draft lane.
- Non-canonical compiled knowledge artifact.

Important boundary:
- The output can support thinking; it cannot validate novelty alone.
- It must be clearly labeled as literature-grounded draft positioning.

### 4. Trend report as background synthesis

What to adopt:
- Chronological grouping of representative papers.
- Explicit distinction between stage summary, current bottlenecks, and possible future directions.

Where it fits:
- A `Research DNA` report artifact after a pilot/search run.
- Not a default paper note claim.

Do not:
- Call it prediction unless the method has measurable predictive validation.
- Use trends to overwrite evidence-backed paper state.

### 5. Reusable keyword extraction constraints

What to adopt:
- Avoid paper-specific marketing phrases as keywords.
- Prefer reusable problem/method/evaluation phrases.
- Treat generated keywords as derived and reviewable.

This is useful for PaperPipe because it directly improves search-design stability and avoids overfitting to paper title branding.

Where it fits:
- Research DNA query refinement suggestions.
- Local paper note structured signals, only when provenance and review state are clear.

### 6. Artifact discipline

What to adopt:
- `request.json`, `response.json`, `summary.txt`, `report.md` style run bundles.
- Keep reproducible plan/request/response/report together.

PaperPipe already does this in a more schema-backed way. The takeaway is not new storage, but stronger consistency for any future external-discovery sidecar.

## What SciAtlas Does Better Than PaperPipe Today

1. Global map breadth
   - It spans across disciplines and can traverse paper, author, institution, keyword, citation, relatedness, and taxonomy edges.
   - PaperPipe is intentionally local/paper-centered and does not currently provide global scientific topology.

2. Author discovery
   - SciAtlas has a clear author retrieval/profile story.
   - PaperPipe's current Research DNA story is stronger for screening/refine but weaker for author/collaborator exploration.

3. Idea positioning vocabulary
   - The "similar point / different point / evidence paper" output is productively concrete.
   - PaperPipe can borrow this as a draft review language without adopting their runtime.

4. Retrieval score decomposition
   - Initial relevance, graph support, and citation importance are explicitly separated.
   - PaperPipe's current related-paper surfaces are simpler and more local.

5. Agent-friendly reference packaging
   - The agent-skill pack is clear about bootstrapping, running retrieval, reading artifacts, and synthesizing downstream work.
   - PaperPipe should not copy their skills directly, but the task decomposition is useful.

## What PaperPipe Does Better

1. Trust boundaries
   - PaperPipe distinguishes raw source, canonical structured state, review/gate artifacts, compiled knowledge, and exports.
   - SciAtlas reports are useful but easier to over-trust if imported directly.

2. Local-first ownership
   - PaperPipe keeps canonical state local and recoverable.
   - SciAtlas's public workflow depends on hosted API access and external tokens.

3. Human review loops
   - Research DNA has explicit screening, approval, refine, lock, and advisory-only rerank semantics.
   - SciAtlas examples are more discovery/report oriented.

4. Biomedical evidence discipline
   - PaperPipe's core loop is PDF/evidence/ClaimSet/stats/artifact-oriented.
   - SciAtlas is stronger at discovery topology than paper-internal evidence verification.

5. Runtime contract discipline
   - PaperPipe has Pydantic schemas, FastAPI wrappers, and idempotent export constraints.
   - SciAtlas client artifacts are useful, but they are not PaperPipe-compatible contracts by default.

## What Does Not Fit Our Direction

### Broad graph database as current runtime truth

Do not introduce a Neo4j-like global graph as a canonical PaperPipe owner.

Reason:
- Current product is paper/job/artifact scoped.
- A broad graph would compete with `src/db_utils.py`, `StructuredPaperState`, Research DNA, and sidecar ownership.
- It would increase operator burden and migration risk before the current surfaces are stable.

### Hosted API as default retrieval dependency

Do not make SciAtlas API a default PaperPipe dependency.

Reason:
- PaperPipe is local-first.
- External inference/search payloads must be classified.
- Private PDFs, local notes, local paths, and unpublished context cannot be sent as routine discovery payload.

### Graph visualization before route-level state grammar

Do not build a decorative graph UI from this reference.

Reason:
- PaperPipe's UI grammar explicitly warns against fake graph truth.
- Relationship summaries are safer than broad graph visuals until the underlying data contract is explicit.

### Idea generation as an autonomous product promise

Do not position PaperPipe as autonomously generating validated biomedical research ideas.

Reason:
- Novelty, feasibility, and soundness require human review and domain constraints.
- SciAtlas's own downstream application examples are qualitative, and benchmark/evaluation is future work.

### Importing SciAtlas agent skills into `.codex/skills/`

Do not copy SciAtlas skills into PaperPipe's runtime or Codex local skills without policy review.

Reason:
- PaperPipe's scientific skills pack is policy-gated.
- SciAtlas skills assume external API setup and hosted retrieval.
- Their agent skills are useful as design references, not drop-in project-approved skills.

## Product Psychology Review

This is a product-direction review, not a UI implementation. No UI artifact is changed here. Still, SciAtlas touches search, related recommendations, author discovery, and research journey framing, so the product psychology guardrails apply.

### Quick Review (5 min)

- Choice count: expose at most one external-discovery action at first, preferably `Find related authors` or `Compare external discovery`.
- Benefit: frame the feature as "broaden the map around this Research DNA", not "trust the graph".
- Next action: results should lead to review/screening, not automatic promotion.
- Feedback: every run should show payload class, source, query, and non-canonical status.
- Ethics: avoid making graph scores look like scientific truth or author authority.

### Full Review

P0:
- Do not make SciAtlas a canonical truth store.
- Do not send private paper text, local paths, lab notes, or unpublished user data to the hosted API.
- Do not add graph-truth language or visual graph authority without a schema/API owner.
- Do not auto-promote idea novelty, trends, or author recommendations.

P1:
- Make external discovery a review-first sidecar under Research DNA.
- Show source chain, query, retrieved papers/authors, and skipped/rejected reasons.
- Keep original local queue and SciAtlas-derived queue separate.
- Use human-readable recommendation summaries before any graph visualization.

P2:
- Consider a future external-discovery panel only after the sidecar contract and eval metrics are stable.
- Later, support trend/idea reports as compiled knowledge with `canonical_status=non_canonical`.

6P storyboard context:
- Problem: a researcher has a bounded biomedical question but worries their local paper set misses adjacent fields, authors, or emerging directions.
- Emotion: they want confidence that they are not trapped in a narrow search bubble.
- Action: they run a bounded external-discovery check from a Research DNA profile.
- Struggle: external search can produce impressive but unreviewed suggestions.
- Attempt: PaperPipe presents graph-backed suggestions as reviewable sidecars with provenance and payload boundaries.
- Happy ending: the researcher finds a useful adjacent author/paper/positioning clue and routes it into screening without confusing it with canonical evidence.

BMAP:
- Motivation: high for literature review, collaborator discovery, and idea positioning.
- Ability: high only if the action is one click from an existing Research DNA run and outputs are compact.
- Prompt: best prompt is after a pilot/search run, when the user sees gaps or needs broader context.

B.I.A.S:
- Block: too many SciAtlas tasks at once will overload users; start with one task.
- Interpret: label it "external map check" or "related-author exploration", not "validated graph truth".
- Act: default action should be "review candidates", not "adopt ranking".
- Store: save run artifacts and make the non-canonical boundary visible on reopen.

Peak-End:
- Peak: user sees a surprising but well-explained adjacent author/paper with support papers.
- Pit: a polished generated report makes weak evidence look decisive.
- Transition: local Research DNA run -> external sidecar -> screening queue review should preserve boundary labels.
- End: run ends with candidates, payload class, source links, and next review action.

Ethics:
- Regret: acceptable if users can see exactly what was sent and why results are non-canonical.
- Black Mirror: risk if graph centrality becomes hidden prestige ranking for authors or institutions.
- In Real-Life: the product should behave like a careful librarian, not a hype-driven recommendation engine.

## Scenario-by-Scenario Adoption Matrix

| SciAtlas scenario | Fit | Adopt now? | Safe PaperPipe form | Notes |
| --- | --- | --- | --- | --- |
| Literature review | High | Not direct | Research DNA external-discovery comparison | Useful if measured against existing screening/eval metrics |
| Idea positioning | High | Pilot later | Non-canonical idea-grounding sidecar | Keep as draft; do not claim novelty validation |
| Idea generation | Medium | Defer | Compiled knowledge draft only | High over-trust risk; needs strong human review |
| Trend prediction | Medium | Defer | Chronological trend synthesis sidecar | Rename as trend synthesis unless validated prediction exists |
| Related author search | High | Best first pilot | `related_authors_sidecar.json` | Low canonical risk and clear user value |
| Researcher profiling | Medium | Later | Public author profile report | Watch same-name ambiguity and prestige bias |

## Safest Insertion Point

Preferred path:

1. Evaluation harness or benchmark fixture.
2. Sidecar artifact generator.
3. Optional explicit tool action.
4. Behind-flag runtime pilot only after measured value.

Concrete v0:

- Add a manual/offline comparison note first.
- Then, if approved, define a `ResearchDNAExternalDiscoverySidecar` schema.
- The sidecar should include:
  - `schema_version`
  - `layer=compiled_knowledge` or `review_gate_artifact`
  - `canonical_status=non_canonical`
  - `source_provider=sciatlas`
  - `payload_class`
  - request/query text
  - raw response path
  - normalized candidates
  - score breakdown when available
  - warnings
  - source URLs
  - generated_at
  - linked `dna_id`, `run_id`, `query_version`

No API call should happen without explicit operator configuration and payload classification.

## Smallest Pilot

Recommended first pilot:

`Research DNA related-author external map check`

Goal:
- For one existing Research DNA topic, compare SciAtlas related authors against the current local candidate pool and human expectations.

Inputs:
- Public topic/query text only.
- Optional public title anchors only.
- No private PDFs, note text, local paths, or unpublished data.

Outputs:
- `related_authors_sidecar.json`
- `related_authors_report.md`
- `external_discovery_eval.json`

Metrics:
- number of useful new authors found
- support papers per author
- false-positive burden
- overlap with existing candidate papers
- whether the result changes screening/search decisions
- operator time saved or added

Hard stop:
- If results are mostly generic celebrity authors, defer.
- If payload boundary requires private notes/PDF text, reject.
- If there is no measurable improvement over current PubMed/OpenAlex/Research DNA discovery, keep reference-only.

## Do Not Rewrite These Parts

- FastAPI API surface and Pydantic schemas.
- `src/db_utils.py` runtime DB/state behavior.
- `src/indexer.py` local Chroma/vector path.
- `src/profiles/research_dna_*` ownership and lifecycle.
- `backend/routers/paper_notes.py` related-paper behavior unless a separate schema/API contract is adopted.
- Obsidian markdown generation and idempotent note/export behavior.
- Skills policy boundaries in `config/skills_policy.yaml` and `src/skills/`.
- UI design system or graph visualization policy.

## Main Risks

Contract risk:
- SciAtlas response shapes are external and not PaperPipe Pydantic contracts.

Migration risk:
- A graph-first interpretation could accidentally redefine PaperPipe as a general research graph platform.

Dependency/ops risk:
- Hosted API, personal token, long timeouts, external service availability, and optional local GROBID/LLM dependencies.

Privacy risk:
- Queries, titles, references, paper metadata, or idea text may reveal private research direction.

Scientific validity risk:
- Graph proximity and citation importance are not the same as biomedical evidence quality.

Evaluation risk:
- Downstream applications are presented as running examples; dedicated benchmarks are still a future direction.

UX risk:
- Graph language and polished generated reports can make users over-trust weak or unreviewed discovery.

Author/profiling bias risk:
- Citation counts, h-index, institutional edges, and coauthor networks may amplify prestige and historical bias.

## Better-Than-Us Improvements Worth Internalizing

1. Make external discovery artifacts more map-like.
   - PaperPipe should explain "why this paper/author appeared" with path/score components where possible.

2. Separate ranking intents.
   - Precision, discovery, impact, and trend modes should not share one opaque ranking.

3. Treat related authors as a real workflow.
   - This is currently underdeveloped in PaperPipe and has clear researcher value.

4. Make idea positioning a reviewable draft artifact.
   - Similar/different/evidence framing is useful if it is not overclaimed.

5. Design keyword extraction around reusable concepts.
   - Avoiding paper-brand terms is directly useful for stable search profiles.

6. Keep agent-facing artifacts reproducible.
   - Plan/request/response/report grouping is a good external-discovery artifact pattern.

## What PaperPipe Should Keep As A Differentiator

1. Evidence-backed trust boundary.
2. Local-first canonical ownership.
3. Human operator review and correction loops.
4. Biomedical paper-internal evidence handling.
5. FastAPI/Pydantic runtime contracts.
6. Explicit sidecar/non-canonical labels.
7. Guarded regeneration and export behavior.

## Decision

Keep SciAtlas as an active reference.

Do not adopt it as a runtime dependency yet.

Open only a bounded future pilot if the team wants external graph discovery:

`Research DNA external related-author sidecar`

The pilot should be eval-first, opt-in, payload-classified, non-canonical, and measured against existing Research DNA outputs.

## Verification

Inspected:
- arXiv abstract and TeX source for SciAtlas.
- SciAtlas GitHub README, `.env.example`, client/API code, schema/task defaults, built-in skills, and reference search README.
- Local PaperPipe docs and code: master spec, operating principles, Research DNA spec, web viewer spec, UI grammar, indexer, paper-notes related logic, Research DNA schema.
- Existing Notion external reference hub.

Not run:
- SciAtlas hosted API call.
- SciAtlas token registration.
- Local GROBID workflow.
- Neo4j graph deployment.
- Any PaperPipe tests, because this review did not change runtime code.

Residual unknowns:
- Current hosted API availability/latency under real PaperPipe biomedical queries.
- Exact SciAtlas backend response stability.
- Data licensing/redistribution terms for any full graph export beyond the MIT client repo.
- Quality of related-author and idea-grounding outputs on our actual target domains.
