
import asyncio
import json
import logging
import time
from pathlib import Path
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

# Import the logic from bootstrap
from scripts.bootstrap import process_paper

# Setup Logging
# Force reconfiguration to ensure FileHandler is added even if bootstrap imported logging
# Remove existing handlers from root logger to clean slate (optional but safer for batch)
root_logger = logging.getLogger()
if root_logger.handlers:
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("storage/batch_run.log", mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("batch_runner")

async def run_batch():
    # 1. Load Data
    zotero_path = Path("storage/zotero_export.json")
    if not zotero_path.exists():
        logger.error(f"❌ Zotero export not found at {zotero_path}")
        print(f"❌ Zotero export not found at {zotero_path}")
        return

    logger.info("Loading Zotero export...")
    try:
        with open(zotero_path, "r") as f:
            data = json.load(f)
            items = data.get("items", [])
    except Exception as e:
        logger.error(f"❌ Failed to load Zotero export: {e}")
        return

    # Extract eligible papers (must have citationKey)
    papers_to_process = []
    # Deduplicate while preserving order? Or just set?
    seen = set()
    
    for item in items:
        pid = item.get("citationKey")
        # Ensure it's a valid paper (has key and is likely an article/preprint)
        if pid and pid not in seen:
            papers_to_process.append(pid)
            seen.add(pid)
    
    logger.info(f"📚 Found {len(papers_to_process)} unique papers in Zotero export.")

    # 1.5 Prepare Library (Symlink PDFs)
    logger.info("🔗 Symlinking PDFs from Zotero storage...")
    linked_count = 0
    library_dir = Path("Library")
    library_dir.mkdir(exist_ok=True)
    
    for item in items:
        pid = item.get("citationKey")
        if not pid: continue
        
        # Find PDF attachment
        pdf_source = None
        for att in item.get("attachments", []):
            if att.get("path") and att["path"].lower().endswith(".pdf"):
                pdf_source = Path(att["path"])
                break
                
        if pdf_source and pdf_source.exists():
            target_link = library_dir / f"{pid}.pdf"
            try:
                if target_link.exists() or target_link.is_symlink():
                    target_link.unlink()
                target_link.symlink_to(pdf_source)
                linked_count += 1
            except Exception as e:
                logger.warning(f"Failed to symlink {pdf_source}: {e}")
        elif pdf_source:
             logger.warning(f"Source PDF not found on disk: {pdf_source}")

    logger.info(f"✅ Linked {linked_count} PDFs to {library_dir}")

    # 2. Filter Processed
    feedback_path = Path("storage/feedback.jsonl")
    processed_ids = set()
    if feedback_path.exists():
        with open(feedback_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    rec = json.loads(line)
                    if "paper_id" in rec:
                        processed_ids.add(rec["paper_id"])
                except Exception:
                    pass
    
    logger.info(f"⏭️  Found {len(processed_ids)} already processed papers in feedback database.")
    
    # Calculate Queue
    queue = [p for p in papers_to_process if p not in processed_ids]
    logger.info(f"🚀 Queued {len(queue)} papers for processing.")

    if not queue:
        logger.info("✅ All papers processed! Nothing to do.")
        return

    # 3. Process Loop
    # We use rich for a nice progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    ) as progress:
        
        task_id = progress.add_task("[cyan]Processing batch...", total=len(queue))
        
        for paper_id in queue:
            progress.update(task_id, description=f"[cyan]Processing: {paper_id}")
            logger.info(f"--- Batch: Processing {paper_id} ---")
            
            try:
                # Call the bootstrap logic
                # Note: process_paper handles its own errors gracefully (returns None on failure)
                await process_paper(paper_id)
                
                # Rate Limit to respect API limits / local resource usage
                # 2 seconds as requested
                progress.update(task_id, description=f"[yellow]Sleeping (Rate Limit)...")
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Unhandled error in batch loop for {paper_id}: {e}")
                # Don't crash the batch
            
            progress.advance(task_id)

    logger.info("🎉 Batch processing complete.")

if __name__ == "__main__":
    try:
        asyncio.run(run_batch())
    except KeyboardInterrupt:
        logger.info("🛑 Batch processing stopped by user.")
