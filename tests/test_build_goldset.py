import json
from pathlib import Path

from scripts.build_goldset import load_accepted_records, write_splits


def _write_record(path: Path, paper_id: str) -> None:
    path.write_text(
        json.dumps(
            {
                "paper_id": paper_id,
                "bundle_dir": f"/tmp/{paper_id}",
                "reason_codes": [],
                "teacher_output": {
                    "doc_id": paper_id,
                    "claims": [],
                },
                "manifest": {"inputs": {"prior_output_file": "prior_output.json"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _paper_ids_from_jsonl(path: Path) -> set[str]:
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        out.add(json.loads(line)["paper_id"])
    return out


def test_build_goldset_split_is_deterministic_and_leak_free(tmp_path: Path) -> None:
    accepted_dir = tmp_path / "goldset" / "accepted"
    output_root = tmp_path / "goldset" / "splits"
    accepted_dir.mkdir(parents=True, exist_ok=True)

    for paper_id in ["paper-a", "paper-b", "paper-c", "paper-d", "paper-e", "paper-f"]:
        _write_record(accepted_dir / f"{paper_id}.json", paper_id)

    records = load_accepted_records(accepted_dir)
    meta_v1 = write_splits(records=records, output_root=output_root, version_tag="v1")
    meta_v2 = write_splits(records=records, output_root=output_root, version_tag="v2")

    train_v1 = (output_root / "v1" / "train.jsonl").read_text(encoding="utf-8")
    train_v2 = (output_root / "v2" / "train.jsonl").read_text(encoding="utf-8")
    eval_v1 = (output_root / "v1" / "eval.jsonl").read_text(encoding="utf-8")
    eval_v2 = (output_root / "v2" / "eval.jsonl").read_text(encoding="utf-8")

    assert train_v1 == train_v2
    assert eval_v1 == eval_v2

    train_ids = _paper_ids_from_jsonl(output_root / "v1" / "train.jsonl")
    eval_ids = _paper_ids_from_jsonl(output_root / "v1" / "eval.jsonl")
    assert train_ids.isdisjoint(eval_ids)

    assert meta_v1["overlap_count"] == 0
    assert meta_v2["overlap_count"] == 0
