# Stack Integration Next Steps

## Current status

PR #358 is clean as an isolated top-of-stack PR:

- Base: `codex/deepread-soft-gate-base`
- Head: `codex/deepread-soft-gate`
- Commit under review: `5cf5731d`
- Merge state: `CLEAN`
- Manual `agents-smoke`: passed

The stack base is not itself ready for direct `master` integration:

- `codex/deepread-soft-gate-base` is 311 commits ahead of `origin/master`.
- A merge-tree comparison against `origin/master` reports many conflicts, including binary Playwright snapshots and changed-in-both source/test areas.
- There is no open PR for `codex/deepread-soft-gate-base`.

## Why #358 cannot simply be replayed onto master

A clean `origin/master` cherry-pick attempt showed that #358 depends on production and test surfaces that are not present on `master`, including:

- Deep-read worker/job-runner contract and optional provider import behavior.
- Protocol Cards and Protocol Attachments API/store surfaces.
- Project context link API.
- Research DNA API/store behavior.
- Artifact run/latest route behavior and artifact path helpers.
- Frontend/backend API contract fields.

## Prerequisite clusters found

These are the likely prerequisite lanes, based on first-touch commits for the files #358 exercises.

### Runtime and worker/job-runner surface

Representative commits:

- `ced75fb3` `feat(runtime): freeze memory-ready hardening lane`
- `840d6e29` `feat(notes): promote deep-read state across workbench`
- `6c8250fe` `Persist job progress and run metadata`
- `33eb2251` `Write deepread review sidecars`
- `a525c6ac` `Fix high-priority repository review risks`
- `6c126931` `Add Deep Read visual coverage sidecars`
- `07a64d79` `Surface coverage focus and review scope notes`

### Artifact route and run/latest surface

Representative commits:

- `38813265` `feat(papers): add ops summary and artifact query routes`
- `3b37ce43` `Cover runtime metadata sanitization`
- `bab1632e` `Add ops schema and artifact traversal regression`

### Meeting Pack, Chart Pack, Protocol Card, and attachment surfaces

Representative commits:

- `5c09619c` `feat(meeting-pack): adopt baseline runtime slice`
- `2ba3e0f9` `feat(chart-pack): add backend core and storage contract`
- `323410c3` `feat(protocol-cards): add backend core and file store`
- `97f78e9b` `feat(protocol-cards): add thin API surface`
- `aa8f616b` `Harden artifact pack services`

### Research DNA and project context surfaces

Representative commits:

- `a0799f26` `feat(research-dna): add core service and projection flows`
- `8eef5212` `feat(research-dna): add api wrappers`
- `bffb99ba` `Add project context link sanitization`
- `a42e4ee9` `Harden raw-memory secret sanitization`

### Frontend/backend contract surface

Representative commits:

- `d5af4810` `feat(paper-notes): switch list to server filtering and pagination`
- `227b3c06` `feat(frontend): add bounded artifact viewer shell`
- `5da589f9` `feat(protocol-cards): add read-only viewer shell`
- `06d07dac` `Refresh frontend workspace UX flows`
- `81e018d4` `Extend frontend fallback error gating`
- `3fc9c59e` `Restrict mock fallback to network errors`

## Recommended path

Do not open `codex/deepread-soft-gate-base` as one large PR. It is too large and conflict-heavy.

Recommended integration order:

1. Create clean `master`-based prerequisite PRs by functional cluster, starting with backend runtime/artifact route surfaces.
2. Land or stack the artifact-pack surfaces next: Meeting Pack, Chart Pack, Protocol Cards, and Protocol Attachments.
3. Land or stack Research DNA and project context link surfaces.
4. Land or stack frontend/backend API contract surfaces only after their backend routes are present.
5. Replay #358 on top of those clean prerequisite branches, or keep #358 as the top-of-stack review until the lower stack is resolved.

## Replay attempt on 2026-05-10

Attempted to start with the narrow artifact route/run-latest prerequisite cluster on a clean `origin/master` worktree:

- Branch: `codex/artifact-route-prereq-master`
- Worktree: `/Users/jangseongjin/.codex/worktrees/paperpipe-artifact-route-prereq`
- Candidate commits:
  - `38813265` `feat(papers): add ops summary and artifact query routes`
  - `3b37ce43` `Cover runtime metadata sanitization`
  - `bab1632e` `Add ops schema and artifact traversal regression`

Result:

- Cherry-pick of `38813265` conflicted immediately.
- Conflicting files:
  - `backend/main.py`
  - `src/schemas/papers.py`
  - `src/services/paper_ops_summary.py`
  - `tests/test_papers_api.py`
- The cherry-pick was aborted and the temporary worktree was returned to a clean state.

Interpretation:

- Even the artifact-route prerequisite cluster is not a clean commit-level replay.
- `master` already contains overlapping paper ops/schema/test work, so the next safe step is a smaller manual extraction of the exact route/schema/test behavior needed by #358, not blind cherry-picking of historical commits.
- Keep prerequisite replay PRs behavior-scoped rather than commit-scoped.

## Current recommendation for #358

Keep #358 open as an isolated review artifact and regression-test PR. Do not retarget it directly to `master` until the prerequisite stack is replayed or landed.
