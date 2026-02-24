from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.runtime_paths import goldset_root as default_goldset_root


@dataclass(frozen=True)
class GoldRecord:
    paper_id: str
    payload: dict[str, Any]
    source_path: Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stable_bucket(paper_id: str) -> int:
    digest = hashlib.sha256(paper_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % 10


def load_accepted_records(accepted_dir: Path) -> list[GoldRecord]:
    if not accepted_dir.exists():
        return []
    records: list[GoldRecord] = []
    for path in sorted(accepted_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        paper_id = str(payload.get("paper_id") or "").strip()
        if not paper_id:
            continue
        records.append(GoldRecord(paper_id=paper_id, payload=payload, source_path=path))
    return records


def split_records(records: list[GoldRecord]) -> tuple[list[GoldRecord], list[GoldRecord]]:
    train: list[GoldRecord] = []
    eval_: list[GoldRecord] = []
    seen: set[str] = set()
    for rec in sorted(records, key=lambda r: r.paper_id):
        if rec.paper_id in seen:
            raise RuntimeError(f"duplicate paper_id in accepted set: {rec.paper_id}")
        seen.add(rec.paper_id)
        bucket = stable_bucket(rec.paper_id)
        if bucket < 8:
            train.append(rec)
        else:
            eval_.append(rec)
    return train, eval_


def _to_jsonl_record(rec: GoldRecord) -> dict[str, Any]:
    payload = rec.payload
    return {
        "paper_id": rec.paper_id,
        "teacher_output": payload.get("teacher_output"),
        "prior_output": payload.get("manifest", {}).get("inputs", {}).get("prior_output_file"),
        "reason_codes": payload.get("reason_codes", []),
        "bundle_dir": payload.get("bundle_dir"),
        "source_file": str(rec.source_path),
    }


def write_splits(
    *,
    records: list[GoldRecord],
    output_root: Path,
    version_tag: str,
) -> dict[str, Any]:
    train, eval_ = split_records(records)
    split_root = output_root / version_tag
    split_root.mkdir(parents=True, exist_ok=True)

    train_path = split_root / "train.jsonl"
    eval_path = split_root / "eval.jsonl"

    with train_path.open("w", encoding="utf-8") as f:
        for rec in train:
            f.write(json.dumps(_to_jsonl_record(rec), ensure_ascii=False) + "\n")

    with eval_path.open("w", encoding="utf-8") as f:
        for rec in eval_:
            f.write(json.dumps(_to_jsonl_record(rec), ensure_ascii=False) + "\n")

    train_ids = {rec.paper_id for rec in train}
    eval_ids = {rec.paper_id for rec in eval_}
    overlap = sorted(train_ids.intersection(eval_ids))

    meta = {
        "schema_version": "goldset_split.v1",
        "generated_at": _utc_now(),
        "version_tag": version_tag,
        "total": len(records),
        "train_count": len(train),
        "eval_count": len(eval_),
        "overlap_count": len(overlap),
        "overlap_paper_ids": overlap,
        "rule": "hash(paper_id) % 10 < 8 => train else eval",
        "train_path": str(train_path),
        "eval_path": str(eval_path),
    }
    (split_root / "split_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic train/eval JSONL from goldset/accepted.")
    parser.add_argument(
        "--goldset-root",
        default=str(default_goldset_root()),
        help="Goldset root directory",
    )
    parser.add_argument("--accepted-dir", default="", help="Accepted directory override (default: <goldset>/accepted)")
    parser.add_argument("--output-root", default="", help="Split output root override (default: <goldset>/splits)")
    parser.add_argument("--version-tag", default="", help="Split version tag (default: vYYYYMMDD)")
    args = parser.parse_args()

    g_root = Path(args.goldset_root).expanduser().resolve()
    accepted_dir = Path(args.accepted_dir).expanduser().resolve() if args.accepted_dir else g_root / "accepted"
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else g_root / "splits"
    version_tag = args.version_tag.strip() or f"v{datetime.now(timezone.utc).strftime('%Y%m%d')}"

    records = load_accepted_records(accepted_dir)
    meta = write_splits(records=records, output_root=output_root, version_tag=version_tag)

    print(f"[goldset-build] accepted_records={len(records)}")
    print(f"[goldset-build] version={version_tag}")
    print(f"[goldset-build] train={meta['train_count']} eval={meta['eval_count']} overlap={meta['overlap_count']}")
    print(f"[goldset-build] train_path={meta['train_path']}")
    print(f"[goldset-build] eval_path={meta['eval_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
