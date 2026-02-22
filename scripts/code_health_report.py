#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from pathlib import Path


def _py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except Exception:
        return 0


def _collect_function_names(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
    return names


def build_report(repo_root: Path, max_lines: int, top_n: int) -> dict:
    src_root = repo_root / "src"
    tests_root = repo_root / "tests"

    src_files = _py_files(src_root)
    test_files = _py_files(tests_root)

    src_line_map = {str(p.relative_to(repo_root)): _line_count(p) for p in src_files}
    test_line_map = {str(p.relative_to(repo_root)): _line_count(p) for p in test_files}

    src_total = sum(src_line_map.values())
    tests_total = sum(test_line_map.values())
    ratio = round((tests_total / src_total), 3) if src_total else 0.0

    top_files = sorted(src_line_map.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    oversize = [item for item in top_files if item[1] > max_lines]

    fn_counter: Counter[str] = Counter()
    fn_sources: dict[str, list[str]] = defaultdict(list)
    for path in src_files:
        rel = str(path.relative_to(repo_root))
        for fn_name in _collect_function_names(path):
            fn_counter[fn_name] += 1
            fn_sources[fn_name].append(rel)

    duplicate_functions = []
    for name, count in fn_counter.most_common():
        if count < 2:
            continue
        duplicate_functions.append(
            {
                "name": name,
                "count": count,
                "files": sorted(set(fn_sources[name]))[:5],
            }
        )

    return {
        "src_total_lines": src_total,
        "tests_total_lines": tests_total,
        "test_to_src_ratio": ratio,
        "top_src_files": top_files,
        "oversize_files": oversize,
        "duplicate_function_names_top10": duplicate_functions[:10],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="PaperPipe code health snapshot")
    parser.add_argument("--repo", default=".", help="Repository root path")
    parser.add_argument("--max-lines", type=int, default=500, help="Max lines threshold per source file")
    parser.add_argument("--top-n", type=int, default=10, help="How many top files to show")
    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    report = build_report(repo_root=repo_root, max_lines=args.max_lines, top_n=args.top_n)

    print("[Code Health]")
    print(f"src_total_lines={report['src_total_lines']}")
    print(f"tests_total_lines={report['tests_total_lines']}")
    print(f"test_to_src_ratio={report['test_to_src_ratio']}")
    print("")

    print(f"[Top {args.top_n} src files]")
    for path, lines in report["top_src_files"]:
        flag = "  !OVER" if lines > args.max_lines else ""
        print(f"- {path}: {lines}{flag}")
    print("")

    print("[Duplicate function names (top 10)]")
    for item in report["duplicate_function_names_top10"]:
        files = ", ".join(item["files"])
        print(f"- {item['name']} ({item['count']}): {files}")


if __name__ == "__main__":
    main()
