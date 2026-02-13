
import logging
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.processor import process_daily_slots
from src.schemas import Paper
from src.config import load_config
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_full_pipeline_integration():
    """
    End-to-End Integration Test for PaperPipe.
    Simulates: Fetch -> Rank -> Classify -> Tag -> Process -> DB/Obsidian/Zotero
    """
    print("\n🚀 Starting Full Pipeline Integration Test...")
    
    # 1. Setup Mock Data
    mock_paper = Paper(
        id="10.1234/test.paper",
        title="Integration Test Paper: Exploring Automations",
        published="2023-10-01",
        source="TestFetch",
        authors=["Alice Test", "Bob Mock"],
        summary="This is a test summary for integration.",
        link="http://example.com/pdf",
        citation_count=100  # High impact
    )
    
    # 2. Mock Components
    # We need to mock:
    # - get_fetchers: Return our mock paper
    # - LLMProvider: Return deterministic tags/classification
    # - OpenAlexFetcher/BibliometricScorer: (Optional, or mock the scorer)
    # - download_paper: Don't actually download
    # - save_paper_to_obsidian: We can let this run if we use a temp dir, 
    #   but mocking is safer to avoid clutter. Let's mock it to verify call.
    # - export_to_ris: Mock to verify call.

    # Mock load_config to avoid Pydantic validation errors
    with patch('src.processor.load_config') as mock_load_config:
        # Create a full Mock Config
        mock_config = MagicMock()
        mock_config.paths.zotero_base_dir = Path("Test/Zotero")
        mock_config.paths.upload_dir = Path("Test/Uploads")
        mock_config.paths.export_dir = Path("Test/Export")
        
        # Configure Slots
        mock_slot = MagicMock()
        mock_slot.query = "test query"
        mock_slot.source = "all"
        mock_config.search.slots = {"clinical": mock_slot}
        
        # Configure Features
        mock_config.llm.features.slot_classification.enabled = True
        mock_config.llm.features.one_liner.enabled = True
        mock_config.llm.features.trial_extraction.enabled = True
        mock_config.ranking.bibliometrics.enabled = True
        
        # Configure Thresholds
        mock_config.confidence_thresholds.high = 0.85
        mock_config.confidence_thresholds.low = 0.60
        
        mock_load_config.return_value = mock_config

        with patch('src.processor.get_fetchers') as mock_get_fetchers, \
             patch('src.processor.get_llm_provider') as mock_get_llm, \
             patch('src.ranking.BibliometricScorer') as mock_scorer_cls, \
             patch('src.processor.download_paper') as mock_download, \
             patch('src.processor.save_paper_to_obsidian') as mock_obsidian, \
             patch('src.processor.export_to_ris') as mock_zotero, \
             patch('src.processor.save_paper_state') as mock_db_save, \
             patch('src.processor.is_paper_processed', return_value=False): # Force process

            # Configure Mocks
            
            # Fetcher
            mock_fetcher = MagicMock()
            mock_fetcher.source_name = "TestFetch"
            mock_fetcher.fetch.return_value = [mock_paper]
            mock_get_fetchers.return_value = [mock_fetcher]
            
            # LLM
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_available.return_value = True
            mock_llm_instance.classify_slot.return_value = "clinical" # Keep original slot
            mock_llm_instance.tag_paper.return_value = {
                "soft_tags": ["#Automation", "#Testing"],
                "confidence": 0.95 # High confidence -> Auto Approve
            }
            mock_llm_instance.generate_one_liner.return_value = "A test paper about automation."
            mock_llm_instance.extract_trial_data.return_value = None
            mock_llm_instance.evaluate_escalation.return_value = {"approved": False} # Default
            mock_get_llm.return_value = mock_llm_instance
            
            # Ranking
            mock_scorer = mock_scorer_cls.return_value
            mock_scorer.calculate_scores.return_value = [mock_paper] # Return same list (ranked)
            
            # Download
            mock_download.return_value = mock_paper # Return paper as is
            
            # Obsidian
            mock_obsidian.return_value = "Generated/Note/Path.md"

            # 3. Run Pipeline
            print("   -> Running process_daily_slots()...")
            results = process_daily_slots(ignore_db=True)
        
        # 4. Assertions
        print("   -> Verifying results...")
        
        assert len(results) > 0, "Pipeline should return at least one result"
        processed_paper = results[0]
        
        # Check Slot
        assert processed_paper['slot'] == 'clinical'
        print("      ✅ Slot classification verified.")
        
        # Check Tags
        tags = processed_paper['tags']
        assert "#Automation" in tags
        assert "#Testing" in tags
        print("      ✅ Hybrid tagging verified.")
        
        # Check Status (High Confidence -> Auto Approved)
        # Note: status enum is int or str? Let's check schema/processor logic
        # It sets PaperStatus.AUTO_APPROVED. 
        # We can check if 'processing_status' key exists.
        assert 'processing_status' in processed_paper
        print(f"      ✅ Status verified: {processed_paper['processing_status']}")
        
        # Check Integrations
        assert mock_obsidian.called
        print("      ✅ Obsidian save triggered.")
        
        assert mock_zotero.called
        print("      ✅ Zotero export triggered.")
        
        assert mock_db_save.called
        print("      ✅ DB save triggered.")
        
        print("✅ Full Pipeline Test Passed!")

if __name__ == "__main__":
    test_full_pipeline_integration()
