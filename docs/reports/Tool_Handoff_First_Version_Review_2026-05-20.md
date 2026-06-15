# Tool Handoff First Version Review

Status: Proposal / fit review
Date: 2026-05-20
Owner: Lattice runtime/product maintainers
Canonical parent:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/PaperPipe_UI_GRAMMAR.md`

This document summarizes the first-version design discussion for a Tool Handoff surface in Lattice/PaperPipe.

It is not a new master spec, DB contract, or approval to replace the current paper/job/artifact runtime. It describes a bounded first implementation path for turning existing paper-scoped structured state into tool-ready prompts, grammar payloads, and draft handoff artifacts.

## 1. Product Thesis

Lattice should not try to rebuild every excellent external tool.

The stronger role is:

> Lattice compiles already-extracted, evidence-linked paper knowledge into safe, tool-ready context that external AI tools, APIs, MCP servers, or user-owned agents can immediately use.

The user should mainly do two things:

1. Connect or select a tool target when needed.
2. Say what they want in natural language.

Examples:
- "이 논문을 랩미팅용 6장 슬라이드로 만들어줘."
- "핵심 기전을 도식화해줘."
- "Notion에 정리하기 좋은 페이지 초안으로 바꿔줘."
- "이미지 생성 AI에 넘길 figure prompt를 만들어줘."

The product value is not generic chat. The value is evidence-aware translation from paper state into the right downstream working format.

## 2. Current Runtime Fit

The idea fits the current product boundary if it stays paper-first, artifact-first, local-first, evidence-linked, and reviewable.

Current anchors already present in the codebase:

- `src/schemas/skills.py::StructuredPaperState` already stores paper-scoped claim/evidence/signals/runs.
- `src/schemas/privacy_preflight.py::PrivacyPreflightPayloadClass` already defines `local_only`, `lab_allowed`, and `external_allowed`.
- `src/services/privacy_preflight.py` already provides deterministic preflight checks for external payload risks.
- `src/schemas/paper_synthesis.py`, `src/schemas/talk_pack.py`, and chart/meeting handoff artifacts already show the pattern: derived artifact, explicit lineage, non-canonical status, draft/review boundary.
- `/api/chat` is intentionally stubbed in the current runtime, so first version should not depend on a broad chat assistant.

This means the first version should be a bounded downstream artifact lane, not a new general workspace or autonomous tool platform.

## 3. First Version Scope

Recommended first version:

> Tool Handoff Panel: a preview-first panel that generates tool-ready prompts or grammar payloads from the current paper context.

In scope:
- Paper detail or paper card entry point.
- Natural-language request input.
- Output target selection.
- Deterministic intent parsing for common requests.
- ContextPack built from existing paper state.
- One or more first-party adapters.
- Preview-only output.
- Copy and Save Draft actions.
- Validation and payload boundary summary.
- Handoff artifact saved as non-canonical draft/export artifact.

Out of scope for first version:
- Direct arbitrary API execution.
- User API key storage in browser state.
- Automatic MCP discovery.
- General tool marketplace.
- Long-lived chatbot memory.
- Full conversation agent.
- Sending raw PDF, full note, local paths, raw memory, or secrets to external tools.

## 4. UX Shape

The surface should be chat-like only at the input level. It should not behave like a full chatbot in the first version.

Recommended UI:

```text
Paper Detail
  Create with tools
    Output target:
      Diagram
      Slides
      Notion draft
      Image prompt

    Request:
      "이 논문을 랩미팅용 6장 슬라이드로 만들어줘"

    Interpreted request:
      target = slides_outline
      audience = lab_meeting
      slide_count = 6
      language = ko
      include = key_claims, methods, limitations

    Context scope:
      Will use:
        paper card
        selected claims
        evidence snippets
        limitations
      Will not use:
        raw PDF
        full note
        raw memory
        local paths

    Preview:
      generated slide outline / Mermaid / Notion blocks / image prompt

    Safety:
      payload_class = external_allowed or local_only
      validation = pass / warn / blocked

    Actions:
      Copy
      Save draft
      Regenerate
      Later: Execute
```

The first version should make the user feel:

- "I can say what I want naturally."
- "Lattice understood the task in editable structured terms."
- "I can inspect the evidence and data boundary before using the output."
- "The result is a draft handoff, not promoted truth."

## 5. Request Interpretation

The request input should not be treated as open-ended chat. It should be parsed into a constrained intent schema.

Example:

```text
"이 논문을 랩미팅용 6장 슬라이드로 만들어줘"
```

Parsed intent:

```json
{
  "target": "slides_outline",
  "audience": "lab_meeting",
  "slide_count": 6,
  "language": "ko",
  "tone": "evidence_backed",
  "include": ["background", "methods", "key_claims", "limitations"],
  "exclude": []
}
```

Recommended V0 parser:

- Rule-based target inference.
- Rule-based slot extraction.
- Sensible defaults.
- Editable interpretation preview.

Initial deterministic rules:

```text
"슬라이드", "PPT", "발표" -> slides_outline
"도식", "diagram", "흐름도" -> mermaid_diagram
"노션", "정리" -> notion_page_draft
"그림", "이미지", "일러스트" -> image_prompt
"6장", "6 slides" -> slide_count = 6
"랩미팅" -> audience = lab_meeting
```

Recommended V1 parser:

- Add a small local or bounded LLM only for slot filling.
- Require JSON/Pydantic validation.
- Unknown values become `null` or defaults.
- No scientific facts may be invented during intent parsing.

## 6. Internal Objects

The first implementation should introduce a small set of explicit contracts.

### ToolManifest

Describes a tool target or adapter.

Suggested fields:
- `tool_id`
- `display_name`
- `capabilities`
- `input_schema`
- `output_schema`
- `execution_modes`
- `payload_class`
- `allowed_layers`
- `denied_layers`
- `template_id`
- `validator_ids`

### ToolHandoffIntent

The structured interpretation of the user's natural-language request.

Suggested fields:
- `target`
- `audience`
- `language`
- `count`
- `tone`
- `include`
- `exclude`
- `constraints`
- `defaults_applied`
- `confidence`
- `warnings`

### ContextPack

The minimal paper-scoped context selected for the adapter.

Allowed first-version layers:
- `paper_card`
- `selected_claims`
- `evidence_snippets`
- `limitations`
- `run_meta`

Denied first-version layers:
- `raw_pdf`
- `raw_memory`
- `full_note`
- `local_paths`
- `secrets`

### ToolHandoffArtifact

The saved non-canonical output bundle.

Suggested fields:
- `handoff_id`
- `artifact_family = tool_handoff`
- `layer = user_facing_artifact`
- `canonical_status = non_canonical`
- `status = draft`
- `paper_slug`
- `tool_id`
- `adapter_id`
- `user_request`
- `parsed_intent`
- `context_pack_ref`
- `generated_payload`
- `preview`
- `validation`
- `privacy_preflight`
- `source_refs`
- `evidence_refs`
- `warnings`
- `created_at`
- `updated_at`

### PayloadPolicy

The policy gate for data leaving the local runtime.

Use the existing language:
- `local_only`
- `lab_allowed`
- `external_allowed`

Ambiguous payloads should default to the stricter class.

## 7. Adapter Contract

The adapter pattern is a good center for this feature, but class inheritance alone is not enough. It must be paired with manifest, schemas, policy, validator, and preview.

Recommended conceptual interface:

```python
class BaseToolAdapter:
    tool_id: str
    payload_class: str

    def manifest(self): ...
    def parse_intent(self, user_request): ...
    def build_context(self, paper_state, intent): ...
    def compile(self, context_pack, intent): ...
    def validate(self, compiled_payload): ...
    def preview(self, compiled_payload): ...
    def execute(self, compiled_payload, secrets): ...
    def normalize_result(self, raw_result): ...
    def build_artifact(self, result): ...
```

First version should implement only:

- `manifest`
- `parse_intent`
- `build_context`
- `compile`
- `validate`
- `preview`
- `build_artifact`

`execute` should be present in the contract but disabled or unimplemented for first version.

## 8. Recommended First Adapters

Start with one adapter end-to-end, then add two more.

### 1. MermaidDiagramAdapter

Why first:
- No external API key required.
- Easy to preview and validate.
- Good proof of "natural language to tool grammar."

Output:
- Mermaid flowchart or sequence diagram.

Validation:
- Max nodes.
- Required title.
- Evidence labels optional but recommended.
- No raw quotes beyond short evidence snippets.

### 2. SlidesOutlineAdapter

Why second:
- Strong user value.
- Existing Talk Pack concepts already resemble slide manifests.

Output:
- Slide outline JSON or markdown.
- No PPTX rendering required in first handoff version.

Validation:
- Slide count.
- At least one evidence-backed slide when claims are used.
- Limitations slide recommended.

### 3. NotionPageDraftAdapter

Why third:
- Natural handoff target.
- Can start as markdown or structured blocks without direct Notion API execution.

Output:
- Notion-ready markdown or block-style JSON.

Validation:
- Source/evidence section present.
- Draft/non-canonical status visible.

## 9. API Shape

Suggested first-version endpoints:

```text
GET  /tool-adapters
POST /tool-handoffs/interpret
POST /tool-handoffs/generate
GET  /tool-handoffs/{handoff_id}
```

Possible request:

```json
{
  "paper_slug": "current-paper",
  "tool_id": "slides_outline",
  "user_request": "이 논문을 랩미팅용 6장 슬라이드로 만들어줘",
  "context_scope": {
    "include_claim_ids": [],
    "include_limitations": true
  },
  "execution_mode": "preview"
}
```

Possible response:

```json
{
  "handoff": {
    "handoff_id": "toolhandoff_...",
    "artifact_family": "tool_handoff",
    "canonical_status": "non_canonical",
    "status": "draft",
    "tool_id": "slides_outline",
    "parsed_intent": {},
    "preview": {},
    "validation": {
      "status": "pass",
      "warnings": []
    },
    "privacy_preflight": {
      "payload_class": "external_allowed",
      "status": "pass"
    },
    "evidence_refs": []
  }
}
```

## 10. Tool Attachment Model

"Attaching a tool" should not mean that the user can paste any arbitrary API URL and let Lattice execute it.

For first versions, tool attachment should mean one of three progressively broader actions:

```text
Stage 1: Enable built-in preview targets
  - Mermaid diagram
  - Slides outline
  - Notion page draft
  - Image prompt
  - no API key
  - no external execution
  - Preview / Copy / Save draft only

Stage 2: Connect approved executable adapters
  - Notion API page create
  - slide export provider
  - selected image-generation provider
  - backend-only secret reference
  - connection test required
  - preview gate before Execute

Stage 3: Import custom adapter manifest
  - future only
  - deny-by-default
  - schema validation required
  - payload policy required
  - dry-run or preview mode required
  - no raw arbitrary execution surface
```

The first implementation should only need Stage 1. Stage 2 can be designed in the contracts but should not be necessary to prove value.

### User-Facing Flow

The user-facing flow should avoid API/platform jargon:

```text
Settings / Tools
  Supported tool targets
    Mermaid diagram       Enabled
    Slides outline        Enabled
    Notion draft          Enabled
    Image prompt          Enabled
    Notion API create     Connect later

Paper Detail
  Create with tools
    target = Slides outline
    request = "이 논문을 랩미팅용 6장 슬라이드로 만들어줘"
    Preview
    Copy / Save draft
```

In first version, the paper detail panel can show built-in preview targets even before a full Settings / Tools page exists.

### Internal Connection Objects

Tool attachment should be represented separately from handoff generation.

Suggested `ToolConnection` fields:

- `tool_id`
- `enabled`
- `connection_status`
- `auth_mode`
- `secret_ref`
- `endpoint_ref`
- `last_tested_at`
- `last_test_result`
- `payload_class`
- `allowed_execution_modes`
- `warnings`

`ToolConnection` should not contain plaintext API keys, OAuth tokens, or browser-owned secrets.

### Secret Boundary

Secrets must stay backend-owned.

Rules:

- Do not store provider API keys in browser state, localStorage, or handoff artifacts.
- Do not include API keys in prompts or local/small LLM inputs.
- Store only a `secret_ref` in `ToolConnection`.
- Redact secret-like strings in logs and artifact metadata.
- Require connection tests before enabling `api_execute`.
- Keep `api_execute` unavailable for first-version preview tools.

### Attachment API Shape

Possible future endpoints:

```text
GET  /tool-adapters
GET  /tool-connections
POST /tool-connections/{tool_id}/enable
POST /tool-connections/{tool_id}/test
POST /tool-connections/{tool_id}/disable
POST /tool-handoffs/{handoff_id}/execute   # later only
```

First implementation can start with:

```text
GET  /tool-adapters
POST /tool-handoffs/generate
GET  /tool-handoffs/{handoff_id}
```

and treat built-in preview adapters as enabled by default.

### Attachment UX Review

#### Quick Review

- Block: Show "what this tool target makes," not adapter/MCP/API details.
- Interpret: Display capability and data boundary before connection fields.
- Act: Stage 1 tools should work without setup.
- Store: Save connection status, last test result, and payload boundary.
- Ethics: No hidden credentials and no hidden external send.

#### Full Review

P0:
- Custom arbitrary API execution is out of scope.
- API keys must not be browser-owned.
- Every executable adapter must declare payload policy and execution modes.

P1:
- Connection test should be mandatory before execute.
- Failed connection tests should not erase saved draft handoffs.
- The panel should degrade to Copy / Save draft when execution is unavailable.

P2:
- Custom manifest import can be explored after built-in preview and approved executable adapters are stable.

#### BMAP

- Motivation: The user wants to reuse excellent external tools.
- Ability: Enable built-in preview targets first so value appears before account setup.
- Prompt: `Connect later` should not block preview-first use.

#### B.I.A.S

- Block: API/MCP terms create early friction.
- Interpret: "This target can make slides/diagrams/pages" is the useful meaning.
- Act: Use enable/test/preview/execute as progressive steps.
- Store: Connection status and data boundary must be visible after setup.

#### Peak-End

- Peak: A built-in target works immediately without API setup.
- Pit: The user wonders where an API key went or what data was sent.
- End: The tool appears in paper detail with a clear status and safe fallback action.

#### Ethics

- Regret: The user should not later discover their key or raw paper data was exposed.
- Black Mirror: Custom adapters could become data exfiltration paths; keep them deny-by-default.
- In Real-Life: The product should say "this is what I will send" before any execution.

## 11. Readiness Assessment

Estimated readiness based on current repo shape:

```text
V0: template-only handoff
Readiness: 70-80%
Example: paper_slug + user_request -> Mermaid or slide outline preview

V1: adapter contract + validation + saved artifact
Readiness: 55-65%
Example: ToolManifest, BaseToolAdapter, ToolHandoffArtifact, privacy preflight

V2: small local LLM slot filling
Readiness: 40-50%
Example: natural-language request -> validated intent JSON

V3: direct API/MCP execution
Readiness: 30-40%
Example: Notion API, auth, retries, rate limits, normalized errors

V4: general tool platform
Readiness: 15-25%
Example: arbitrary external MCP/API attachment and autonomous use
```

Primary gaps:
- No first-class `ToolManifest` schema yet.
- No `BaseToolAdapter` contract yet.
- No `ToolHandoffArtifact` store/service/router yet.
- No direct secret store for connected external tool credentials in this lane.
- `/api/chat` is currently stubbed and should not be the first-version dependency.

Primary strengths:
- Paper-scoped structured state exists.
- Derived artifact patterns exist.
- Handoff and quality gate patterns exist.
- Payload class vocabulary exists.
- Privacy preflight service exists.
- FastAPI router structure is already established.

## 12. UX Review

### Quick Review (5 min)

- Block: Do not expose adapter, MCP, or schema language to the user.
- Interpret: Show "what Lattice understood" before showing generated grammar.
- Act: The default action should be `Preview`, then `Copy` or `Save draft`.
- Store: Save the request snapshot, generated payload, evidence refs, and data boundary summary.
- Ethics: No hidden external send in first version.

### Full Review

#### P0

- Preview-first is mandatory.
- External execution is out of scope for first version.
- Raw PDF, raw memory, full note, local paths, and secrets must be denied from first-version external payloads.
- Generated outputs are draft, non-canonical, and reviewable.

#### P1

- The panel should live near paper detail or paper card context, not as a global chatbot.
- Intent interpretation should be editable.
- Context scope should be visible in plain language.
- Validation warnings should appear before copy/export actions.

#### P2

- Add example chips for common requests.
- Add "regenerate" only after first preview works reliably.
- Add execution mode only after secret and API failure handling are implemented.

### Full Review Coverage

#### 6P storyboard context

- Problem: The user has already extracted and reviewed paper knowledge, but must repeatedly re-explain it to external tools.
- Emotion: The user feels friction because the information is already organized inside Lattice.
- Action: The user opens `Create with tools` from the paper detail surface.
- Struggle: Each external tool has a different prompt style, grammar, API shape, or MCP capability.
- Attempt: Lattice converts the user's natural-language request and paper context into a validated handoff payload.
- Happy Ending: The user gets a copyable or saveable draft output with evidence refs and data boundary summary.

#### BMAP

- Motivation: High. Users want to reuse strong external tools without rebuilding them inside Lattice.
- Ability: The main barrier is tool grammar and prompt construction.
- Prompt: The right prompt is a paper-local action such as `Create with tools`, `Make slides`, `Diagram`, or `Notion draft`.

#### B.I.A.S

- Block: Internal implementation terms create friction.
- Interpret: The panel should communicate "paper knowledge to tool-ready output."
- Act: Natural-language request plus target selection should be enough.
- Store: The saved draft should make provenance and boundary visible.

#### Peak-End

- Peak: A one-line Korean request becomes a usable Mermaid diagram or slide outline.
- Pit: The user sees malformed JSON, hidden external sends, or confusing API errors.
- Transition: Paper detail -> interpreted request -> preview -> copy/save.
- End: The user has a draft handoff artifact and can recover how it was made.

#### Ethics

- Regret: The user should never discover later that raw paper data was sent externally.
- Black Mirror: Tool-generated decks or diagrams must not appear more scientifically certain than their evidence supports.
- In Real-Life: The product should behave like a careful research assistant, not an automation broker.

## 13. Implementation Plan

### PR 1: Contract and Mermaid preview

Add:
- `src/schemas/tool_handoff.py`
- `ToolManifest` and built-in adapter catalog entries
- `src/tool_handoffs/adapters/base.py`
- `src/tool_handoffs/adapters/mermaid.py`
- `src/tool_handoffs/service.py`
- `src/tool_handoffs/store.py`
- `backend/routers/tool_handoffs.py`
- targeted tests for schema, parser, service, and route

Behavior:
- Built-in preview adapters are enabled by default.
- Generate Mermaid preview only.
- Save `ToolHandoffArtifact`.
- Run privacy preflight against generated payload text and respect the configured mode. Test/dev fixtures may use report-only, but `block_on_review` should surface a blocked preview state even before external execution exists.
- No external execution.

### PR 2: Tool connection contracts

Add:
- `ToolConnection` schema.
- `/tool-connections` read/list shape.
- Disabled executable mode placeholders.
- Secret boundary documentation in API descriptions.

Behavior:
- No plaintext secret persistence in this PR.
- Built-in preview adapters remain usable without connections.
- Executable external adapters remain disabled until a later secret-store-backed PR.

### PR 3: Slides outline adapter

Add:
- `SlidesOutlineAdapter`
- slide-count and audience parsing
- evidence-backed slide outline validation

Behavior:
- Generate markdown or JSON slide outline.
- Reuse Talk Pack vocabulary where useful, without silently changing Talk Pack persisted contracts.

### PR 4: Panel UI

Add:
- Paper detail `Create with tools` panel.
- Target selection.
- Request input.
- Interpreted request preview.
- Context scope summary.
- Generated output preview.
- Copy and Save Draft.

Verification:
- `cd frontend && npm run build`
- relevant Playwright coverage if the touched paper detail surface already has tests

## 14. Open Questions

1. Should first-version saved artifacts live under a new `storage/tool_handoffs/` root or under the existing artifact family root pattern?
2. Should the first route be paper-slug based only, or allow run-id pinning from the start?
3. Should `external_allowed` previews be blocked when privacy preflight mode is `block_on_review`, even if no actual external execution happens?
4. Should Mermaid validation use a lightweight parser, a deterministic grammar check, or preview rendering in frontend tests?
5. Should the UI expose "data not sent" as a fixed safety summary, or derive it from adapter manifest policy?
6. Should the first Settings / Tools surface exist before executable adapters, or should Stage 1 built-in targets appear only inside paper detail first?
7. What backend secret store should Stage 2 use, and how should secret refs be migrated or revoked?
8. Should custom adapter manifest import require a project policy file similar to the skills policy gate?

## 15. Decision Recommendation

Proceed with a first version only if it is framed as:

> A paper-scoped Tool Handoff artifact lane that creates previewable, validated, non-canonical draft payloads.

Do not frame first version as:

- a chatbot
- a general MCP platform
- a tool marketplace
- an arbitrary API attachment surface
- an autonomous agent executor
- a replacement for external tools

The first implementation should prove one narrow loop:

```text
paper structured state
  -> user natural-language request
  -> interpreted intent
  -> minimal ContextPack
  -> Mermaid preview payload
  -> validation and privacy summary
  -> saved draft handoff artifact
```

That loop is small enough to build safely and meaningful enough to validate the product thesis.
