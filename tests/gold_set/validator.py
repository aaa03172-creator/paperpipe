import csv
import logging
from typing import Dict, Set, List
from pathlib import Path

# Adjust path if running from root
from src.db_utils import get_all_papers, is_paper_processed, DB_PATH
# We might need to fetch detailed tags from DB. 
# Currently 'papers' table only has doi, title, source.
# Wait, where are tags stored?
# Tags are seemingly NOT stored in the simplified `papers` table in `src/db.py`.
# They are used to create Obsidian notes, but the DB schema is minimal.
# The user request "Store in DB" implied storing *state*, but "Refining System Parameters" document says 
# "Store tags in DB" or "Store JSON".
# If tags are not in DB, I cannot validate them from DB efficiently without parsing Obsidian notes.
# 
# Let's check `src/processor.py` or `src/db.py` again.
# `src/db.py` has `save_paper_state` which saves `processed_date`.
# It does NOT save tags.
# This is a limitation. The system relies on Obsidian as the "Truth" for content.
# 
# So the VALUDATOR must either:
# 1. Parse Obsidian files (Hard, filenames might vary).
# 2. Or I should have updated DB to store JSON/Tags.
# 
# Given "MVP" and "Refining Parameters", if I didn't add JSON storage to DB, I should probably parse Obsidian notes 
# OR just output the results to a JSON file during processing for validation?
# 
# But the user asked for "Entity Linking" and "Confidence Gates".
# The "Gold Set Validator" implies we can validate.
# 
# I will implement `validator.py` to parse Obsidian nodes?
# Or better: `src/processor.py` likely returns the result. 
# The validator can be run *as part of* a test pipeline where we process papers and catch results.
# 
# User asked for "Script to validate".
# If I use `tests/gold_set/validator.py`, it likely needs to Fetch papers.
# 
# Let's assume for this MVP Validator, we will Mock the input or 
# parse the "Obsidian" files if possible. 
# 
# Update: `src/reporting.py` generates reports. 
# 
# I will implement the validator to:
# 1. Read CSV.
# 2. Scan the Obsidian Vault (path from config) for files matching the Title/DOI?
# 3. Extract hashtags from the MD file.
# 4. Compare.
# 
# This is robust for the current "Obsidian-centric" architecture.

from src.config import load_config
from src.logger import setup_logging

logger = setup_logging()

def load_gold_standard(csv_path: str) -> Dict[str, Dict]:
    gold_data = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = row['doi'].strip()
            tags = {t.strip() for t in row['gold_tags'].split(';') if t.strip()}
            gold_data[doi] = {
                'tags': tags,
                'slot': row['gold_slot'].strip()
            }
    return gold_data

def find_obsidian_file(vault_path: Path, doi: str) -> Path:
    # Basic search. DOI might be in filename or content.
    # Searching content is slow. 
    # Let's assume filename ~ Title or basic search.
    # For MVP, let's just search recursively for .md files containing the DOI.
    for p in vault_path.rglob("*.md"):
        try:
            content = p.read_text(errors='ignore')
            if doi in content:
                return p
        except:
            continue
    return None

def extract_tags_from_md(file_path: Path) -> Set[str]:
    content = file_path.read_text(errors='ignore')
    # Simple regex for hashtags
    import re
    tags = set(re.findall(r'#[\w/-]+', content))
    return tags

import argparse

def run_validation(custom_vault_path: Path = None):
    config = load_config()
    vault_path = custom_vault_path if custom_vault_path else config.paths.obsidian_vault
    
    csv_path = Path(__file__).parent / "gold_standard_template.csv"
    if not csv_path.exists():
        logger.error(f"Gold standard CSV not found at {csv_path}")
        return

    gold_data = load_gold_standard(csv_path)
    
    logger.info(f"🧪 Validating {len(gold_data)} papers against Vault: {vault_path}")
    
    total_f1 = 0
    matches = 0
    
    print(f"{'DOI':<30} | {'Prec':<6} | {'Rec':<6} | {'F1':<6} | {'Slot Match'}")
    print("-" * 75)
    
    for doi, gold in gold_data.items():
        md_file = find_obsidian_file(vault_path, doi)
        
        if not md_file:
            print(f"{doi[:30]:<30} | {'-'*6} | {'-'*6} | {'-'*6} | ❌ Not Found")
            continue
            
        system_tags = extract_tags_from_md(md_file)
        # Normalize (lowercase, remove #)
        system_tags = {t.lower().replace("#", "") for t in system_tags}
        gold_tags = {t.lower().replace("#", "") for t in gold['tags']}
        
        # Calculate Metrics
        intersect = len(system_tags.intersection(gold_tags))
        precision = intersect / len(system_tags) if system_tags else 0.0
        recall = intersect / len(gold_tags) if gold_tags else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        total_f1 += f1
        matches += 1
        
        print(f"{doi[:30]:<30} | {precision:.2f}   | {recall:.2f}   | {f1:.2f}   | ?")
        
    avg_f1 = total_f1 / len(gold_data) if gold_data else 0.0
    print("-" * 75)
    print(f"📊 Average Tagging F1 Score: {avg_f1:.2f} (Matches: {matches}/{len(gold_data)})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gold Set Validator")
    parser.add_argument("--vault", type=str, help="Path to Obsidian Vault to validate against")
    args = parser.parse_args()
    
    vault = Path(args.vault) if args.vault else None
    run_validation(vault)
