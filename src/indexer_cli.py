from __future__ import annotations

import argparse
import json
from typing import Any, Callable


def build_arg_parser(default_model: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PaperPipe local biomedical embedding indexer")
    parser.add_argument("--db", required=True, help="SQLite DB path")
    parser.add_argument("--chroma", default="./storage/vector_db", help="Chroma persist path")
    parser.add_argument(
        "--collection",
        default=None,
        help="Collection name (default: auto from model naming rule)",
    )
    parser.add_argument(
        "--model",
        default=default_model,
        help="SentenceTransformer model name (default: NeuML/pubmedbert-base-embeddings)",
    )
    parser.add_argument(
        "--version",
        type=int,
        default=1,
        help="Collection version number (default: 1)",
    )
    parser.add_argument(
        "--bge-query-prefix",
        choices=["auto", "on", "off"],
        default="auto",
        help="Apply BGE retrieval prefix for query encoding (default: auto)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_index = subparsers.add_parser("index", help="Index papers into ChromaDB")
    p_index.add_argument("--all", action="store_true", help="Index all papers without approval filter")

    p_search = subparsers.add_parser("search", help="Search indexed papers")
    p_search.add_argument("query", help="Search query text")
    p_search.add_argument("--k", type=int, default=5, help="Top-k results")

    return parser


def run_cli(indexer_factory: Callable[..., Any], default_model: str) -> None:
    parser = build_arg_parser(default_model=default_model)
    args = parser.parse_args()

    indexer = indexer_factory(
        db_path=args.db,
        chroma_path=args.chroma,
        model_name=args.model,
        collection_name=args.collection,
        collection_version=args.version,
        bge_query_prefix=args.bge_query_prefix,
    )

    if args.command == "index":
        result = indexer.index(include_all=args.all)
        print(json.dumps({"collection": result.collection_name, "indexed_count": result.indexed_count}))
        return

    if args.command == "search":
        results = indexer.search(query=args.query, k=args.k)
        print(json.dumps(results, ensure_ascii=False, default=str))
        return

    parser.error("Unknown command")
