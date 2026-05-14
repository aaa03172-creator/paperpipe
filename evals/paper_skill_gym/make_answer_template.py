from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from evals.paper_skill_gym.schemas import answer_template_from_probe, load_probes


def build_answer_template(probes_dir: Path) -> list[dict]:
    probes = load_probes(probes_dir)
    return [
        answer_template_from_probe(probe).model_dump(mode="json", exclude_none=True)
        for probe in probes
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a blank Paper Skill Gym answer template.")
    parser.add_argument("--probes-dir", type=Path, default=Path("evals/paper_skill_gym/probes"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    template = build_answer_template(args.probes_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(yaml.safe_dump(template, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
