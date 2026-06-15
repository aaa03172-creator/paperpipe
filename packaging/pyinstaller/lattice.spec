# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules


ROOT = Path.cwd()
ASSET_ROOT = Path(os.environ.get("PAPERPIPE_BUNDLE_ASSET_ROOT", str(ROOT))).resolve()
BUNDLE_PROFILE = os.environ.get("PAPERPIPE_BUNDLE_PROFILE", "full").strip().lower() or "full"

if BUNDLE_PROFILE not in {"full", "cloud-ui"}:
    raise ValueError(f"Unsupported PAPERPIPE_BUNDLE_PROFILE={BUNDLE_PROFILE!r}")

CLOUD_UI_EXCLUDES = [
    "cv2",
    "docling",
    "easyocr",
    "matplotlib",
    "onnx",
    "onnxruntime",
    "PIL",
    "scipy",
    "sentence_transformers",
    "sklearn",
    "tensorflow",
    "torch",
    "torchvision",
    "transformers",
]


def _collect_tree(source: Path, destination_root: str) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative_parent = path.relative_to(source).parent
        destination = Path(destination_root) / relative_parent
        files.append((str(path), str(destination)))
    return files


def _collect_optional_submodules(module_name: str) -> list[str]:
    try:
        return collect_submodules(module_name)
    except Exception:
        return []


datas = [
    *_collect_tree(ASSET_ROOT / "frontend" / "dist", "frontend/dist"),
    *_collect_tree(ASSET_ROOT / "frontend" / "styles", "frontend/styles"),
    (str(ROOT / "config.example.yaml"), "."),
]

submission_demo_root = ROOT / "packaging" / "submission_demo"
if submission_demo_root.exists():
    datas.extend(_collect_tree(submission_demo_root, "submission_demo"))


a = Analysis(
    [str(ROOT / "src" / "cli.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        *collect_submodules("backend"),
        *_collect_optional_submodules("google.cloud.firestore"),
        *_collect_optional_submodules("google.cloud.storage"),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=CLOUD_UI_EXCLUDES if BUNDLE_PROFILE == "cloud-ui" else [],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

cli_exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="lattice",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == "darwin":
    app_exe = EXE(
        pyz,
        a.scripts,
        [],
        name="Lattice",
        exclude_binaries=True,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    app_collect = COLLECT(
        app_exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="Lattice-support",
    )

    app_bundle = BUNDLE(
        app_collect,
        name="Lattice.app",
        version="3.1.0",
        bundle_identifier="ai.paperpipe.lattice",
        icon=str(ROOT / "packaging" / "pyinstaller" / "lattice.icns"),
        info_plist={
            "CFBundleName": "Lattice",
            "CFBundleDisplayName": "Lattice",
            "CFBundleShortVersionString": "3.1.0",
            "CFBundleVersion": "3.1.0",
            "NSAppTransportSecurity": {
                "NSAllowsLocalNetworking": True,
            },
        },
    )
