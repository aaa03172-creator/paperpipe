import json
import subprocess
from pathlib import Path


def _tracked_goldset_manifests(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "goldset/manifests/*.json"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [repo_root / line for line in result.stdout.splitlines() if line.strip()]


def _manifest_rows(payload: dict) -> list[dict]:
    for key in ("documents", "runs", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def test_tracked_goldset_manifests_have_stable_eval_identity() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest_paths = _tracked_goldset_manifests(repo_root)

    assert manifest_paths
    for path in manifest_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("eval_id") == path.stem
        assert str(payload.get("subset") or "").strip()

        rows = _manifest_rows(payload)
        assert rows, f"{path} should expose documents[], runs[], or items[]"

        case_ids = [str(row.get("case_id") or "").strip() for row in rows]
        assert all(case_ids), f"{path} has row(s) without case_id"
        assert len(case_ids) == len(set(case_ids)), f"{path} has duplicate case_id values"
