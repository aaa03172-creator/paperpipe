# Teacher Quality Loop Quarantine Review Drill (2026-03-09)

Status: Historical validation report  
Date: 2026-03-09  
Owner: Quality/runtime maintainers  
Canonical parent: `docs/teacher_quality_loop.md`

## Purpose
Validate the quarantine review workflow with a reproducible drill after the real-output probe showed `8/8` accepted records and produced no natural quarantine cases.

## Why A Drill Was Needed
- real local-first teacher outputs across the 2026-03-09 probes did not yield a quarantine record
- the remaining open question was not model quality itself, but whether the review path (`list -> edit -> resolve -> audit`) worked end to end
- to avoid polluting the canonical `goldset/`, the drill used an isolated root under `tmp/`

## Controlled Input
- source bundle:
  - `storage/artifacts/dry_probe_20260309/teacher/zotero_bialystokBilingualismConsequencesMind2012`
- source teacher output:
  - `storage/artifacts/dry_probe_20260309/teacher/zotero_bialystokBilingualismConsequencesMind2012/teacher_output.json`
- perturbation:
  - cleared `page`, `section`, `source_span`, `char_start`, `char_end` from all evidence spans
  - expected gate result: `EVIDENCE_LOCATION_MISSING`

## Commands
```bash
# 1) create a controlled invalid teacher output from a real bundle
python3 - <<'PY'
import json
from pathlib import Path
src = Path("storage/artifacts/dry_probe_20260309/teacher/zotero_bialystokBilingualismConsequencesMind2012/teacher_output.json")
out = Path("tmp/teacher_quarantine_drill_20260309/teacher_output.location_missing.json")
out.parent.mkdir(parents=True, exist_ok=True)
payload = json.loads(src.read_text(encoding="utf-8"))
for claim in payload.get("claims", []):
    for span in claim.get("evidence_spans", []):
        span["page"] = None
        span["section"] = None
        span["source_span"] = None
        span["char_start"] = None
        span["char_end"] = None
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY

# 2) route to quarantine in an isolated goldset root
python3 scripts/verify_teacher_output.py \
  --bundle-dir storage/artifacts/dry_probe_20260309/teacher/zotero_bialystokBilingualismConsequencesMind2012 \
  --teacher-output tmp/teacher_quarantine_drill_20260309/teacher_output.location_missing.json \
  --goldset-root tmp/teacher_quarantine_drill_20260309/goldset

# 3) inspect unresolved quarantine
python3 scripts/review_teacher_quarantine.py \
  --goldset-root tmp/teacher_quarantine_drill_20260309/goldset \
  list

# 4) simulate manual correction by restoring the validated teacher output
python3 - <<'PY'
import json
from pathlib import Path
q = Path("tmp/teacher_quarantine_drill_20260309/goldset/quarantine/zotero_bialystokBilingualismConsequencesMind2012.json")
valid = Path("storage/artifacts/dry_probe_20260309/teacher/zotero_bialystokBilingualismConsequencesMind2012/teacher_output.json")
record = json.loads(q.read_text(encoding="utf-8"))
record["teacher_output"] = json.loads(valid.read_text(encoding="utf-8"))
q.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
PY

# 5) resolve with an explicit review decision
python3 scripts/review_teacher_quarantine.py \
  --goldset-root tmp/teacher_quarantine_drill_20260309/goldset \
  resolve \
  --paper-id zotero:bialystokBilingualismConsequencesMind2012 \
  --resolution APPROVED_WITH_EDIT \
  --reviewer workflow-drill \
  --notes "Restored evidence location fields from validated teacher output before promotion."
```

## Results
- quarantine created: `1`
- quarantine reason: `EVIDENCE_LOCATION_MISSING`
- review resolution: `APPROVED_WITH_EDIT`
- accepted-after-review: `true`
- manual decision log written: `true`
- audit review record written: `true`

Artifacts:
- isolated root: `tmp/teacher_quarantine_drill_20260309/goldset`
- review audit:
  - `tmp/teacher_quarantine_drill_20260309/goldset/reviews/zotero_bialystokBilingualismConsequencesMind2012_20260309T091005.886759+0000.json`
- manual decisions:
  - `tmp/teacher_quarantine_drill_20260309/goldset/manual_decisions/human_decisions.jsonl`
- accepted-after-review:
  - `tmp/teacher_quarantine_drill_20260309/goldset/accepted/zotero_bialystokBilingualismConsequencesMind2012.json`

## Interpretation
- the quarantine review CLI behaved as designed on a real bundle
- the workflow evidence now exists for:
  - unresolved listing
  - reviewer decision capture
  - manual decision logging
  - accepted/quarantine sync
- this was a controlled drill, not a naturally occurring quarantine from the 2026-03-09 local-first teacher runs

## Follow-up
- if a future real local-first batch produces a natural quarantine record, that case should replace this drill as the preferred reviewer-workflow evidence
