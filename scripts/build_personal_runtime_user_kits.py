from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import release_macos_personal_runtime as mac_release

DEFAULT_OUTPUT_DIR = ROOT / "dist" / "release" / "user-kits"
WINDOWS_KIT_NAME = "Lattice-windows-source-alpha-kit"
MACOS_KIT_NAME = "Lattice-macos-alpha-kit"

WINDOWS_SNAPSHOT_DIRS = [
    "backend",
    "src",
]

WINDOWS_SNAPSHOT_FILES = [
    "config.example.yaml",
    "requirements.txt",
    "pyproject.toml",
]

WINDOWS_SCRIPT_FILES = [
    "build_personal_runtime_bundle.py",
    "check_windows_personal_runtime_smoke.py",
    "init_db.py",
]

REFERENCE_DOCS = [
    "docs/PERSONAL_RUNTIME_INSTALL.md",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))


def _zip_dir(source_dir: Path, zip_path: Path) -> Path:
    if zip_path.exists():
        zip_path.unlink()
    archive_path = shutil.make_archive(
        str(zip_path.with_suffix("")),
        "zip",
        root_dir=str(source_dir.parent),
        base_dir=source_dir.name,
    )
    return Path(archive_path).resolve()


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def _ensure_macos_release_artifacts(artifact_basename: str, *, build_release: bool) -> mac_release.ReleasePaths:
    paths = mac_release.build_release_paths(ROOT, artifact_basename)
    required = [
        paths.zip_path,
        paths.config_example_copy_path,
        paths.manifest_path,
        paths.alpha_handoff_path,
    ]
    if all(path.exists() for path in required):
        return paths
    if not build_release:
        missing = ", ".join(str(path) for path in required if not path.exists())
        raise FileNotFoundError(
            f"Missing macOS release artifacts: {missing}. "
            "Run scripts/release_macos_personal_runtime.py first or pass --build-macos-release."
        )
    cmd = [sys.executable, str(ROOT / "scripts" / "release_macos_personal_runtime.py")]
    _run(cmd)
    return paths


def _copy_reference_docs(kit_root: Path, docs: list[str]) -> None:
    reference_root = kit_root / "reference"
    for relpath in docs:
        src = ROOT / relpath
        _copy_file(src, reference_root / Path(relpath).name)


def _kit_product_guide(os_name: str, current_shape: str, install_shape: str) -> str:
    return f"""
# 제품 안내

Lattice는 현재 여러 사용자가 함께 쓰는 공용 워크스페이스가 아니라, 개인별로 분리된 personal runtime 형태로 제공됩니다.

## 이 제품이 지향하는 방식

- 사용자 1명당 런타임 1개
- 서로 섞이지 않는 개인 상태와 저장공간
- 사용자 소유의 config, state, artifact 경계
- 현재 연구 워크플로를 위한 로컬 백엔드 + 브라우저 UI

## 이 키트로 지금 할 수 있는 것

- 현재 `lattice` 실행 방식에 맞춘 로컬 실행
- 사용자 범위 경로에 생성되는 runtime DB와 앱 전용 저장공간
- Obsidian, Zotero 같은 외부 경로의 로컬 설정
- 포함된 프런트 자산으로 제공되는 현재 `/ui` 화면

## 이 키트의 {os_name} 지원 형태

- 현재 지원 수준: `{current_shape}`
- 설치 형태: `{install_shape}`

## 아직 아닌 것

- 팀 공용 서버
- 누구나 바로 설치하는 완성형 앱스토어식 설치기
- 범용 워크스페이스 플랫폼

## 솔직한 기대치

이 키트는 close-person alpha 용도입니다. 설치 안내를 함께 전달하는 것이 좋고, 첫 실행에서는 어느 정도 도움이나 확인이 필요할 수 있습니다.
"""


def _feedback_template(os_name: str, install_command: str, start_command: str) -> str:
    return f"""
# 피드백 노트

처음 설치하고 처음 실행한 뒤에 아래 내용을 간단히 적어주세요.

## 사용 환경

- OS: `{os_name}`
- 기기:
- Python 버전:

## 설치 결과

- 설치가 끝까지 잘 되었나요?
- 아니라면 어느 단계에서 막혔나요?
- 사용한 명령: `{install_command}`

## 첫 실행 결과

- 앱이 실행되었나요?
- `/ui` 화면이 정상적으로 열리거나 로드되었나요?
- 사용한 명령: `{start_command}`

## 설정 파일 작성

- `config.yaml` 수정은 어렵지 않았나요?
- Obsidian, Zotero 경로 설명은 이해하기 쉬웠나요?

## 가장 불편했던 점

- 가장 헷갈리거나 막혔던 부분은 무엇이었나요?

## 가장 좋았던 점

- 바로 도움이 된 부분은 무엇이었나요?

## 버그 또는 막힘

- 가능하면 스크린샷, 터미널 출력, 실패한 정확한 단계를 함께 적어주세요.

## 전체 의견

- 다시 써볼 의향이 있나요?
- 더 넓게 공유하려면 무엇이 먼저 좋아져야 하나요?
"""


def _macos_start_here(artifact_basename: str) -> str:
    return f"""
# 먼저 읽어주세요

이 폴더는 현재 Lattice의 macOS close-person alpha 배포용 키트입니다.

## 먼저 할 일 3가지

1. `01_PRODUCT_GUIDE.md`를 읽습니다.
2. `02_INSTALL_GUIDE.md` 순서대로 설치합니다.
3. 첫 실행 후 `04_FEEDBACK_NOTE.md`를 적어주세요.

## 포함된 파일

- `files/{artifact_basename}.zip`
- `files/{artifact_basename}.config.example.yaml`

## 현재 지원 범위

- 이 키트는 실제로 동작하는 macOS alpha handoff 기준입니다.
- 아직 Gatekeeper-ready 공개 배포물은 아닙니다.
- macOS에서 첫 실행 경고가 뜰 수 있습니다.

## 참고

- `reference/`와 `files/*.alpha-handoff.md` 안의 일부 문서는 maintainer 참고용이라 영문일 수 있습니다.
"""


def _windows_start_here() -> str:
    return """
# 먼저 읽어주세요

이 폴더는 현재 Lattice의 Windows source-alpha 배포용 키트입니다.

## 먼저 할 일 3가지

1. `01_PRODUCT_GUIDE.md`를 읽습니다.
2. `02_INSTALL_GUIDE.md` 순서대로 설치합니다.
3. 첫 실행 후 `04_FEEDBACK_NOTE.md`를 적어주세요.

## 포함된 구성

- `app/`에는 현재 personal runtime 실행에 필요한 source snapshot이 들어 있습니다.
- `install_and_smoke_windows.ps1`는 첫 설치와 기본 점검을 한 번에 수행합니다.
- `start_lattice_windows.ps1`는 설치 후 일반 실행용 스크립트입니다.

## 현재 지원 범위

- 이 키트는 from-source Windows alpha 기준입니다.
- 아직 패키지된 `.exe` 설치기는 아닙니다.
- SmartScreen/code-signing 지원은 포함되지 않습니다.

## 참고

- `reference/` 안의 일부 문서는 maintainer 참고용이라 영문일 수 있습니다.
"""


def _macos_install_guide(artifact_basename: str) -> str:
    return f"""
# 설치 안내

## 준비물

- macOS
- `/Applications`로 앱을 옮길 수 있는 권한

## 설치 순서

1. `files/{artifact_basename}.zip` 파일의 압축을 풉니다.
2. `Lattice.app`를 `/Applications` 또는 사용자가 관리하는 다른 폴더로 옮깁니다.
3. `files/{artifact_basename}.config.example.yaml`를 아래 경로로 복사합니다.
   `~/Library/Application Support/Lattice/config/config.yaml`
4. `config.yaml`을 열어 아래 값을 실제 내 경로로 바꿉니다.
   `paths.obsidian_vault`
   `paths.zotero_base_dir`
5. `Lattice.app`를 실행합니다.

## 선택 확인 명령

```bash
PAPERPIPE_INSTALL_LAYOUT=1 /Applications/Lattice.app/Contents/MacOS/Lattice self-test --json
PAPERPIPE_INSTALL_LAYOUT=1 /Applications/Lattice.app/Contents/MacOS/Lattice --no-open --port 8031
```

## 참고

- `self-test`가 `degraded`로 나와도, Obsidian/Zotero 예시 경로가 아직 placeholder이면 정상일 수 있습니다.
"""


def _windows_install_guide() -> str:
    return """
# 설치 안내

## 준비물

- Windows
- Python 3.13+
- PowerShell

이 키트에는 이미 빌드된 프런트 번들이 포함되어 있어서 Node.js는 필수가 아닙니다.

## 권장 설치 경로

1. 이 폴더에서 PowerShell을 엽니다.
2. 아래 명령을 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\\install_and_smoke_windows.ps1
```

이 스크립트가 해주는 일:

- `app/requirements.txt` 기준으로 Python 의존성을 설치합니다.
- install-layout 모드를 사용하도록 맞춥니다.
- `%APPDATA%\\Lattice\\config\\config.yaml`가 없으면 생성합니다.
- `self-test --json`를 실행합니다.
- 런타임을 띄우고 `/health`, `/ui`를 점검합니다.

## 첫 설치 후 일반 실행

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\\start_lattice_windows.ps1
```

## 수동 실행을 원하면

```powershell
cd .\\app
py -3 -m pip install -r requirements.txt
py -3 scripts/check_windows_personal_runtime_smoke.py --mode source
```
"""


def _macos_cautions() -> str:
    return """
# 주의사항 및 제한

- 이 키트는 alpha 품질 기준입니다.
- Gatekeeper-ready 서명과 notarization은 아직 보류 상태입니다.
- macOS에서 첫 실행 경고가 뜰 수 있습니다.
- Obsidian/Zotero 경로가 예시값이면 `degraded`가 나올 수 있습니다.
- 이 키트는 1명 사용자, 1대 장비 기준이며 팀 공용 런타임이 아닙니다.
"""


def _windows_cautions() -> str:
    return """
# 주의사항 및 제한

- 이 키트는 alpha 품질 기준입니다.
- 이 키트는 from-source 런타임이며, 패키지된 Windows 설치기가 아닙니다.
- 기기에 Python이 설치되어 있어야 합니다.
- SmartScreen/code-signing 지원은 포함되지 않습니다.
- Obsidian/Zotero 경로가 예시값이면 `warn` 또는 `degraded`가 나올 수 있습니다.
- 이 키트는 1명 사용자, 1대 장비 기준이며 팀 공용 런타임이 아닙니다.
"""


def _write_windows_helper_scripts(kit_root: Path) -> None:
    install_script = r"""
$ErrorActionPreference = "Stop"
$kitRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appRoot = Join-Path $kitRoot "app"

Push-Location $appRoot
try {
  py -3 -m pip install -r requirements.txt
  py -3 scripts/check_windows_personal_runtime_smoke.py --mode source
}
finally {
  Pop-Location
}
"""
    start_script = r"""
$ErrorActionPreference = "Stop"
$kitRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$appRoot = Join-Path $kitRoot "app"

Push-Location $appRoot
try {
  $env:PAPERPIPE_INSTALL_LAYOUT = "1"
  py -3 -m src.cli start
}
finally {
  Pop-Location
}
"""
    _write_text(kit_root / "install_and_smoke_windows.ps1", install_script)
    _write_text(kit_root / "start_lattice_windows.ps1", start_script)


def _build_windows_app_snapshot(dest_root: Path) -> list[str]:
    app_root = dest_root / "app"
    _reset_dir(app_root)

    copied_paths: list[str] = []

    for relpath in WINDOWS_SNAPSHOT_DIRS:
        src = ROOT / relpath
        dest = app_root / relpath
        _copy_tree(src, dest)
        copied_paths.append(relpath)

    frontend_dist = ROOT / "frontend" / "dist"
    if not (frontend_dist / "index.html").exists():
        raise FileNotFoundError(
            "Built frontend bundle is missing. Run `cd frontend && npm run build` first."
        )
    _copy_tree(frontend_dist, app_root / "frontend" / "dist")
    _copy_tree(ROOT / "frontend" / "styles", app_root / "frontend" / "styles")
    copied_paths.extend(["frontend/dist", "frontend/styles"])

    packaging_root = app_root / "packaging" / "pyinstaller"
    packaging_root.mkdir(parents=True, exist_ok=True)
    _copy_file(ROOT / "packaging" / "pyinstaller" / "lattice.spec", packaging_root / "lattice.spec")
    copied_paths.append("packaging/pyinstaller/lattice.spec")

    scripts_root = app_root / "scripts"
    scripts_root.mkdir(parents=True, exist_ok=True)
    _write_text(scripts_root / "__init__.py", "")
    copied_paths.append("scripts/__init__.py")
    for filename in WINDOWS_SCRIPT_FILES:
        _copy_file(ROOT / "scripts" / filename, scripts_root / filename)
        copied_paths.append(f"scripts/{filename}")

    for relpath in WINDOWS_SNAPSHOT_FILES:
        _copy_file(ROOT / relpath, app_root / relpath)
        copied_paths.append(relpath)

    return sorted(copied_paths)


def _write_macos_docs(kit_root: Path, artifact_basename: str) -> None:
    _write_text(kit_root / "00_START_HERE.md", _macos_start_here(artifact_basename))
    _write_text(
        kit_root / "01_PRODUCT_GUIDE.md",
        _kit_product_guide("macOS", "close-person alpha", "signed-or-unsigned app zip handoff"),
    )
    _write_text(kit_root / "02_INSTALL_GUIDE.md", _macos_install_guide(artifact_basename))
    _write_text(kit_root / "03_CAUTIONS_AND_LIMITS.md", _macos_cautions())
    _write_text(
        kit_root / "04_FEEDBACK_NOTE.md",
        _feedback_template(
            "macOS",
            f"Unzip files/{artifact_basename}.zip and copy the config template into ~/Library/Application Support/Lattice/config/config.yaml",
            "/Applications/Lattice.app/Contents/MacOS/Lattice --no-open --port 8031",
        ),
    )


def _write_windows_docs(kit_root: Path) -> None:
    _write_text(kit_root / "00_START_HERE.md", _windows_start_here())
    _write_text(
        kit_root / "01_PRODUCT_GUIDE.md",
        _kit_product_guide("Windows", "from-source alpha", "source snapshot plus PowerShell helper scripts"),
    )
    _write_text(kit_root / "02_INSTALL_GUIDE.md", _windows_install_guide())
    _write_text(kit_root / "03_CAUTIONS_AND_LIMITS.md", _windows_cautions())
    _write_text(
        kit_root / "04_FEEDBACK_NOTE.md",
        _feedback_template(
            "Windows",
            ".\\install_and_smoke_windows.ps1",
            ".\\start_lattice_windows.ps1",
        ),
    )


def build_macos_kit(output_dir: Path, artifact_basename: str, *, build_release: bool) -> tuple[Path, Path]:
    release_paths = _ensure_macos_release_artifacts(artifact_basename, build_release=build_release)

    kit_root = (output_dir / MACOS_KIT_NAME).resolve()
    _reset_dir(kit_root)
    files_root = kit_root / "files"
    files_root.mkdir(parents=True, exist_ok=True)

    copied_files: dict[str, str] = {}
    for src in (
        release_paths.zip_path,
        release_paths.config_example_copy_path,
        release_paths.manifest_path,
        release_paths.alpha_handoff_path,
    ):
        dest = files_root / src.name
        _copy_file(src, dest)
        copied_files[dest.name] = _sha256(dest)

    _write_macos_docs(kit_root, artifact_basename)
    _copy_reference_docs(kit_root, REFERENCE_DOCS + ["docs/MACOS_PERSONAL_RUNTIME_ALPHA_HANDOFF.md"])

    manifest = {
        "kit_name": MACOS_KIT_NAME,
        "platform": "macOS",
        "support_level": "close-person alpha",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact_basename": artifact_basename,
        "files": copied_files,
    }
    _write_text(kit_root / "KIT_MANIFEST.json", json.dumps(manifest, indent=2))

    zip_path = _zip_dir(kit_root, output_dir / f"{MACOS_KIT_NAME}.zip")
    return kit_root, zip_path


def build_windows_kit(output_dir: Path) -> tuple[Path, Path]:
    kit_root = (output_dir / WINDOWS_KIT_NAME).resolve()
    _reset_dir(kit_root)

    snapshot_items = _build_windows_app_snapshot(kit_root)
    _write_windows_docs(kit_root)
    _write_windows_helper_scripts(kit_root)
    _copy_reference_docs(kit_root, REFERENCE_DOCS + ["docs/WINDOWS_PERSONAL_RUNTIME_ALPHA.md"])

    important_checksums = {}
    for relpath in [
        "app/config.example.yaml",
        "app/requirements.txt",
        "app/frontend/dist/index.html",
        "app/scripts/check_windows_personal_runtime_smoke.py",
        "install_and_smoke_windows.ps1",
        "start_lattice_windows.ps1",
    ]:
        path = kit_root / relpath
        important_checksums[relpath] = _sha256(path)

    manifest = {
        "kit_name": WINDOWS_KIT_NAME,
        "platform": "Windows",
        "support_level": "from-source alpha",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_items": snapshot_items,
        "important_checksums": important_checksums,
    }
    _write_text(kit_root / "KIT_MANIFEST.json", json.dumps(manifest, indent=2))

    zip_path = _zip_dir(kit_root, output_dir / f"{WINDOWS_KIT_NAME}.zip")
    return kit_root, zip_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assemble macOS and Windows personal-runtime user handoff kits."
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory that will receive the generated kit folders and kit zips.",
    )
    parser.add_argument(
        "--artifact-basename",
        default=mac_release.default_artifact_basename(platform.machine()),
        help="macOS artifact basename to pull from dist/release.",
    )
    parser.add_argument(
        "--build-macos-release",
        action="store_true",
        help="Run the current macOS release script if the expected release files are missing.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    mac_root, mac_zip = build_macos_kit(
        output_dir,
        args.artifact_basename,
        build_release=args.build_macos_release,
    )
    windows_root, windows_zip = build_windows_kit(output_dir)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "kits": {
            "macos": {
                "folder": str(mac_root),
                "zip": str(mac_zip),
            },
            "windows": {
                "folder": str(windows_root),
                "zip": str(windows_zip),
            },
        },
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
