# Patch Checklist

## Map First

Before editing, write down:
- entry point
- owner files
- schema or API surface touched
- nearest tests or smoke checks

If you cannot do this, stop and map further.

## Smallest Patch Rules

- prefer additive integration over replacement
- keep unrelated files untouched
- avoid opportunistic refactors
- preserve existing names, routes, and storage shape unless the task requires a change

## Architecture Check

Ask these questions:
- does this change alter a `src/schemas/` contract
- does it move or duplicate runtime ownership
- does it introduce a new dependency that is not clearly justified
- does it blur the boundary between personas, profiles, and output modes
- does it turn a pilot into an implicit default

If any answer is yes, call out the risk explicitly.

## Verification Ladder

Prefer the smallest relevant check:
1. targeted unit test
2. targeted smoke script
3. route-specific or page-specific build/test
4. broader suite only if smaller checks cannot cover the behavior

## Closeout

Always report:
- changed files and why
- verification run
- missing verification
- rollback path or disable path
