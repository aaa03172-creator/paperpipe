from __future__ import annotations

from pathlib import Path
from rich.console import Console

from src.config import load_config
from src.db_utils import get_paper_by_id, update_reading_status
from src.services.deepread_note_writer import (
    build_deepread_markdown,
    build_stats_markdown,
    upsert_deepread_section,
)
from src.timeout_policy import (
    default_reader_timeout_base_seconds,
    default_stats_timeout_base_seconds,
    estimate_reader_timeout_seconds,
    estimate_stats_timeout_seconds,
    is_timeout_exception,
    time_limit,
)


def update_reading_status_workflow(identifier: str, status: str, console: Console) -> None:
    from src.obsidian import set_reading_status

    config = load_config()
    console.print(f"[bold cyan]🔄 Updating status to '{status}' for: {identifier}[/bold cyan]")
    doi = set_reading_status(identifier, status, config)
    if doi:
        update_reading_status(doi, status)
        console.print(f"   ✅ DB Updated (DOI: {doi})")
        console.print("   ✅ Obsidian Note & Index Updated")
        return
    console.print("[bold red]❌ Paper not found in Index.[/bold red]")
    console.print("   (Try using exact Paper ID, DOI, or Title from 'paperpipe stats' or 'paperpipe fetch --save')")


def run_deepread_workflow(
    identifier: str,
    verify: bool,
    console: Console,
    *,
    reader_timeout_sec: int = 0,
    stats_timeout_sec: int = 0,
    adaptive_step_timeout: bool = True,
) -> None:
    import csv

    config = load_config()
    if not config.agents.enabled:
        console.print("[yellow]⚠️ Agents are disabled in config. Enable them to use this feature.[/yellow]")
        return

    console.print(f"[bold cyan]🤖 Starting Deep Read Pipeline for: {identifier}[/bold cyan]")
    try:
        paper_row = get_paper_by_id(identifier)
    except Exception:
        paper_row = None

    pdf_path = None
    if paper_row:
        db_pdf_path = paper_row.get("local_path") or paper_row.get("pdf_path")
        if db_pdf_path:
            pdf_path = Path(db_pdf_path)

    if not pdf_path or not pdf_path.exists():
        results = list(config.paths.library_dir.rglob(f"*{identifier}*.pdf"))
        if not results and "/" in identifier:
            clean_id = identifier.replace("/", "_")
            results = list(config.paths.library_dir.rglob(f"*{clean_id}*.pdf"))
        if results:
            pdf_path = results[0]

    if not pdf_path or not pdf_path.exists():
        console.print(f"[red]❌ PDF not found for {identifier}[/red]")
        return

    console.print(f"   📂 PDF: {pdf_path}")

    vault_path = config.paths.obsidian_vault
    idx_files = [config.paths.index_all, "00_Index/on_demand.csv"]
    target_note_path = None
    for rel_idx in idx_files:
        p = vault_path / rel_idx
        if not p.exists():
            continue
        try:
            with open(p, "r") as f:
                for row in csv.DictReader(f):
                    if row.get("Paper_ID") == identifier or row.get("DOI") == identifier:
                        if row.get("Note_Path"):
                            target_note_path = vault_path / row["Note_Path"]
                        break
        except Exception:
            pass
        if target_note_path:
            break

    if not target_note_path or not target_note_path.exists():
        console.print("[yellow]⚠️ Note not found. Will just print output.[/yellow]")
    else:
        console.print(f"   📝 Note: {target_note_path}")

    try:
        from src.agents.ingest_agent import IngestAgent
        from src.agents.indexer_agent import IndexerAgent
        from src.agents.reader_agent import ReaderAgent
        if verify:
            from src.agents.stats_agent import StatsVerificationAgent

        console.print("[bold]1️⃣  Ingesting PDF...[/bold]")
        ingest_conf = getattr(config, "ingest", None)
        parser_backend = str(getattr(ingest_conf, "parser_backend", "fitz_pdfplumber") or "fitz_pdfplumber").strip().lower()
        enable_docling = bool(getattr(ingest_conf, "enable_docling", False))
        if parser_backend == "docling" and not enable_docling:
            parser_backend = "fitz_pdfplumber"
        ingester = IngestAgent(
            parser_backend=parser_backend,
            enable_ocr_fallback=bool(getattr(ingest_conf, "enable_ocr_fallback", False)),
            ocr_lang=str(getattr(ingest_conf, "ocr_lang", "eng") or "eng"),
            ocr_min_text_chars=int(getattr(ingest_conf, "ocr_min_text_chars", 200)),
            enable_table_pass2_ocr=bool(getattr(ingest_conf, "enable_table_pass2_ocr", False)),
            enable_cloud_table_fallback=bool(getattr(ingest_conf, "enable_cloud_table_fallback", False)),
            cloud_table_page_budget=int(getattr(ingest_conf, "cloud_table_page_budget", 2)),
            cloud_table_model=str(getattr(ingest_conf, "cloud_table_model", "gpt-4o-mini") or "gpt-4o-mini"),
            cloud_table_base_url=getattr(ingest_conf, "cloud_table_base_url", None),
            cloud_table_api_key=getattr(ingest_conf, "cloud_table_api_key", None),
            cloud_table_timeout_seconds=int(getattr(ingest_conf, "cloud_table_timeout_seconds", 30)),
        )
        doc = ingester.process_v2(str(pdf_path))
        if not doc:
            console.print("[red]❌ Ingest Agent failed to produce v2 artifact.[/red]")
            return
        console.print(f"   ✅ Extracted {len(doc.pages)} pages (v2 artifact).")

        console.print("[bold]2️⃣  Indexing (RAG)...[/bold]")
        indexer = IndexerAgent(collection_name="paperpipe_rag")
        index_artifact = indexer.process(doc)
        console.print(f"   ✅ Indexed {index_artifact.chunk_count} chunks.")

        from src.agents.feedback_retriever import FeedbackRetriever

        retriever = FeedbackRetriever()
        similar_feedback = retriever.query_relevant_feedback(doc.meta.title, limit=3)
        persona_hint = None
        if similar_feedback:
            fb_lines = ["Similar feedback examples (Top-3):"]
            for idx, item in enumerate(similar_feedback, 1):
                fb_lines.append(f"{idx}) paper_id={item['paper_id']} preview={item['preview']}")
            persona_hint = "\n".join(fb_lines)
            console.print(f"   [yellow]⚠️ Similar feedback injected: {len(similar_feedback)}[/yellow]")

        console.print("[bold]3️⃣  Deep Reading (Agentic Analysis)...[/bold]")
        reader = ReaderAgent(model_name=config.agents.main_model, persona_hint=persona_hint)
        page_count = len(getattr(doc, "pages", []) or [])
        table_count = len(getattr(doc, "tables", []) or [])
        llm_timeout_default = max(15, int(getattr(config.llm, "timeout_seconds", 15) or 15))
        reader_timeout_base = (
            int(reader_timeout_sec)
            if int(reader_timeout_sec) > 0
            else default_reader_timeout_base_seconds(llm_timeout_default)
        )
        reader_timeout_budget = estimate_reader_timeout_seconds(
            reader_timeout_base,
            page_count=page_count,
            table_count=table_count,
            adaptive=bool(adaptive_step_timeout),
        )
        console.print(f"   ⏱️ Reader timeout budget: {reader_timeout_budget}s (adaptive={bool(adaptive_step_timeout)})")
        try:
            with time_limit(int(reader_timeout_budget)):
                claims_set = reader.analyze(doc)
        except Exception as exc:
            if not is_timeout_exception(exc):
                raise
            console.print(
                f"[red]❌ Reader timeout after {reader_timeout_budget}s. "
                "Retry with --reader-timeout-sec <sec>.[/red]"
            )
            return

        if not claims_set:
            console.print("[red]❌ Reader Agent failed to extract claims.[/red]")
            return

        console.print(f"   ✅ Extracted {len(claims_set.claims)} claims.")

        stats_md = ""
        if verify:
            console.print("\n[bold magenta]4️⃣  Starting Stats Verification Agent (Reflexion Loop)...[/bold magenta]")
            verifier = StatsVerificationAgent()
            stats_timeout_base = (
                int(stats_timeout_sec)
                if int(stats_timeout_sec) > 0
                else default_stats_timeout_base_seconds(llm_timeout_default)
            )
            stats_timeout_budget = estimate_stats_timeout_seconds(
                stats_timeout_base,
                page_count=page_count,
                table_count=table_count,
                claim_count=len(claims_set.claims),
                adaptive=bool(adaptive_step_timeout),
            )
            console.print(f"   ⏱️ Stats timeout budget: {stats_timeout_budget}s (adaptive={bool(adaptive_step_timeout)})")
            try:
                with console.status("[bold magenta]   🕵️‍♀️ Verifying Claims (Docker Sandbox Active)...[/bold magenta]", spinner="dots"):
                    with time_limit(int(stats_timeout_budget)):
                        stats_report = verifier.run(job_id=identifier.replace("/", "_"), doc=doc, claims=claims_set)
                console.print(f"   ✅ Verification Complete. Checks run: {len(stats_report.checks)}")
                stats_md = build_stats_markdown(stats_report)
            except Exception as exc:
                if not is_timeout_exception(exc):
                    raise
                console.print(
                    f"[yellow]⚠️ Stats verification timed out after {stats_timeout_budget}s. "
                    "Continuing without stats section.[/yellow]"
                )

        md_output = build_deepread_markdown(
            model_name=reader.model_name,
            claims_set=claims_set,
            stats_md=stats_md if verify else "",
        )
        if target_note_path:
            content = target_note_path.read_text(encoding="utf-8")
            updated = upsert_deepread_section(content, md_output)
            target_note_path.write_text(updated, encoding="utf-8")
            console.print("[bold green]✨ Deep Read section upserted in note.[/bold green]")
        else:
            console.print(md_output)
    except Exception as exc:
        console.print(f"[bold red]❌ Pipeline Error: {exc}[/bold red]")
        import traceback

        traceback.print_exc()
