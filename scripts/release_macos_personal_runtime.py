from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
DEFAULT_RELEASE_DIR = DIST_DIR / "release"
DEFAULT_APP_BUNDLE = DIST_DIR / "Lattice.app"
DEFAULT_CLI_BINARY = DIST_DIR / "lattice"
DEFAULT_SUPPORT_DIR = DIST_DIR / "Lattice-support"


@dataclass(frozen=True)
class ReleasePaths:
    app_bundle: Path
    cli_binary: Path
    support_dir: Path
    release_dir: Path
    zip_path: Path
    alpha_handoff_path: Path
    config_example_copy_path: Path
    manifest_path: Path
    notary_submit_path: Path
    notary_log_path: Path


@dataclass(frozen=True)
class ReleasePreflight:
    status: str
    local_release_ready: bool
    gatekeeper_release_ready: bool
    requested_identity: str | None
    requested_notary_profile: str | None
    matching_identity: str | None
    notary_profile_available: bool
    notary_profile_detail: str | None
    available_identities: list[str]
    tools: dict[str, bool]
    artifacts: dict[str, bool]
    blockers: list[str]
    next_steps: list[str]


def default_artifact_basename(machine: str) -> str:
    normalized = machine.strip().lower() or "unknown"
    return f"Lattice-macos-{normalized}"


def resolve_release_mode(identity: str, notary_profile: str) -> tuple[bool, bool]:
    sign_enabled = bool(identity.strip())
    notarize_enabled = bool(notary_profile.strip())
    if notarize_enabled and not sign_enabled:
        raise ValueError("A notary profile requires a signing identity.")
    return sign_enabled, notarize_enabled


def build_release_paths(root: Path, artifact_basename: str, release_dir: Path | None = None) -> ReleasePaths:
    dist_dir = root / "dist"
    resolved_release_dir = (release_dir or dist_dir / "release").resolve()
    return ReleasePaths(
        app_bundle=(dist_dir / "Lattice.app").resolve(),
        cli_binary=(dist_dir / "lattice").resolve(),
        support_dir=(dist_dir / "Lattice-support").resolve(),
        release_dir=resolved_release_dir,
        zip_path=(resolved_release_dir / f"{artifact_basename}.zip").resolve(),
        alpha_handoff_path=(resolved_release_dir / f"{artifact_basename}.alpha-handoff.md").resolve(),
        config_example_copy_path=(resolved_release_dir / f"{artifact_basename}.config.example.yaml").resolve(),
        manifest_path=(resolved_release_dir / f"{artifact_basename}.manifest.json").resolve(),
        notary_submit_path=(resolved_release_dir / f"{artifact_basename}.notary-submit.json").resolve(),
        notary_log_path=(resolved_release_dir / f"{artifact_basename}.notary-log.json").resolve(),
    )


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    capture_output: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def _run_combined(cmd: list[str]) -> str:
    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = proc.stdout or ""
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=output)
    return output


def _run_no_check(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _require_tool(tool: str) -> None:
    if shutil.which(tool) is None:
        raise FileNotFoundError(f"Required tool is not available on PATH: {tool}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_bundle(*, clean: bool, skip_frontend_build: bool) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / "build_personal_runtime_bundle.py")]
    if skip_frontend_build:
        cmd.append("--skip-frontend-build")
    if clean:
        cmd.append("--clean")
    _run(cmd, cwd=ROOT)


def _ensure_artifacts_exist(paths: ReleasePaths) -> None:
    required_paths = [paths.app_bundle, paths.cli_binary]
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        missing_display = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(
            f"Expected packaging artifact is missing: {missing_display}. Run the bundle build first or pass --build."
        )


def _codesign(path: Path, identity: str, *, deep: bool) -> None:
    cmd = ["codesign", "--force", "--sign", identity]
    if identity != "-":
        cmd.extend(["--timestamp", "--options", "runtime"])
    if deep:
        cmd.append("--deep")
    cmd.append(str(path))
    _run(cmd)


def _verify_codesign(paths: ReleasePaths) -> None:
    _run(["codesign", "--verify", "--strict", str(paths.cli_binary)])
    _run(["codesign", "--verify", "--deep", "--strict", str(paths.app_bundle)])


def _package_zip(app_bundle: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    _run(
        [
            "ditto",
            "-c",
            "-k",
            "--keepParent",
            "--sequesterRsrc",
            "--rsrc",
            str(app_bundle),
            str(zip_path),
        ]
    )


def _copy_handoff_files(paths: ReleasePaths, artifact_basename: str) -> None:
    shutil.copy2(ROOT / "config.example.yaml", paths.config_example_copy_path)

    handoff_note = f"""# Lattice macOS Alpha Handoff

Status: close-person alpha  
Artifact: `{artifact_basename}`

## What is included

- app bundle: `{paths.app_bundle.name}`
- signed/notarized release zip: `{paths.zip_path.name}` if the maintainer completed the Gatekeeper-ready path
- local alpha config template: `{paths.config_example_copy_path.name}`

## Current honesty bar

- This build is for trusted close-person alpha testers.
- The app may still be blocked by macOS Gatekeeper if the maintainer has not completed Developer ID signing and notarization.
- Do not treat this as a general-public installer.

## Maintainer checklist before sending

1. Confirm the bundle starts locally and serves `/ui`.
2. Confirm `self-test --json` reports `ui_bundle=ok`.
3. Edit the config template or give the tester the exact values they should fill in for:
   - `paths.obsidian_vault`
   - `paths.zotero_base_dir`
4. Send this note together with the app artifact and config template.

## Tester install path

1. Unzip the app artifact if you received a zip.
2. Move `Lattice.app` into `/Applications` or another user-controlled folder.
3. Copy `{paths.config_example_copy_path.name}` to:
   `~/Library/Application Support/Lattice/config/config.yaml`
4. Edit that `config.yaml` with your real Obsidian and Zotero paths.
5. Launch the app.

## If macOS warns on first open

- This is expected for a non-notarized alpha handoff.
- Only proceed if you trust the maintainer and the source of the file.
- Prefer an assisted first-run with the maintainer instead of broad self-serve distribution.

## Optional terminal checks

```bash
PAPERPIPE_INSTALL_LAYOUT=1 /Applications/Lattice.app/Contents/MacOS/Lattice self-test --json
PAPERPIPE_INSTALL_LAYOUT=1 /Applications/Lattice.app/Contents/MacOS/Lattice --no-open --port 8031
```

## Known rough edges

- Gatekeeper-ready trust distribution may still be pending.
- Windows packaged support is not part of this handoff.
- Placeholder Obsidian/Zotero paths will show `degraded` readiness until edited.
"""
    paths.alpha_handoff_path.write_text(handoff_note, encoding="utf-8")


def _submit_notary(zip_path: Path, profile: str, output_path: Path) -> dict[str, object]:
    result = _run(
        [
            "xcrun",
            "notarytool",
            "submit",
            str(zip_path),
            "--keychain-profile",
            profile,
            "--wait",
            "--output-format",
            "json",
        ],
        capture_output=True,
    )
    output_path.write_text(result.stdout, encoding="utf-8")
    return json.loads(result.stdout)


def _fetch_notary_log(submission_id: str, profile: str, output_path: Path) -> None:
    _run(
        [
            "xcrun",
            "notarytool",
            "log",
            "--keychain-profile",
            profile,
            submission_id,
            str(output_path),
        ]
    )


def _staple_and_validate(app_bundle: Path) -> None:
    _run(["xcrun", "stapler", "staple", str(app_bundle)])
    _run(["xcrun", "stapler", "validate", str(app_bundle)])


def _assess_gatekeeper(app_bundle: Path) -> str:
    return _run_combined(["spctl", "--assess", "--type", "execute", "-v", str(app_bundle)]).strip()


def _list_codesign_identities() -> list[str]:
    if shutil.which("security") is None:
        return []
    result = _run_no_check(["security", "find-identity", "-v", "-p", "codesigning"])
    identities: list[str] = []
    for line in (result.stdout or "").splitlines():
        match = re.search(r'"([^"]+)"', line)
        if match:
            identities.append(match.group(1))
    return identities


def _match_requested_identity(available_identities: list[str], requested_identity: str) -> str | None:
    requested = requested_identity.strip()
    if not requested:
        return None
    for identity in available_identities:
        if identity == requested or requested in identity:
            return identity
    return None


def _check_notary_profile(profile: str) -> tuple[bool, str | None]:
    requested = profile.strip()
    if not requested:
        return False, None
    if shutil.which("xcrun") is None:
        return False, "xcrun is not available"
    result = _run_no_check(
        ["xcrun", "notarytool", "history", "-p", requested, "--output-format", "json"]
    )
    detail = (result.stdout or "").strip() or None
    return result.returncode == 0, detail


def evaluate_release_preflight(
    *,
    paths: ReleasePaths,
    tools: dict[str, bool],
    available_identities: list[str],
    requested_identity: str,
    requested_notary_profile: str,
    notary_profile_available: bool,
    notary_profile_detail: str | None,
) -> ReleasePreflight:
    artifacts = {
        "app_bundle": paths.app_bundle.exists(),
        "cli_binary": paths.cli_binary.exists(),
        "support_dir": paths.support_dir.exists(),
    }

    requested_identity_value = requested_identity.strip() or None
    requested_notary_profile_value = requested_notary_profile.strip() or None
    matching_identity = (
        _match_requested_identity(available_identities, requested_identity)
        if requested_identity_value
        else None
    )

    local_release_ready = (
        tools.get("codesign", False)
        and tools.get("ditto", False)
        and artifacts["app_bundle"]
        and artifacts["cli_binary"]
    )
    gatekeeper_release_ready = (
        local_release_ready
        and tools.get("xcrun", False)
        and tools.get("spctl", False)
        and matching_identity is not None
        and bool(requested_notary_profile_value)
        and notary_profile_available
    )

    blockers: list[str] = []
    next_steps: list[str] = []

    if not artifacts["app_bundle"]:
        blockers.append("Missing dist/Lattice.app")
        next_steps.append("Run the PyInstaller bundle build before the release path.")
    if not artifacts["cli_binary"]:
        blockers.append("Missing dist/lattice")
        next_steps.append("Run the PyInstaller bundle build before the release path.")
    if not tools.get("codesign", False):
        blockers.append("codesign is not available")
        next_steps.append("Install Xcode command line tools on macOS.")
    if not tools.get("ditto", False):
        blockers.append("ditto is not available")
        next_steps.append("Install the default macOS command-line tools.")

    if requested_identity_value and matching_identity is None:
        blockers.append(f"Requested signing identity is not available: {requested_identity_value}")
        next_steps.append("Install a Developer ID Application certificate in Keychain or update the identity value.")
    elif not available_identities:
        blockers.append("No code-signing identities are currently available")
        next_steps.append("Install a Developer ID Application certificate in Keychain before notarized release.")

    if requested_notary_profile_value and not notary_profile_available:
        blockers.append(f"Requested notary profile is not available: {requested_notary_profile_value}")
        next_steps.append(
            "Create the notarytool Keychain profile with `xcrun notarytool store-credentials <profile>`."
        )
    elif not requested_notary_profile_value:
        blockers.append("No notary profile has been configured")
        next_steps.append(
            "Create a notarytool Keychain profile and set PAPERPIPE_MACOS_NOTARY_PROFILE for Gatekeeper-ready release."
        )

    if not tools.get("xcrun", False):
        blockers.append("xcrun is not available")
    if not tools.get("spctl", False):
        blockers.append("spctl is not available")

    if not local_release_ready:
        status = "error"
    elif gatekeeper_release_ready:
        status = "ok"
    else:
        status = "warn"

    deduped_next_steps = list(dict.fromkeys(next_steps))

    return ReleasePreflight(
        status=status,
        local_release_ready=local_release_ready,
        gatekeeper_release_ready=gatekeeper_release_ready,
        requested_identity=requested_identity_value,
        requested_notary_profile=requested_notary_profile_value,
        matching_identity=matching_identity,
        notary_profile_available=notary_profile_available,
        notary_profile_detail=notary_profile_detail,
        available_identities=available_identities,
        tools=tools,
        artifacts=artifacts,
        blockers=blockers,
        next_steps=deduped_next_steps,
    )


def collect_release_preflight(paths: ReleasePaths, identity: str, notary_profile: str) -> ReleasePreflight:
    tools = {
        "codesign": shutil.which("codesign") is not None,
        "ditto": shutil.which("ditto") is not None,
        "xcrun": shutil.which("xcrun") is not None,
        "spctl": shutil.which("spctl") is not None,
        "security": shutil.which("security") is not None,
    }
    available_identities = _list_codesign_identities()
    notary_profile_available, notary_profile_detail = _check_notary_profile(notary_profile)
    return evaluate_release_preflight(
        paths=paths,
        tools=tools,
        available_identities=available_identities,
        requested_identity=identity,
        requested_notary_profile=notary_profile,
        notary_profile_available=notary_profile_available,
        notary_profile_detail=notary_profile_detail,
    )


def _write_manifest(
    *,
    paths: ReleasePaths,
    artifact_basename: str,
    sign_enabled: bool,
    notarize_enabled: bool,
    identity: str,
    notary_profile: str,
    gatekeeper_output: str | None,
    notary_payload: dict[str, object] | None,
) -> None:
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact_basename": artifact_basename,
        "paths": {
            key: str(value)
            for key, value in asdict(paths).items()
        },
        "signing": {
            "enabled": sign_enabled,
            "identity": identity if identity else None,
        },
        "notarization": {
            "enabled": notarize_enabled,
            "profile": notary_profile if notary_profile else None,
            "submit_result": notary_payload,
        },
        "gatekeeper_assessment": gatekeeper_output,
        "hashes": {
            "cli_binary_sha256": _sha256(paths.cli_binary),
            "release_zip_sha256": _sha256(paths.zip_path),
        },
    }
    paths.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build, sign, notarize, staple, and verify the macOS personal-runtime release around the current "
            "PyInstaller-based Lattice bundle."
        )
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build the current PyInstaller bundle before the release steps.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="When used with --build, ask the bundle build to clean temporary artifacts first.",
    )
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="When used with --build, reuse the existing frontend/dist output.",
    )
    parser.add_argument(
        "--identity",
        default=os.getenv("PAPERPIPE_MACOS_SIGN_IDENTITY", ""),
        help=(
            "Developer ID Application signing identity. Defaults to PAPERPIPE_MACOS_SIGN_IDENTITY. "
            "Leave empty to reuse the current local signature without re-signing."
        ),
    )
    parser.add_argument(
        "--notary-profile",
        default=os.getenv("PAPERPIPE_MACOS_NOTARY_PROFILE", ""),
        help=(
            "Keychain profile name created with `xcrun notarytool store-credentials`. "
            "Defaults to PAPERPIPE_MACOS_NOTARY_PROFILE."
        ),
    )
    parser.add_argument(
        "--release-dir",
        default=str(DEFAULT_RELEASE_DIR),
        help="Directory where the release zip, manifest, and notarization logs should be written.",
    )
    parser.add_argument(
        "--artifact-basename",
        default=default_artifact_basename(platform.machine()),
        help="Base filename for the release zip and manifest.",
    )
    parser.add_argument(
        "--check-prereqs",
        action="store_true",
        help="Only inspect release prerequisites and print a JSON readiness report.",
    )
    args = parser.parse_args()

    if sys.platform != "darwin":
        raise SystemExit("This release script is macOS-only.")

    sign_enabled, notarize_enabled = resolve_release_mode(args.identity, args.notary_profile)
    paths = build_release_paths(ROOT, args.artifact_basename, Path(args.release_dir))

    if args.check_prereqs:
        report = collect_release_preflight(paths, args.identity, args.notary_profile)
        print(json.dumps(asdict(report), indent=2))
        requested_gatekeeper_path = bool(args.identity.strip()) or bool(args.notary_profile.strip())
        if not report.local_release_ready:
            return 1
        if requested_gatekeeper_path and not report.gatekeeper_release_ready:
            return 1
        return 0

    _require_tool("codesign")
    _require_tool("ditto")
    if notarize_enabled:
        _require_tool("xcrun")
        _require_tool("spctl")

    if args.build:
        _build_bundle(clean=args.clean, skip_frontend_build=args.skip_frontend_build)

    _ensure_artifacts_exist(paths)
    paths.release_dir.mkdir(parents=True, exist_ok=True)
    _copy_handoff_files(paths, args.artifact_basename)

    if sign_enabled:
        _codesign(paths.cli_binary, args.identity, deep=False)
        _codesign(paths.app_bundle, args.identity, deep=True)

    _verify_codesign(paths)
    _package_zip(paths.app_bundle, paths.zip_path)

    gatekeeper_output: str | None = None
    notary_payload: dict[str, object] | None = None

    if notarize_enabled:
        notary_payload = _submit_notary(paths.zip_path, args.notary_profile, paths.notary_submit_path)
        submission_id = str(notary_payload.get("id") or "").strip()
        status = str(notary_payload.get("status") or "").strip().lower()

        if status != "accepted":
            if submission_id:
                _fetch_notary_log(submission_id, args.notary_profile, paths.notary_log_path)
            raise SystemExit(
                f"Notarization did not complete successfully. Status={notary_payload.get('status')!r}. "
                f"See {paths.notary_submit_path} and {paths.notary_log_path}."
            )

        _staple_and_validate(paths.app_bundle)
        gatekeeper_output = _assess_gatekeeper(paths.app_bundle)
        # Re-zip after stapling so the distributed archive contains the stapled bundle.
        _package_zip(paths.app_bundle, paths.zip_path)

    _write_manifest(
        paths=paths,
        artifact_basename=args.artifact_basename,
        sign_enabled=sign_enabled,
        notarize_enabled=notarize_enabled,
        identity=args.identity,
        notary_profile=args.notary_profile,
        gatekeeper_output=gatekeeper_output,
        notary_payload=notary_payload,
    )

    summary = {
        "app_bundle": str(paths.app_bundle),
        "cli_binary": str(paths.cli_binary),
        "release_zip": str(paths.zip_path),
        "alpha_handoff_note": str(paths.alpha_handoff_path),
        "config_example_copy": str(paths.config_example_copy_path),
        "manifest": str(paths.manifest_path),
        "signed": sign_enabled,
        "notarized": notarize_enabled,
        "gatekeeper_assessment": gatekeeper_output,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
