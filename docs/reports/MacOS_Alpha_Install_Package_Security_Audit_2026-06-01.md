# macOS Alpha Install Package Security Audit

Status: Targeted install-package audit completed; fix follow-up added 2026-06-02
Date: 2026-06-01
Scope: `dist/release/Lattice-macos-arm64.zip` and extracted `dist/Lattice.app`
Artifact SHA256: `068c8977fa14b3f093f19040bd52b12cb7d5dc95af1a3dc1c356fcec929f4d22`
Launcher artifact SHA256: `5152a4c3c4d800d4e8a221a8026be69c28c49678511cd6c93d43572049313e81`

## Findings

### P1 - Not Gatekeeper-ready for public macOS distribution

Confirmed.

The package is locally code-signed only with an ad-hoc signature:

- `codesign -dv --verbose=4 dist/Lattice.app` reports `Signature=adhoc`
- `TeamIdentifier=not set`
- release manifest reports `signed=false`, `notarized=false`, and `gatekeeper_assessment=null`
- `spctl --assess --type execute -vv dist/Lattice.app` returns `dist/Lattice.app: rejected` with `spctl_exit=3`

Impact:

This artifact should not be presented as a public self-serve installer. Testers may see macOS trust warnings or launch blocking. For the Google Agent Challenge, this is acceptable only as an assisted alpha demo package.

Smallest fix direction:

Complete the Developer ID release path: Developer ID Application certificate, hardened runtime signing, Apple notarization with `notarytool`, stapling, re-zipping the stapled app, and final `spctl` acceptance.

Follow-up fix status, 2026-06-02:

The credential-dependent signing and notarization work remains blocked until a Developer ID Application certificate and notary profile exist. To prevent accidental public release claims before that, `scripts/release_macos_personal_runtime.py` now provides a `--require-gatekeeper` guard that rejects unsigned or non-notarized release attempts up front.

### P2 - Large native dependency surface in the packaged app

Mitigated for the cloud UI demo package.

The original audited package was large: extracted app about `841M`, release zip about `320M`, and `487` executable files. The largest native file was `dist/Lattice.app/Contents/Frameworks/torch/lib/libtorch_cpu.dylib` at about `205M`.

After the 2026-06-02 cloud UI profile rebuild:

- extracted app: about `194M`
- release zip: about `94M`
- executable files: `176`
- heavy ML package directories found for `torch`, `transformers`, `cv2`, `sklearn`, `scipy`, and `PIL`: `0`
- largest files observed: `dist/Lattice.app/Contents/Frameworks/pymupdf/libmupdf.dylib` and `dist/Lattice.app/Contents/MacOS/Lattice`, both about `31M`

Impact:

The cloud UI demo package now has a substantially smaller native dependency surface. The default `full` bundle remains larger by design because it preserves local parser, OCR, indexing, and ML-adjacent compatibility.

Smallest fix direction:

Create a cloud-demo packaging profile that excludes unused local ML/native stacks when the installed app is acting primarily as a lightweight cloud-backed UI.

Follow-up fix status, 2026-06-02:

The default personal-runtime bundle remains unchanged for local feature compatibility. A new `cloud-ui` PyInstaller profile can now be selected with `PAPERPIPE_BUNDLE_PROFILE=cloud-ui` or `scripts/build_personal_runtime_bundle.py --bundle-profile cloud-ui`; that profile excludes local heavy ML stacks such as `torch`, `transformers`, `cv2`, `sklearn`, and `scipy`.

The release script also forwards `--bundle-profile cloud-ui` when it is asked to run the bundle build via `--build`.

### P3 - Release manifest previously leaked local absolute paths; fixed during audit

Confirmed and fixed.

During the audit, the generated release manifest was found to include local absolute paths under `/Users/jangseongjin/...`. `scripts/release_macos_personal_runtime.py` was updated so manifest paths and console summary paths are repo-relative when possible. The release package and manifest were regenerated after the fix.

Current evidence:

- manifest `paths` values are now relative, for example `dist/Lattice.app` and `dist/release/Lattice-macos-arm64.zip`
- current release zip hash is `068c8977fa14b3f093f19040bd52b12cb7d5dc95af1a3dc1c356fcec929f4d22`
- current launcher zip hash is `5152a4c3c4d800d4e8a221a8026be69c28c49678511cd6c93d43572049313e81`
- manifest hash matches the actual zip hash
- custom app icon is present as `lattice.icns`
- the assisted local launcher can be regenerated with `scripts/install_macos_lattice_launcher.py --sign`, is now emitted by the alpha release path as `dist/release/Lattice-macos-arm64.launcher.zip`, uses the same `lattice.icns`, writes logs to `~/Library/Logs/Lattice/launcher.log`, and starts the installed app from `~/Library/Application Support/Lattice`
- launcher smoke on 2026-06-02 KST passed after stopping the existing packaged app process and opening `/Applications/Lattice Launcher.app`; `/health` returned `200` after 5 seconds

Residual risk:

The package was checked for obvious local path leakage after regeneration. Future release metadata should keep the same relative-path behavior. The launcher is an ad-hoc signed assisted-alpha wrapper and does not replace Developer ID signing, hardened runtime, notarization, or a first-class native WebView shell for public distribution.

Follow-up fix status, 2026-06-02:

A focused regression test now covers the manifest path invariant and asserts generated release manifest paths are repo-relative rather than absolute.

## Positive Checks

### Package integrity

Passed.

- `dist/release/Lattice-macos-arm64.manifest.json` hash matches the actual release zip hash
- `unzip -tq dist/release/Lattice-macos-arm64.zip` completed successfully
- zip top level is `Lattice.app`
- archive entry count: `835`
- zip-slip style path entries: `0`

### Bundle symlinks

Passed.

- symlink count: `97`
- symlinks escaping `Lattice.app/`: `0`

The observed symlinks are internal bundle links, including framework-relative links, not external archive escapes.

### Privileged file modes

Passed.

No setuid or setgid files were found under `dist/Lattice.app`.

### Obvious secret and credential leakage

No live-looking secret was confirmed in the package.

Checked for:

- `.env*`
- private key extensions such as `.key` and `.p8`
- service-account-like names
- sqlite/db files
- `.git` and `.ssh`
- obvious API key and private-key string patterns
- local absolute path pattern `/Users/jangseongjin`
- demo GCS bucket names in the app package and release sidecars

Expected non-secret hits:

- `certifi/cacert.pem`
- gRPC CA roots under `_credentials/roots.pem`
- vendored library references to service-account APIs and private-key signer type names

These are dependency assets or documentation/type-name references, not bundled cloud service account keys.

### Browser-visible cloud redaction proof

Passed after regenerating the package and again after the 2026-06-02 cloud UI rebuild.

`scripts/run_macos_alpha_zip_cloud_demo_proof.sh` extracted the release zip, launched the extracted `Lattice.app`, and confirmed:

- `/health` returned `200`
- `/ui` returned `200`
- `/api/cloud/papers` returned `200`
- `/api/cloud/papers/search` returned `200`
- expected demo paper id `paper_mock_000001` was present
- public cloud list/search payloads did not expose GCS refs, bucket names, signed URLs, service accounts, or internal object-ref fields
- current proof zip SHA256: `068c8977fa14b3f093f19040bd52b12cb7d5dc95af1a3dc1c356fcec929f4d22`
- current proof launcher zip SHA256: `5152a4c3c4d800d4e8a221a8026be69c28c49678511cd6c93d43572049313e81`

## Distribution Decision

Use this package for:

- assisted Google Agent Challenge demo
- close-person alpha testing
- local operator-controlled proof of the GCS + Firestore paper/page path

Do not use this package for:

- public self-serve macOS distribution
- notarized installer claims
- production multi-tenant security claims

## Verification Commands

Representative commands run:

```bash
uv run --extra cloud --extra packaging python scripts/build_personal_runtime_bundle.py --skip-frontend-build --clean --bundle-profile cloud-ui
uv run --extra cloud --extra packaging python scripts/release_macos_personal_runtime.py
uv run --extra cloud --extra packaging python scripts/release_macos_personal_runtime.py --require-gatekeeper

python3 - <<'PY'
import json, hashlib
from pathlib import Path
zip_path = Path("dist/release/Lattice-macos-arm64.zip")
manifest = json.loads(Path("dist/release/Lattice-macos-arm64.manifest.json").read_text())
actual = hashlib.sha256(zip_path.read_bytes()).hexdigest()
assert actual == manifest["hashes"]["release_zip_sha256"]
PY

unzip -tq dist/release/Lattice-macos-arm64.zip
codesign --verify --deep --strict --verbose=4 dist/Lattice.app
codesign -dv --verbose=4 dist/Lattice.app
spctl --assess --type execute -vv dist/Lattice.app
find dist/Lattice.app -type f \( -perm -4000 -o -perm -2000 \) -ls
find dist/Lattice.app \( -name '.env*' -o -name '*.pem' -o -name '*.key' -o -name '*.p8' -o -name '*credential*' -o -name '*service*account*' -o -name '*.sqlite' -o -name '*.db' -o -name '.git' -o -name '.ssh' \) -print
scripts/run_macos_alpha_zip_cloud_demo_proof.sh
PAPERPIPE_DEMO_PDF_PATH="/path/to/demo.pdf" scripts/run_gcp_cloud_paper_demo_readiness_gate.sh
```

## Follow-up Before Wider Distribution

1. Add Developer ID signing and notarization credentials to the release path.
2. Re-run release generation and confirm `spctl` accepts the stapled app.
3. Keep the verified `cloud-ui` profile for the stage demo unless a local-only feature requires the larger `full` bundle.
4. Keep the manifest local-path redaction behavior covered by the targeted release-script test.
