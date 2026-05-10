# Ctx2Skill-Lite Fit Review

Status: Proposed eval-sidecar pilot  
Date: 2026-05-10  
Owner: PaperPipe/Lattice evaluation maintainers  
Related code: `evals/paper_skill_gym/`

## Executive Summary

Recommendation: partial adoption.

Ctx2Skill is useful to PaperPipe as a way to test whether paper-reading Skill.md guidance actually improves. It should not be adopted as a product runtime framework or multi-agent orchestration layer.

The adopted slice is `Ctx2Skill-lite`: probe-based, eval-only, deterministic where possible, and separated from FastAPI routes, DB state, active `.codex/skills/`, and `src/skills/`.

## Repo Fit

This fit follows the current PaperPipe/Lattice boundary:

- `docs/Lattice_v3_Master_Spec.md` treats structured paper/job/artifact state as canonical.
- `docs/PERSONA_MODE_BOUNDARY.md` warns against turning every perspective into a separate agent.
- `docs/SKILLS_PACKAGING_GUIDE.md` separates Codex workflow skills from runtime-visible product skills.
- `config/skills_policy.yaml` gates runtime-visible skills explicitly.
- Existing deep-read quality paths already include reader eval, citation grounding, teacher review sidecars, goldsets, baselines, and snapshots.

The safe insertion point is therefore an additive evaluation harness, not product runtime integration.

## Adopted Components

The initial pilot lives under `evals/paper_skill_gym/`:

- `probes/*.yaml`: ten hand-authored paper-reading probes.
- `schemas.py`: Pydantic contracts for probes, answers, reports, comparisons, and regression summaries.
- `make_answer_template.py`: blank answer-template generator for current-baseline capture.
- `run_probe_set.py`: deterministic binary probe judge.
- `compare_reports.py`: baseline-vs-candidate accept/reject gate.
- `sample_answers/baseline_stub.yaml`: deterministic smoke fixture, not a real product baseline.

## Probe Taxonomy

The pilot covers:

- figure grounding
- table interpretation
- claim/evidence separation
- method reconstruction
- limitation detection
- reproducibility
- citation/page grounding
- unsupported/unknown logging

## Candidate Acceptance Policy

A candidate Skill.md can be considered for human review only when:

- total pass rate does not regress,
- hard pass rate does not regress,
- easy pass rate does not regress,
- replay balance score does not regress,
- baseline-passing probes do not newly fail,
- protected locator/unknown/unsupported/evidence rubrics do not newly fail,
- probe count is unchanged,
- the patch remains small, reviewable, and outside runtime contracts.

Reject reports include `failure_summary` and deterministic `suggested_actions`. These are review prompts only; they must not automatically edit active Skill.md files.

## Non-Adopted Components

Do not adopt at this stage:

- Ctx2Skill's full five-agent orchestration.
- Automatic Skill.md rewriting.
- Product runtime Challenger/Reasoner/Judge/Proposer/Generator agents.
- DB, API, ClaimSet, artifact schema, or active runtime skill changes.
- Model-judge-only pass/fail decisions without deterministic gates.

## Verification

Current local verification for the pilot:

```bash
.venv/bin/python -m pytest -q tests/test_paper_skill_gym.py
.venv/bin/python -m py_compile \
  evals/__init__.py \
  evals/paper_skill_gym/__init__.py \
  evals/paper_skill_gym/schemas.py \
  evals/paper_skill_gym/run_probe_set.py \
  evals/paper_skill_gym/compare_reports.py \
  evals/paper_skill_gym/make_answer_template.py \
  tests/test_paper_skill_gym.py
```

## Next PR-Sized Actions

1. Capture a real `current_baseline` answer file from the current reader/Skill.md behavior.
2. Add one candidate Skill.md diff report and compare it against `current_baseline`.
3. Promote only human-reviewed, stable probes into a longer-lived goldset.

