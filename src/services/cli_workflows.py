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


def run_deepread_workflow(identifier: str, verify: bool, console: Console) -> None:
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
        ingester = IngestAgent()
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
        claims_set = reader.analyze(doc)
        if not claims_set:
            console.print("[red]❌ Reader Agent failed to extract claims.[/red]")
            return

        console.print(f"   ✅ Extracted {len(claims_set.claims)} claims.")

        stats_md = ""
        if verify:
            console.print("\n[bold magenta]4️⃣  Starting Stats Verification Agent (Reflexion Loop)...[/bold magenta]")
            verifier = StatsVerificationAgent()
            with console.status("[bold magenta]   🕵️‍♀️ Verifying Claims (Docker Sandbox Active)...[/bold magenta]", spinner="dots"):
                stats_report = verifier.run(job_id=identifier.replace("/", "_"), doc=doc, claims=claims_set)
            console.print(f"   ✅ Verification Complete. Checks run: {len(stats_report.checks)}")
            stats_md = build_stats_markdown(stats_report)

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
