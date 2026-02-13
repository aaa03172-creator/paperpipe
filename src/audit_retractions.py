import time
import logging
from src.config import load_config
from src.db import get_all_papers, mark_as_retracted, init_db
from src.retraction import check_retraction
from src.logger import setup_logging

# Initialize logger
logger = setup_logging()

def audit_retractions():
    """
    Weekly Audit Script to check for retracted papers in the database.
    Strategy:
    1. Fetch all papers from DB.
    2. Check Crossref/Retraction Watch for each.
    3. Update DB if retracted.
    4. Log results.
    """
    init_db() # Ensure DB schema is up-to-date
    config = load_config()
    papers = get_all_papers()
    
    logger.info(f"🛡️ Starting Retraction Audit for {len(papers)} papers...")
    
    retracted_count = 0
    checked_count = 0
    error_count = 0
    
    for paper in papers:
        doi = paper['doi']
        title = paper['title']
        
        # Skip if already marked as retracted (Optional: remove this if you want to re-verify)
        if paper.get('is_retracted'):
            logger.info(f"   ⏭️  Skipping known retracted paper: {doi}")
            continue
            
        checked_count += 1
        
        try:
            # Use unpaywall email for polite pool
            email = config.system.unpaywall_email
            result = check_retraction(doi, email)
            
            if result['is_retracted']:
                logger.warning(f"   ☠️  RETRACTION DETECTED: {title} ({doi})")
                logger.warning(f"       Details: {result['retraction_details']}")
                
                mark_as_retracted(doi)
                retracted_count += 1
            else:
                # Debug logging only to avoid noise
                logger.debug(f"   ✅ Clean: {doi}")
                
            # Be polite to the API
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"   ⚠️ Error checking {doi}: {e}")
            error_count += 1
            
    logger.info("="*40)
    logger.info("📊 Retraction Audit Summary")
    logger.info(f"   - Total Checked: {checked_count}")
    logger.info(f"   - Retractions Found: {retracted_count}")
    logger.info(f"   - Errors: {error_count}")
    logger.info("="*40)

if __name__ == "__main__":
    # Ensure logging level includes INFO
    logging.basicConfig(level=logging.INFO)
    audit_retractions()
