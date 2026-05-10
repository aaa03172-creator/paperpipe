# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules


ROOT = Path.cwd()
ASSET_ROOT = Path(os.environ.get("PAPERPIPE_BUNDLE_ASSET_ROOT", str(ROOT))).resolve()


def _collect_tree(source: Path, destination_root: str) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative_parent = path.relative_to(source).parent
        destination = Path(destination_root) / relative_parent
        files.append((str(path), str(destination)))
    return files


datas = [
    *_collect_tree(ASSET_ROOT / "frontend" / "dist", "frontend/dist"),
    *_collect_tree(ASSET_ROOT / "frontend" / "styles", "frontend/styles"),
    (str(ROOT / "config.example.yaml"), "."),
]


a = Analysis(
    [str(ROOT / "src" / "cli.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("backend"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
        info_plist={
            "CFBundleName": "Lattice",
            "CFBundleDisplayName": "Lattice",
            "CFBundleShortVersionString": "3.1.0",
            "CFBundleVersion": "3.1.0",
        },
    )
