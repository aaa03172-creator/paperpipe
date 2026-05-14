# PaperPipe Main Branch Guide

This branch is not the current integration line.

`main` currently serves two narrower purposes:
- a lightweight Python runtime snapshot (`src/`, `config.example.yaml`, `PaperPipe_Master_Spec.md`)
- the default-branch registration point for `.github/workflows/frontend-real-smoke.yml`

For the current integration and CI surface, use the `master` implementation line.

## What Is In This Branch

- `src/cli.py`: Typer entrypoint for the legacy/local Python workflow
- `config.example.yaml`: example local configuration
- `PaperPipe_Master_Spec.md`: branch-local product/runtime spec snapshot
- `.github/workflows/frontend-real-smoke.yml`: manual real-paper smoke workflow registered on the default branch

## Quick Start

Install dependencies:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -e .
python3 -m pip install -r requirements.txt
```

Create local config:

```bash
cp config.example.yaml config.yaml
```

Set the required runtime secret:

```bash
export OPENAI_API_KEY="..."
```

Useful local commands:

```bash
python3 -m src.cli doctor
python3 -m src.cli run
python3 -m src.cli watch
```

## Frontend Real Smoke Workflow

The repository default branch is `main`, so GitHub registers `frontend-real-smoke.yml` here.

Important:
- This workflow is `workflow_dispatch` only.
- The workflow definition lives on `main`, but the actual implementation may live on another ref.
- The workflow expects an implementation tree that contains `frontend/` and `scripts/check_frontend_real_smoke_env.py`.
- Because those paths are not present on `main`, dispatch the workflow against the implementation branch you want to verify.

Example:

```bash
gh workflow run frontend-real-smoke.yml \
  --ref <implementation-branch> \
  -f config_path=config.yaml
```

The self-hosted runner must satisfy the labels declared in `.github/workflows/frontend-real-smoke.yml`.

## Branch Note

Current branch split:
- `main`: default-branch workflow registration + legacy Python snapshot
- `master`: active integration and PR gate line

Keep that split explicit until the repository branch strategy is unified.

## Reference Docs

- Local spec snapshot: [PaperPipe_Master_Spec.md](./PaperPipe_Master_Spec.md)
- Current integration README on `master`: [README on master](https://github.com/aaa03172-creator/paperpipe/blob/master/README.md)
