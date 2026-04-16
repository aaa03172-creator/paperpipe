# macOS Personal Runtime Alpha Handoff

Status: Active  
Date: 2026-03-28  
Owner: Lattice runtime maintainers  
Purpose: define the honest close-person handoff path for the current macOS personal-runtime bundle while Gatekeeper-ready trust distribution is still deferred.

Canonical parents:
- `docs/PERSONAL_RUNTIME_INSTALL.md`
- `docs/MACOS_PERSONAL_RUNTIME_RELEASE.md`
- `docs/reports/Personal_Runtime_Packaging_Decision_2026-03-28.md`

## Scope

Use this when:

- you want to hand the current macOS app to a small number of trusted testers
- you are comfortable with operator-assisted setup
- Gatekeeper-ready signing/notarization is not yet the goal

Do not use this as if it were:

- a public distribution guide
- a mass self-serve installer flow
- proof of general consumer installability

## Current honest product state

Today the repo can produce:

- `dist/Lattice.app`
- `dist/lattice`
- `dist/release/Lattice-macos-arm64.zip`
- `dist/release/Lattice-macos-arm64.alpha-handoff.md`
- `dist/release/Lattice-macos-arm64.config.example.yaml`

Today the repo does not yet guarantee:

- Apple Gatekeeper acceptance
- notarized public web distribution
- frictionless first-run for non-technical testers

## Maintainer path

1. Build the current bundle:

```bash
.venv/bin/python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean
```

2. Produce the alpha handoff package:

```bash
.venv/bin/python scripts/release_macos_personal_runtime.py
```

3. Confirm the generated files exist:

- `dist/release/Lattice-macos-arm64.zip`
- `dist/release/Lattice-macos-arm64.alpha-handoff.md`
- `dist/release/Lattice-macos-arm64.config.example.yaml`

4. Run one final runtime check before sending:

```bash
PAPERPIPE_CONFIG_PATH="$PWD/config.example.yaml" PAPERPIPE_INSTALL_LAYOUT=1 ./dist/Lattice.app/Contents/MacOS/Lattice self-test --json
```

5. Edit the config example or separately provide the tester with the exact values for:

- `paths.obsidian_vault`
- `paths.zotero_base_dir`

## What to send the tester

Send these together:

- the alpha app artifact zip
- the alpha handoff note
- the config template

If the tester is not comfortable with Terminal or with manual config edits, do not send only the zip. Do an assisted setup session.

## Tester path

The intended tester flow is:

1. Unzip the app artifact.
2. Move `Lattice.app` into `/Applications` or another user-controlled folder.
3. Copy the provided config template to:
   `~/Library/Application Support/Lattice/config/config.yaml`
4. Edit the config with real local paths.
5. Launch the app.

## Expect rough edges

Because trust distribution is intentionally deferred:

- macOS may warn on first open
- the maintainer may need to help with the first launch
- placeholder external roots will degrade readiness

That is acceptable for this phase because the product goal is still:

- one operator
- one runtime
- close-person alpha feedback

## When to stop using this path

Stop using this alpha handoff path when either of these becomes true:

- you want broad self-serve web distribution
- you want testers to install without maintainer assistance

At that point, move to the Gatekeeper-ready path in:

- `docs/MACOS_PERSONAL_RUNTIME_RELEASE.md`
