#!/usr/bin/env python3
import argparse
import json
import hashlib
from pathlib import Path


def _load_summary(snapshot_dir: Path) -> dict:
    summary_path = snapshot_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary missing: {summary_path}")
    with summary_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _list_files(root: Path) -> set[str]:
    files = set()
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            files.add(rel)
    return files


def diff_snapshots(base: Path, target: Path) -> dict:
    base_summary = _load_summary(base)
    target_summary = _load_summary(target)

    base_files = _list_files(base)
    target_files = _list_files(target)

    added_files = sorted(target_files - base_files)
    removed_files = sorted(base_files - target_files)
    common_files = sorted(base_files & target_files)

    changed_files = []
    for rel in common_files:
        b = base / rel
        t = target / rel
        if _sha256(b) != _sha256(t):
            changed_files.append(rel)

    return {
        "base_run_id": base_summary.get("run_id"),
        "target_run_id": target_summary.get("run_id"),
        "added": len(added_files),
        "removed": len(removed_files),
        "changed": len(changed_files),
        "added_files": added_files,
        "removed_files": removed_files,
        "changed_files": changed_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PaperPipe PR#1 snapshot diff tool")
    parser.add_argument("--base", required=True, help="Base snapshot directory")
    parser.add_argument("--target", required=True, help="Target snapshot directory")
    parser.add_argument("--out", required=True, help="JSON diff output path")
    parser.add_argument("--out-text", default=None, help="Optional human-readable diff output path")
    args = parser.parse_args()

    base = Path(args.base)
    target = Path(args.target)
    out = Path(args.out)
    diff = diff_snapshots(base, target)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=2)

    out_text = Path(args.out_text) if args.out_text else out.with_suffix(".txt")
    out_text.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"Base: {base}",
        f"Target: {target}",
        f"base_run_id={diff['base_run_id']}",
        f"target_run_id={diff['target_run_id']}",
        f"added={diff['added']}",
        f"removed={diff['removed']}",
        f"changed={diff['changed']}",
    ]
    if diff["changed_files"]:
        lines.append("changed_files:")
        for rel in diff["changed_files"]:
            lines.append(f"- {rel}")
    with out_text.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("[diff_snapshots] done")
    print(f"  base:   {base}")
    print(f"  target: {target}")
    print(f"  added={diff['added']} removed={diff['removed']} changed={diff['changed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
