#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY_PATH="$ROOT_DIR/config/skills_policy.yaml"
SOURCE_ROOT="$ROOT_DIR/rules/scientific-skills/scientific-skills"
DEST_ROOT="$ROOT_DIR/.codex/skills"

if [[ ! -f "$POLICY_PATH" ]]; then
  echo "skills policy not found: $POLICY_PATH" >&2
  exit 1
fi

if [[ ! -d "$SOURCE_ROOT" ]]; then
  echo "scientific skills source not found: $SOURCE_ROOT" >&2
  exit 1
fi

mkdir -p "$DEST_ROOT"
python3 - <<'PY' "$POLICY_PATH" | while IFS= read -r skill; do
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = yaml.safe_load(handle) or {}

for item in data.get("project_scoped_skills", []) or []:
    text = str(item).strip()
    if text:
        print(text)
PY
  src="$SOURCE_ROOT/$skill"
  dest="$DEST_ROOT/$skill"
  if [[ ! -d "$src" ]]; then
    echo "warning: missing skill source: $skill" >&2
    continue
  fi
  rm -rf "$dest"
  cp -R "$src" "$dest"
  echo "synced $skill"
done
