# Paper Skill Gym

Status: eval-only PoC.

This directory is a Ctx2Skill-lite landing zone for paper-reading Skill.md evaluation. It is not a product runtime skill and must not be wired into `src/skills/`, FastAPI routes, or DB state without a separate contract review.

## Scope

The gym answers one narrow question:

> Did a candidate paper-reading Skill.md improve evidence-grounded paper reading without regressing easy cases?

It does not automatically rewrite active Skill.md files.

## Components

- `probes/*.yaml`: small paper-reading probes with binary rubrics.
- `schemas.py`: Pydantic contracts for probes, answers, verdicts, and reports.
- `make_answer_template.py`: blank answer-template generator for current-baseline capture.
- `run_probe_set.py`: deterministic binary judge and replay-style summary.
- `compare_reports.py`: baseline-vs-candidate accept/reject gate.

## Probe Taxonomy

- `figure_grounding`
- `table_interpretation`
- `claim_evidence_separation`
- `method_reconstruction`
- `limitation_detection`
- `reproducibility`
- `citation_page_grounding`
- `unsupported_unknown_logging`

## Candidate Accept Criteria

A candidate Skill.md may be considered for human review only if:

- total pass rate improves against the baseline probe set,
- hard pass rate improves or stays flat,
- easy pass rate does not regress,
- `replay_balance_score = hard_pass_rate * easy_pass_rate` improves or stays flat,
- locator/evidence rubrics do not regress,
- the patch is small and reviewable,
- it does not change runtime APIs, DB contracts, artifact schemas, or active `.codex/skills/` files automatically.

Reject or quarantine the candidate if it:

- passes hard probes by inventing unsupported content,
- weakens unknown/unsupported logging,
- removes provenance requirements,
- bloats Skill.md with case-specific memorization,
- requires a product runtime orchestration change.

## Example

Create a blank answer template for the current reader/Skill.md baseline:

```bash
.venv/bin/python -m evals.paper_skill_gym.make_answer_template \
  --out snapshots/paper_skill_gym/current_baseline.todo.yaml
```

Fill the generated `answer`, `claims`, `evidence`, and `unknowns` fields from the current reader/Skill.md behavior. Do not edit probe YAML to make a baseline pass.

```bash
.venv/bin/python -m evals.paper_skill_gym.run_probe_set \
  --answers evals/paper_skill_gym/sample_answers/baseline_stub.yaml \
  --out snapshots/paper_skill_gym/baseline_report.json
```

Compare a candidate report against the baseline:

```bash
.venv/bin/python -m evals.paper_skill_gym.compare_reports \
  --baseline snapshots/paper_skill_gym/baseline_report.json \
  --candidate snapshots/paper_skill_gym/candidate_report.json \
  --out snapshots/paper_skill_gym/comparison.json
```

The compare command exits `0` for `accept` and `1` for `reject`.

Reject reports include `failure_summary` tags such as:

- `missing_locator`
- `missing_unknown_logging`
- `table_interpretation_regression`
- `figure_table_conflict_regression`
- `evidence_grounding_regression`

Reject reports also include deterministic `suggested_actions`. These are review prompts for a candidate Skill.md patch, not automatic edits.
