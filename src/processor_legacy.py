from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pypdf import PdfReader

from src.config import AppConfig, load_config
from src.db_utils import is_paper_processed, save_paper_state
from src.downloader import download_paper
from src.fetch import get_fetchers
from src.llm_provider import LLMProvider, get_llm_provider
from src.obsidian import save_paper_to_obsidian
from src.schemas import Paper, PaperStatus
from src.zotero import export_to_ris


def process_paper_legacy(
    paper_data: Dict[str, Any],
    config: Optional[AppConfig] = None,
    llm_provider: Optional[LLMProvider] = None,
    is_deep_target: bool = False,
):
    """Compatibility shim used by legacy watcher/tests."""
    _ = is_deep_target
    _ = config
    _ = llm_provider
    return paper_data.get("paper")


def process_local_pdf_legacy(file_path: Path, config: Optional[AppConfig] = None):
    """Legacy entrypoint retained for backward compatibility."""
    cfg = config or load_config()
    title = file_path.stem
    try:
        reader = PdfReader(str(file_path))
        meta_title = (reader.metadata or {}).get("/Title")
        if meta_title:
            title = str(meta_title)
    except Exception:
        pass

    paper = Paper(
        id=f"local--{int(time.time())}",
        title=title,
        authors=[],
        published=datetime.now().strftime("%Y-%m-%d"),
        source="local_pdf",
        summary="",
        link=f"file://{file_path.absolute()}",
        local_pdf_path=file_path,
    )
    return process_paper_legacy({"paper": paper}, config=cfg, llm_provider=None, is_deep_target=False)


def process_daily_slots_legacy(ignore_db: bool = False) -> List[Dict[str, Any]]:
    """Legacy batch pipeline used by older tests/scripts."""
    return process_daily_slots_legacy_with_deps(
        ignore_db=ignore_db,
        load_config_fn=load_config,
        get_llm_provider_fn=get_llm_provider,
        get_fetchers_fn=get_fetchers,
        is_paper_processed_fn=is_paper_processed,
        download_paper_fn=download_paper,
        save_paper_to_obsidian_fn=save_paper_to_obsidian,
        export_to_ris_fn=export_to_ris,
        save_paper_state_fn=save_paper_state,
    )


def process_daily_slots_legacy_with_deps(
    ignore_db: bool,
    *,
    load_config_fn,
    get_llm_provider_fn,
    get_fetchers_fn,
    is_paper_processed_fn,
    download_paper_fn,
    save_paper_to_obsidian_fn,
    export_to_ris_fn,
    save_paper_state_fn,
) -> List[Dict[str, Any]]:
    config = load_config_fn()
    llm = get_llm_provider_fn(config.llm, config.entity_aliases)
    slots = getattr(config.search, "slots", {}) or {}
    fetchers = get_fetchers_fn(config)
    results: List[Dict[str, Any]] = []

    for slot_name, slot_cfg in slots.items():
        query = getattr(slot_cfg, "query", "")
        for fetcher in fetchers:
            try:
                papers = fetcher.fetch(query, max_results=5)
            except TypeError:
                papers = fetcher.fetch(query=query, max_results=5)
            for paper in papers:
                if not ignore_db and is_paper_processed_fn(paper.id):
                    continue

                paper = download_paper_fn(paper, config)
                resolved_slot = slot_name
                if llm and llm.is_available() and getattr(config.llm.features.slot_classification, "enabled", False):
                    try:
                        resolved_slot = llm.classify_slot(
                            {"title": paper.title, "summary": paper.summary},
                            slot_name,
                        ) or slot_name
                    except Exception:
                        resolved_slot = slot_name

                tags: list[str] = []
                confidence = 0.0
                if llm and llm.is_available():
                    tag_payload = llm.tag_paper({"title": paper.title, "summary": paper.summary}) or {}
                    tags = tag_payload.get("soft_tags", []) or []
                    confidence = float(tag_payload.get("confidence", 0.0) or 0.0)

                if confidence >= config.confidence_thresholds.high:
                    status = PaperStatus.APPROVED
                elif confidence < config.confidence_thresholds.low:
                    status = PaperStatus.QUARANTINED
                else:
                    status = PaperStatus.PENDING_REVIEW

                row = {
                    "id": paper.id,
                    "paper_id": paper.id,
                    "doi": paper.doi or paper.id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "published": paper.published,
                    "source": paper.source,
                    "summary": paper.summary,
                    "link": paper.link,
                    "slot": resolved_slot,
                    "tags": tags,
                    "processing_status": status,
                    "pdf_path": str(paper.local_pdf_path) if paper.local_pdf_path else None,
                    "local_pdf_path": str(paper.local_pdf_path) if paper.local_pdf_path else None,
                }

                if not row["pdf_path"]:
                    from src.institutional_access import (
                        generate_institutional_proxy_url,
                        upsert_institutional_proxy_link,
                    )

                    proxy_url = generate_institutional_proxy_url(doi=row["doi"], publisher_url=row["link"])
                    if proxy_url:
                        row["feedback_json"] = upsert_institutional_proxy_link("{}", proxy_url)

                results.append(row)

                try:
                    save_paper_to_obsidian_fn(row, config)
                except Exception:
                    pass
                try:
                    export_to_ris_fn(row, Path(config.paths.export_dir))
                except Exception:
                    pass
                try:
                    save_paper_state_fn(
                        row["doi"],
                        row["title"],
                        row["source"],
                        datetime.now().strftime("%Y-%m-%d"),
                    )
                except Exception:
                    pass

    return results
