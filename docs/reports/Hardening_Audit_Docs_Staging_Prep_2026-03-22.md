# Hardening Audit Docs Staging Prep

Status: staging manifest  
Date: 2026-03-22  
Branch: `codex/agents-smoke-ci-check`

## Intent

Freeze the audit/spec documentation set that explains the March hardening sequence and the later dirty-worktree lane decomposition.

## Included scope

- `docs/Audit_Driven_Roadmap_2026-03-13.md`
- `docs/Citation_Grounding_Audit_2026-03-13.md`
- `docs/Event_Logging_Audit_2026-03-13.md`
- `docs/Identity_Pathing_Audit_2026-03-13.md`
- `docs/Output_Contract_Audit_2026-03-13.md`
- `docs/PR_C1_Citation_Grounding_Resolver_Spec_2026-03-13.md`
- `docs/PR_C2_Reader_Grounding_Hardening_Spec_2026-03-13.md`
- `docs/PR_E1_Additive_Event_Log_Spec_2026-03-13.md`
- `docs/PR_I1_Identity_Pathing_Spec_2026-03-13.md`
- `docs/PR_I2_Deterministic_Chunk_IDs_Spec_2026-03-13.md`
- `docs/PR_O1_Output_Contract_Bridge_Spec_2026-03-13.md`
- `docs/PR_R0_Baseline_Adoption_Manifest_2026-03-13.md`
- `docs/reports/README.md`
- `docs/reports/Remaining_Dirty_Worktree_Lanes_2026-03-20.md`
- `docs/reports/Hardening_Audit_Docs_Staging_Prep_2026-03-22.md`

## Explicitly excluded

- tracked edits to legacy canonical docs such as `docs/Repository_Baseline_Adoption_2026-03-13.md`
- UX review reports
- frontend/runtime code changes
- cleanup guardrail docs already committed in earlier lanes

## Verification

1. `python3 scripts/lint_docs.py`
2. `git diff --cached --name-only` stays docs-only

## Commit target

`docs(audit): add hardening roadmap and audit set`
