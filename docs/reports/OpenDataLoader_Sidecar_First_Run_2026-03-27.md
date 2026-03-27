# OpenDataLoader Sidecar First Run

Status: bounded execution report  
Date: 2026-03-27  
Lane: `opendataloader-sidecar-eval`

## Purpose

Run the first real `OpenDataLoader PDF` sidecar evaluation against the frozen hard-doc manifest on current `master`, without changing the PaperPipe runtime parser path.

## Inputs

- Harness: [run_opendataloader_sidecar_pilot.py](/Users/jangseongjin/paperpipe/scripts/eval/run_opendataloader_sidecar_pilot.py)
- Frozen manifest: [opendataloader_sidecar_hard_doc_20260327.json](/Users/jangseongjin/paperpipe/goldset/manifests/opendataloader_sidecar_hard_doc_20260327.json)
- Source reference manifest: [ingest_backend_pilot_20260323.json](/Users/jangseongjin/paperpipe/goldset/manifests/ingest_backend_pilot_20260323.json)

Included hard-doc subset:
- `Chandra 2023`
- `Hansson 2023`
- `Pichet Binette 2023`
- `Therriault 2022`

## Execution Environment

- clean worktree based on `origin/master`
- Homebrew `openjdk@17`
- isolated `uv` virtual environment `.venv-opendataloader`
- `opendataloader-pdf==2.1.1`

Important boundary:
- this install path was kept outside the main PaperPipe runtime environment
- no `parser_backend` enum/config changes were made
- no runtime parser routing changed

## Command

```bash
export JAVA_HOME="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
export PATH="/opt/homebrew/opt/openjdk@17/bin:$PATH"
source .venv-opendataloader/bin/activate
python scripts/eval/run_opendataloader_sidecar_pilot.py \
  --manifest goldset/manifests/opendataloader_sidecar_hard_doc_20260327.json \
  --out-dir snapshots/opendataloader_sidecar_eval \
  --run-id opendataloader_sidecar_hard_doc_20260327_r1 \
  --formats json,markdown
```

## Result

Overall run status:
- `ok`
- exit code `0`
- input count `4 / 4`
- requested outputs present `4 / 4`

Generated sidecar counts:
- JSON files: `4`
- Markdown files: `4`
- image directories: `4`
- PNG files: `68`
- local run footprint: about `6.2 MB`

Observed JSON node signals from the first run:
- `Chandra 2023`: paragraph-heavy, heading-heavy, image nodes present, no table nodes surfaced
- `Hansson 2023`: paragraph-heavy with `2` table nodes surfaced
- `Pichet Binette 2023`: paragraph/list/image heavy, no table nodes surfaced
- `Therriault 2022`: paragraph-heavy with `9` table nodes and many image nodes surfaced

## Local Execution Artifact

The local execution root was:

- `snapshots/opendataloader_sidecar_eval/opendataloader_sidecar_hard_doc_20260327_r1/`

It contained:
- `summary.json`
- `run_manifest.json`
- `stdout.log`
- `stderr.log`
- raw `.json` / `.md` outputs for all 4 PDFs
- auto-generated image directories emitted by the parser

Current decision:
- keep these raw sidecars as local execution artifacts for now
- do not promote the raw snapshot tree into the shared repo yet

Reason:
- `summary.json` currently records worktree-absolute output paths
- raw output includes many image files by default
- this first run establishes installability and artifact generation, not yet a stable shared snapshot contract

## Operational Findings

- `OpenDataLoader PDF` ran successfully once `openjdk@17` was available and the CLI lived in an isolated Python 3.11 environment.
- The CLI does not expose a simple `--version` path in the current installation; version provenance had to come from the Python package install.
- The default run emitted image directories even though `--formats json,markdown` was requested and no explicit `--image-output` mode was set.
- `stdout.log` contained parser warnings such as detected backgrounds and glyph-to-Unicode mapping warnings, but the run still completed successfully.

## Safe Interpretation

This run is evidence of:
- successful local installation in an isolated execution lane
- successful batch sidecar generation on the frozen hard-doc subset
- successful production of JSON and Markdown outputs for all manifest documents

This run is **not** evidence of:
- runtime parser readiness
- canonical schema compatibility
- superiority over the existing parser path
- promotion to a default parser backend

## Recommended Next Step

Keep the next step bounded:
1. inspect the generated sidecars against the current baseline on the same 4 documents
2. decide whether a compact, portable summary artifact is worth promoting into `snapshots/`
3. only then consider a second run with explicit image-output policy or tagged-PDF structure-tree options
