# External AI Tooling Fit Review

Status: dated report / fit review
Date: 2026-06-06
Owner: Lattice runtime maintainers
Scope: external AI projects and posts shared for PaperPipe/Lattice relevance

Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/KNOWLEDGE_LAYER_OPERATING_NOTE.md`
- `docs/Personal_Assistant_Integration_Review_Packet_2026-05-10.md`

## Purpose

This note records a bounded review of recent external AI projects and posts for possible PaperPipe/Lattice reuse.

It is not:

- authorization to change runtime behavior
- approval to import external code or skills
- a replacement for the current paper/job/artifact product boundary
- a claim that social-post metrics are fully verified

## Source Bundle

Reviewed source bundle:

- MisoTTS: https://github.com/MisoLabsAI/MisoTTS
- FunASR: https://github.com/modelscope/FunASR
- TripoSplat: https://github.com/VAST-AI-Research/TripoSplat
- Workshop Wallpaper Bridge: https://github.com/3x-haust/workshop-wallpaper-bridge
- Odysseus: https://github.com/pewdiepie-archdaemon/odysseus
- OpenHuman: https://github.com/tinyhumansai/openhuman
- Qwen3 Korean voice clone quickstart: https://github.com/azzselloo-sudo/qwen3-korean-voice-clone
- MOSS-TTS: https://github.com/OpenMOSS/MOSS-TTS
- Drag-and-Drop LLMs: https://arxiv.org/abs/2506.16406
- design-diversity: https://github.com/epoko77-ai/design-diversity
- AWS LangSmith deep-agent evaluation article: https://aws.amazon.com/ko/blogs/machine-learning/evaluating-deep-agents-using-langsmith-on-aws/
- Hugh Kim Claude Code setup: https://hugh-kim.space/
- Karpathy LLM Wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Presentation and visualization references: Slideland, Speaker Deck, Deck Gallery, SlideShare, Data to Viz, Data Viz Project, PresentationGO, RAWGraphs

Threads posts were not directly fetchable in the browser session. Their content should be treated as externally sourced intake supplied by the user unless independently archived.

## Snapshot Notes

GitHub API snapshot taken on 2026-06-06 KST:

- `pewdiepie-archdaemon/odysseus`: created `2026-05-31T14:05:51Z`, which is 2026-05-31 23:05:51 KST; about 56.8k stars; MIT; default branch `dev`.
- `tinyhumansai/openhuman`: about 30.9k stars; GPL-3.0; active beta posture.
- `modelscope/FunASR`: about 17.3k stars; MIT; mature speech-recognition toolkit.
- `OpenMOSS/MOSS-TTS`: about 3.1k stars; Apache-2.0 model family.
- `MisoLabsAI/MisoTTS`: about 2.0k stars; license needs file-level review before reuse.
- `VAST-AI-Research/TripoSplat`: about 450 stars; MIT; very new.
- `3x-haust/workshop-wallpaper-bridge`: about 174 stars; MIT; local-only macOS bridge.
- `epoko77-ai/design-diversity`: about 149 stars; GitHub API license returned `NOASSERTION`; README claims MIT for design specs/tokens/docs/skills, so inspect files before reuse.
- `azzselloo-sudo/qwen3-korean-voice-clone`: about 25 stars; MIT; small quickstart repo.

Social virality around Odysseus appears plausible from repository timing and current GitHub activity, but tweet/thread like counts were not independently verified.

## Best Fits For PaperPipe

### 1. Evaluation and Trace Discipline

Adopt the pattern, not necessarily the product, from the AWS LangSmith article.

Fit:

- PaperPipe already has deep-read, evidence-grounding, meeting-pack, chart-pack, and artifact lanes that need regression-friendly evaluation.
- The useful pattern is offline pytest-style evaluation with trace artifacts, feedback scores, safety checks, latency, and token-cost metadata.
- A local JSONL/SQLite eval sidecar should be the default. LangSmith or any cloud trace system should be optional and payload-classified.

Recommended bounded slice:

- Add or refine an `eval_sidecar` contract for selected job/run/artifact outputs.
- Score citation coverage, source linkage, unsafe inference, stale state, overstatement risk, and completion quality.
- Keep traces as review artifacts, not canonical truth.

Do not:

- upload raw papers, full notes, local paths, private logs, or canonical state to external trace systems by default
- turn eval traces into a second source of truth

### 2. Local Workspace Product Pattern

Odysseus and OpenHuman are useful as product-reference material, not as runtime architecture to copy.

Fit:

- Odysseus shows strong demand for self-hosted AI workspaces and has unusually high launch attention.
- Its security notes are relevant: shell access, uploads, model downloads, web research, OAuth, API tokens, and local databases make the app admin-console-like.
- OpenHuman's local memory tree plus Obsidian-style Markdown plus SQLite resembles local-pkb more than PaperPipe.

Recommended bounded slice:

- Reuse the security posture: any future assistant-facing PaperPipe bridge should be treated like an admin capability.
- Keep assistant integration thin and read-model-first, matching `docs/Personal_Assistant_Integration_Review_Packet_2026-05-10.md`.
- Prefer stable URI/read contracts over broad memory or workspace ownership.

Do not:

- turn Lattice into a generic chat/workspace platform
- copy GPL-3.0 OpenHuman code into PaperPipe
- import Odysseus as a dependency or product shell

### 2.5 Claude Code Harness Pattern

Hugh Kim's Claude Code setup is useful as an operating reference for agent-assisted development workflows.

Reviewed materials:

- Site: https://hugh-kim.space/
- `manager-orchestrator`: https://github.com/jung-wan-kim/manager-orchestrator
- `memory-bank`: https://github.com/jung-wan-kim/memory-bank
- `usage-gate`: https://github.com/jung-wan-kim/usage-gate
- `claude-code-infrastructure-showcase`: https://github.com/jung-wan-kim/claude-code-infrastructure-showcase
- `cc-sync-template`: https://github.com/jung-wan-kim/cc-sync-template

Useful patterns:

- Manager/specialist separation, where the orchestrator plans, assigns, reviews, and records, but does not directly write product code.
- Contract-first handoff via files rather than fragile chat summaries.
- Phase-based implementation, QA, review, and fix loops.
- Explicit file-boundary rules for parallel agents.
- Hook/skill auto-activation, but with a strong warning to customize instead of blindly copying.
- Three-file dev-doc pattern: task plan, context, and checklist.
- Usage gating, where expensive models are automatically downgraded near quota limits.
- Cross-device configuration sync, with explicit secret/file-path exclusion.

Fit:

- PaperPipe already has task-local working files, verification maps, skill policy, dirty-worktree discipline, and review artifacts.
- The most useful overlap is the "filesystem as truth" and "bounded handoff artifact" pattern.
- Usage/cost gating is directionally useful for external inference and expensive eval lanes.

Recommended bounded slice:

- Keep PaperPipe's existing `.codex/work/<date>_<slug>/plan.md`, `findings.md`, and `progress.md` pattern rather than importing a parallel Claude harness.
- Consider a small "agent lane handoff" checklist for multi-agent review/implementation:
  - task scope
  - allowed files
  - blocked files
  - expected verification
  - owner of final merge decision
  - required doc updates
- Consider a future provider cost gate for cloud LLM calls, but keep it inside PaperPipe's inference-routing and payload-classification policy.

Do not:

- import Claude-specific hooks as PaperPipe runtime policy
- auto-trigger broad skills or tools that bypass `config/skills_policy.yaml`
- sync secrets, runtime state, logs, private paths, or cached plugin code through a settings-sync repo
- let automated orchestration override the repo's current human-reviewable product boundary

### 3. Audio Intake

FunASR is the strongest audio candidate in the bundle.

Fit:

- Meeting Pack and Talk Pack workflows could benefit from local or self-hosted speech-to-text.
- Speaker diarization, multilingual ASR, streaming, and OpenAI-compatible API claims align with meeting/seminar capture.
- MIT licensing is comparatively easy to reason about, subject to model-license review for specific model weights.

Recommended bounded slice:

- Draft an `audio_ingest` RFC only after current paper-first runtime lanes remain stable.
- Treat audio as raw source.
- Treat transcript as derived source artifact.
- Treat summaries, action items, and meeting packs as user-facing artifacts with provenance.

Do not:

- make audio capture passive or always-on
- use transcript summaries as canonical truth without source links and confidence flags

### 4. Presentation and Visualization Quality

design-diversity plus Data to Viz, Data Viz Project, PresentationGO, Deck Gallery, Speaker Deck, SlideShare, and RAWGraphs are useful for artifact polish and review, not core reasoning.

Fit:

- PaperPipe already has Meeting Pack, Chart Pack, Protocol Cards, and presentation-review materials.
- The useful pattern is a style/profile and chart-selection gate, not a new UI system.

Recommended bounded slice:

- Add a presentation artifact quality checklist:
  - chart type matches data shape
  - chart caveats are recorded
  - slides remain editable when exported
  - visual style is constrained by a declared profile
  - design choices do not hide uncertainty or missing evidence

Do not:

- import arbitrary design packs into the runtime without license review
- let decorative design override evidence hierarchy

### 5. TTS and Voice Output

MOSS-TTS is the strongest broad TTS candidate. Qwen3 Korean voice clone is useful for a small Korean experiment. MisoTTS is high-quality but heavy and English-only at the reviewed snapshot.

Fit:

- Optional Korean/audio briefing for meeting packs or operator review is plausible.
- Voice output is downstream convenience, not core evidence processing.

Recommended bounded slice:

- Hold as an optional export adapter after artifact correctness gates are stronger.
- Start with text-first outputs and only then generate audio from a saved artifact.
- Require voice-consent, watermarking, and impersonation safeguards.

Do not:

- make voice cloning part of core PaperPipe
- generate deceptive or identity-confusing audio
- send private biomedical content to remote TTS without payload classification

### 6. LLM Wiki / Compiled Knowledge

Karpathy's LLM Wiki pattern is highly relevant to PaperPipe, but only if translated into the existing knowledge-layer contract.

Source pattern:

- immutable raw sources
- LLM-maintained Markdown wiki
- a schema/instruction file that tells the LLM how to update the wiki
- `index.md` for navigation
- append-only `log.md` for chronology
- periodic lint passes for contradictions, stale claims, orphan pages, missing cross-references, and data gaps

Fit:

- PaperPipe already has a knowledge-layer operating note and an explicit raw / compiled / canonical boundary.
- The useful pattern is "compiled knowledge that compounds," not "let the LLM freely rewrite truth."
- A wiki-like layer could help for protocol knowledge, method comparison context, project-level reading maps, and long-running research themes.

Externally sourced adoption notes supplied by the user:

- The workflow must verify that wiki updates happen consistently. If agents update code, artifacts, or terminology without updating the wiki, later repair becomes expensive.
- Keeping raw data in the same codebase/context can confuse the LLM when terminology changes or old claims remain visible. Raw sources should be preserved, but not casually loaded as equal-rank current guidance.

Recommended bounded slice:

- Treat any LLM Wiki adoption as a `compiled knowledge` lane, subordinate to canonical paper/run/artifact state.
- Keep raw sources immutable and outside the default instruction/search path unless explicitly requested.
- Maintain a current `index.md` and append-only `log.md` if a wiki lane is opened.
- Add a wiki consistency check to relevant workflows:
  - source ingested -> source summary created or updated
  - concept/entity page touched when needed
  - index updated
  - log appended
  - stale/contradictory terms flagged
- Require lint passes that detect stale terminology and ingestion-order bias before using wiki pages for operator-facing recommendations.

Do not:

- treat the wiki as canonical state
- mix raw and compiled pages in the same default retrieval priority
- let a generic LLM rewrite wiki pages without a schema/instruction contract
- use old raw notes to override newer canonical docs, schemas, or reviewed artifacts

## Low Fit Or Hold

### TripoSplat

Good for 2D-to-3D asset experiments, weak fit for current PaperPipe.

Possible future use:

- biomedical visual artifact lab
- figure/3D communication experiments

Hold until:

- image evidence and visual artifact lanes need 3D representation
- license, model weights, and output provenance are separately reviewed

### Workshop Wallpaper Bridge

Useful as an example of a local-only macOS bridge with explicit project boundaries.

Possible reuse:

- local-only packaging language
- user-owned file import posture
- clear "does not download / does not bypass / does not redistribute" boundary phrasing

Not a functional fit for PaperPipe runtime.

### Drag-and-Drop LLMs

Interesting research direction for rapid LoRA generation, but not implementation-ready for PaperPipe.

Possible future use:

- specialist extraction profiles
- narrow task adapters for paper understanding

Hold until:

- code and weights are available and reviewed
- biomedical extraction/evidence tasks have a clear benchmark target
- generated adapters can be evaluated against existing goldsets

## Recommended PR-Sized Next Actions

1. `eval_sidecar` proposal
   - Create a bounded design note for local-first eval traces over deep-read and artifact outputs.
   - Keep trace payloads classified and minimized.

2. `audio_ingest` RFC
   - Evaluate FunASR as an optional local/self-hosted transcript provider.
   - Keep raw audio, transcript, and summary layers separate.

3. `presentation_quality_gate`
   - Add a checklist for Meeting Pack / Chart Pack / Talk Pack outputs based on Data to Viz and presentation design references.
   - Treat design as artifact QA, not as evidence.

4. `compiled_knowledge_wiki_gate`
   - Draft a bounded wiki-lane note that maps LLM Wiki ideas onto PaperPipe's raw/compiled/canonical layer taxonomy.
   - Include an index/log contract and a required update-consistency check.
   - Keep raw source folders out of default LLM context unless a task explicitly needs source audit.

## Current Recommendation

Adopt:

- local eval sidecar pattern
- admin-console security posture for future assistant bridges
- bounded Claude Code harness patterns: filesystem-as-truth, agent handoff files, explicit file boundaries, and cost gates
- audio ingest as a later optional lane
- presentation/chart quality gate as artifact QA
- bounded LLM Wiki pattern for compiled knowledge, with update consistency and stale-term linting

Hold:

- TTS as optional downstream export
- Drag-and-Drop LLMs until benchmarked and reproducible
- TripoSplat until a real 3D visual-evidence need appears

Reject for now:

- broad Odysseus/OpenHuman-style workspace expansion inside PaperPipe
- passive personal memory or autonomous capture inside Lattice
- external trace/upload defaults for sensitive paper state
