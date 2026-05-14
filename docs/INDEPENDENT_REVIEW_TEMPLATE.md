# Independent Review Template

Status: Active template
Date: 2026-04-03
Owner: Lattice runtime maintainers
Canonical parent: `docs/working-files.md`

Purpose: provide a small optional template for PR-sized, non-UX independent review notes without turning every task into a heavyweight protocol.

Use this when:

- a bounded runtime, backend, schema, artifact, or docs change needs a compact independent signoff
- a lane-specific closure note needs a consistent `pass / warn / fail` structure
- the work is meaningful enough that rerun verification and residual risk should be recorded

Do not use this when:

- the task is a trivial one-shot edit
- the task already requires a dedicated workflow artifact such as `docs/UX_REVIEW_TEMPLATE.md`
- the change is a launch or release decision better represented by `green / yellow / red` release notes

## Header
- Change/Lane:
- Goal:
- Reviewer:
- Date:
- Related contract or plan:
- Verification scope:

## 1. Scope Checked
- In scope:
- Out of scope:

## 2. Contract Checked
- Expected outputs:
- Hard fail conditions:
  - Example checks:
    - a second canonical path was introduced instead of updating the current canonical doc
    - a retired compatibility stub is being treated as the active reference
    - additive review/task artifacts are being treated as runtime or doc SSOT
    - a compiled knowledge asset reads or promotes inputs outside its approved bounded source set
    - a compiled knowledge asset cannot jump back to upstream claim/evidence/source lineage

## 3. Files and Surfaces Checked
- ...

## 4. Verification Rerun
- Command:
- Result:
- What it proves:

## 5. Findings
### P0
### P1
### P2

## 6. Verdict
- Verdict: `pass` | `warn` | `fail`
- Hard fail triggered: yes | no
- Why:

## 7. Residual Risks
- ...

## 8. Next PR-sized Actions
- ...
