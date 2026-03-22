# Profiles YAML Research-DNA Snapshot Staging Prep (2026-03-23)

## Goal
Split a narrow data/config lane that updates the checked-in profile snapshot without mixing it with runtime config logic.

## Included
- `/Users/jangseongjin/paperpipe/config/profiles.yaml`
- `/Users/jangseongjin/paperpipe/docs/reports/Profiles_Yaml_Research_DNA_Snapshot_Staging_Prep_2026-03-23.md`

## Why This Is One Lane
- The dirty change is a serialized profile snapshot update plus one disabled Research DNA projection profile.
- `src/config.py` and `config.example.yaml` have already been separated into the runtime config lane.
- This file loads cleanly through the existing profile loader and does not require additional code changes.

## Verification Plan
- `python3 -c "from pathlib import Path; from src.profiles.profile_store import load_profiles; cfg = load_profiles(Path('config/profiles.yaml')); print(len(cfg.profiles))"`
- `python3 scripts/lint_docs.py`

## Expected Outcome
The checked-in profile snapshot reflects revision-aware profile serialization and includes the bounded Research DNA compatibility snapshot.
