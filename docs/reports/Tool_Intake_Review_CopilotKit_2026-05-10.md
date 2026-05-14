# Tool Intake Review: CopilotKit

Status: Proposed fit review
Date: 2026-05-10
Owner: Frontend/runtime maintainers
Candidate: `https://github.com/CopilotKit/CopilotKit`
Canonical parent: `docs/Lattice_v3_Master_Spec.md`
Operating note: `docs/PaperPipe_Minimum_Operating_Principles.md`
Related chat contract: `docs/API_CHAT_CONTRACT.md`
Related UI grammar: `docs/PaperPipe_UI_GRAMMAR.md`
Related assistant seam: `docs/Personal_Assistant_Integration_Seam_2026-05-10.md`

## 1. Current Bottleneck

PaperPipe has future assistant-facing needs, but the current runtime intentionally keeps `/api/chat` stub-only and does not yet have an adopted live chat, RAG, agent, provider, tool-calling, or assistant-state contract.

CopilotKit is being considered because it offers mature agent UI patterns: chat UI, generative UI, shared UI/agent state, backend tool rendering, and human-in-the-loop workflows.

## 2. Classification

Classification: `reference only`

Rationale:
- CopilotKit directly targets agent-native applications, while PaperPipe's current assistant boundary is deliberately not implementation-ready.
- Its strongest features overlap with areas PaperPipe has explicitly deferred: chat-first shell, shared agent/UI state, generative UI, runtime tool rendering, provider wiring, and agent-controlled UI updates.
- CopilotKit can still inform future design patterns for source-routed assistant panels, human confirmation, streamed progress, and action previews.
- It should not be installed into the product runtime until PaperPipe adopts a separate assistant runtime contract.

## 3. Capability Summary

From the official repository and package metadata, CopilotKit provides:

| Capability | PaperPipe relevance | Fit |
| --- | --- | --- |
| React chat UI | future assistant panel pattern | reference only |
| Backend tool rendering | possible action-preview idea | risky for runtime |
| Generative UI | useful pattern vocabulary | defer for product |
| Shared state between agent and UI | interesting for controlled assistant state | high risk for canonical boundaries |
| Human-in-the-loop | useful confirmation pattern | reference only |
| AG-UI protocol | possible future protocol reference | defer |
| Copilot Cloud | not aligned with local-first default | avoid unless separately approved |
| Self-hosted runtime | technically interesting | defer pending contract |
| Python SDK / FastAPI support | stack-adjacent | not enough for adoption |

## 4. Fit To PaperPipe

Good reference value:
- source-routed assistant panel behavior
- streamed action progress
- human confirmation before agent actions
- tool-call preview and result rendering patterns
- distinction between headless logic and UI shell
- possible future AG-UI vocabulary for agent-event streams

Poor direct fit today:
- PaperPipe is not currently an agent-native app.
- The frontend is Vite + React Router, while much CopilotKit documentation and examples lean toward agent app bootstrapping and framework-specific setup.
- PaperPipe's biomedical answer contract requires evidence refs and uncertainty before any assistant response becomes useful.
- Shared agent/UI state risks becoming a parallel truth layer unless heavily constrained.
- Generative UI risks making assistant-produced interface fragments look stronger than canonical evidence state.

## 5. Safest Insertion Point

Safest current insertion point:
- documentation and design research only

Acceptable near-term use:
- cite CopilotKit as a reference in a future assistant-boundary UX report
- extract patterns for:
  - source-aware assistant panel
  - confirmation before tool execution
  - streamed progress with explicit state labels
  - action cards that link back to canonical source/evidence
  - headless assistant UI prototypes that do not call external providers

Not safe yet:
- adding `@copilotkit/react-core`, `@copilotkit/react-ui`, or `@copilotkit/runtime`
- using `npx copilotkit@latest init`
- adding Copilot Cloud configuration
- wiring shared state into PaperPipe canonical state
- rendering backend tool output directly into core evidence screens
- enabling a live assistant route before `/api/chat` has an adopted contract

## 6. Do Not Rewrite These Parts

Do not rewrite:
- FastAPI route ownership in `backend/main.py`
- Pydantic contracts under `src/schemas/`
- current `/api/chat` stub-only behavior
- paper note/detail APIs
- `.pp/<slug>/state.json` structured paper state ownership
- artifact stores and downstream artifact readers/writers
- local-first provider/secret boundary
- UI grammar for Paper Detail, Workbench, Artifact Detail, Settings, and future assistant surfaces

## 7. Main Risks

### 7.1 Runtime Boundary Risk

CopilotKit is built to connect UI, agents, and tools into one interaction loop. That is useful for agent-native apps, but PaperPipe currently separates canonical state, generated artifacts, review artifacts, personal memory, and future assistant support.

Failure mode:
- CopilotKit shared state or generative UI becomes an unreviewed parallel truth layer.

Smallest fix direction:
- keep any future assistant state non-canonical, source-routed, and derived from existing FastAPI/Pydantic read models.

### 7.2 Local-First And Secret Risk

CopilotKit can be used with hosted Copilot Cloud or self-hosted runtime patterns. PaperPipe's default must remain local-first with browser-owned secrets forbidden.

Failure mode:
- public API keys, provider tokens, cloud project config, or assistant telemetry become part of frontend config or public git.

Smallest fix direction:
- require a backend-owned provider/secret contract before any runtime pilot.
- keep `.env`, local config, MCP config, Copilot Cloud config, and provider keys out of git.

### 7.3 Dependency And Telemetry Risk

The runtime package pulls in broad AI/provider/protocol/server dependencies, including provider SDKs, MCP/AG-UI packages, GraphQL/server tooling, analytics-related packages, and telemetry-adjacent dependencies.

Failure mode:
- a narrow assistant experiment expands the frontend/backend dependency surface and creates audit, bundle, telemetry, and maintenance cost.

Smallest fix direction:
- no runtime install until a pilot specifies exact package, transitive review, telemetry opt-out, and verification plan.

### 7.4 UX Authority Risk

CopilotKit's generative UI and tool rendering can make agent outputs look native and polished.

Failure mode:
- assistant-generated UI components appear more authoritative than source evidence, Workbench state, or artifact provenance.

Smallest fix direction:
- assistant output must carry source refs, uncertainty, payload boundary, and explicit non-canonical status.

### 7.5 Product Shape Risk

CopilotKit encourages an agent-native product model. PaperPipe should remain an evidence workspace with optional assistant support, not an assistant shell.

Failure mode:
- Paper Detail, Evidence Workbench, and Artifact Detail become secondary to a chat panel.

Smallest fix direction:
- assistant remains embedded and secondary; it cannot become primary navigation until a separate runtime contract is adopted.

## 8. Security And Config Risk

Do not commit:
- provider API keys
- Copilot Cloud project keys
- Copilot runtime URLs that encode private workspace identity
- MCP config or assistant config with tokens
- screenshots or reference captures containing paper titles, local file paths, PDFs, notes, lab data, or private identifiers

Recommended ignores if a future local experiment is created:

```gitignore
.copilotkit/
.copilotkit.local/
copilotkit.config.local.*
*.copilotkit.local.*
```

Existing ignore policy for MCP/reference tools should remain:
- `.lazyweb/`
- `*.mcp.json`
- `.mcp.json`
- `mcp.json`
- token files

Any runtime pilot must also set telemetry opt-out variables where supported:
- `COPILOTKIT_TELEMETRY_DISABLED=true`
- `DO_NOT_TRACK=1`

## 9. Smallest Pilot

Do not start with runtime install.

Smallest safe pilot:

1. Create an assistant-boundary UX report.
   - File: `docs/UX_REVIEW_REPORT_evidence-aware-assistant-boundary.md`
   - Scope: Paper Detail or Artifact Detail side panel only.

2. Define static interaction states without CopilotKit.
   - states: disabled, local-only unavailable, provider missing, source scope selected, answer draft, evidence refs visible, action preview, confirmation required, blocked external payload.

3. Use CopilotKit only as a reference pattern.
   - record which CopilotKit pattern was referenced.
   - do not install packages.
   - do not call hosted services.

4. Only after `/api/chat` changes from stub-only:
   - evaluate a behind-flag, self-hosted-only prototype in a throwaway branch or isolated worktree.
   - require dependency review, telemetry opt-out, provider secret plan, evidence-ref contract, and Playwright coverage.

## 10. Adoption Criteria For Any Future Runtime Pilot

Before CopilotKit can move beyond `reference only`, PaperPipe must have:

- adopted live `/api/chat` or assistant API contract
- backend-owned provider/secret storage
- explicit inference payload classes for assistant requests
- Pydantic request/response schemas with evidence refs and uncertainty
- non-canonical assistant state policy
- no browser-owned provider secret
- no Copilot Cloud dependency by default
- explicit telemetry opt-out
- dependency and license review
- route-specific UX report
- Playwright coverage for assistant boundary states

## 11. Recommendation

Use CopilotKit as a reference for future assistant UX and human-in-the-loop action patterns.

Do not install CopilotKit in the PaperPipe product runtime now.

Do not run `npx copilotkit@latest init` in this repo.

Do not use CopilotKit to reopen chat, RAG, memory, MCP, provider, or generative UI runtime work while `/api/chat` remains stub-only.

The most useful near-term outcome is an assistant-boundary UX report that borrows pattern ideas while keeping PaperPipe's core shape:

> evidence workspace first, assistant support second, canonical state always source-routed.

## 12. Sources Inspected

- GitHub repository: `https://github.com/CopilotKit/CopilotKit`
- Repository README: `https://raw.githubusercontent.com/CopilotKit/CopilotKit/main/README.md`
- Package metadata:
  - `https://raw.githubusercontent.com/CopilotKit/CopilotKit/main/packages/react-core/package.json`
  - `https://raw.githubusercontent.com/CopilotKit/CopilotKit/main/packages/react-ui/package.json`
  - `https://raw.githubusercontent.com/CopilotKit/CopilotKit/main/packages/runtime/package.json`
  - `https://raw.githubusercontent.com/CopilotKit/CopilotKit/main/sdk-python/pyproject.toml`
- Product page and package registry snippets checked for self-hosting, cloud, telemetry, and dependency claims:
  - `https://www.copilotkit.ai/product`
  - `https://www.copilotkit.ai/copilotkit-intelligence`
  - `https://www.npmjs.com/package/@copilotkit/runtime`

Unverified:
- full current docs site behavior behind client-rendered pages
- premium feature license terms
- current cloud data-retention contract
- whether every telemetry path is disabled by the documented opt-out variables
- exact bundle impact in PaperPipe's Vite app
