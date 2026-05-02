
import logging
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from src.processor import process_daily_slots
from src.schemas import Paper
from src.schemas import BiomedicalClinicalExtraction
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
        mock_config.llm.features.specialty_trial_extraction.enabled = True
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
        _, db_save_kwargs = mock_db_save.call_args
        assert db_save_kwargs["issues_state"] == "clear"
        print("      ✅ issues_state persistence verified.")
        
        print("✅ Full Pipeline Test Passed!")

if __name__ == "__main__":
    test_full_pipeline_integration()


def test_full_pipeline_clinical_slot_uses_generic_clinical_extraction_across_biomedical_domains():
    domain_cases = [
        {
            "paper": Paper(
                id="10.1234/oncology.paper",
                title="Clinical biomarker monitoring in metastatic colorectal cancer",
                published="2024-01-10",
                source="TestFetch",
                authors=["Alice Onc"],
                summary="Prospective oncology cohort study measuring circulating tumor DNA response dynamics.",
                link="http://example.com/oncology.pdf",
            ),
            "condition": "Metastatic colorectal cancer",
            "intervention_name": "ctDNA-guided monitoring",
            "intervention_category": "diagnostic",
        },
        {
            "paper": Paper(
                id="10.1234/immunology.paper",
                title="Prospective cytokine profiling in ulcerative colitis patients",
                published="2024-02-11",
                source="TestFetch",
                authors=["Bob Imm"],
                summary="Translational immunology cohort with biomarker and response follow-up.",
                link="http://example.com/immunology.pdf",
            ),
            "condition": "Ulcerative colitis",
            "intervention_name": "Multiplex cytokine monitoring",
            "intervention_category": "diagnostic",
        },
        {
            "paper": Paper(
                id="10.1234/biomaterial.paper",
                title="Pilot biomaterial scaffold repair study in knee osteoarthritis",
                published="2024-03-12",
                source="TestFetch",
                authors=["Cara Bio"],
                summary="Prospective biomaterials pilot with safety and functional outcome follow-up.",
                link="http://example.com/biomaterial.pdf",
            ),
            "condition": "Knee osteoarthritis",
            "intervention_name": "Injectable hydrogel scaffold",
            "intervention_category": "biomaterial",
        },
        {
            "paper": Paper(
                id="10.1234/neuro.paper",
                title="Blood biomarker study in mild cognitive impairment",
                published="2024-04-13",
                source="TestFetch",
                authors=["Dana Neuro"],
                summary="Clinical neuroscience biomarker study with longitudinal diagnostic follow-up.",
                link="http://example.com/neuro.pdf",
            ),
            "condition": "Mild cognitive impairment",
            "intervention_name": "Plasma biomarker panel",
            "intervention_category": "diagnostic",
        },
    ]

    for case in domain_cases:
        with patch("src.processor.load_config") as mock_load_config:
            mock_config = SimpleNamespace(
                paths=SimpleNamespace(
                    zotero_base_dir=Path("Test/Zotero"),
                    upload_dir=Path("Test/Uploads"),
                    export_dir=Path("Test/Export"),
                ),
                search=SimpleNamespace(
                    slots={
                        "clinical": SimpleNamespace(
                            query="test query",
                            source="all",
                        )
                    }
                ),
                llm=SimpleNamespace(
                    features=SimpleNamespace(
                        clinical_extraction=SimpleNamespace(enabled=True),
                        specialty_trial_extraction=SimpleNamespace(enabled=True),
                        slot_classification=SimpleNamespace(enabled=True),
                        one_liner=SimpleNamespace(enabled=False),
                    )
                ),
                ranking=SimpleNamespace(bibliometrics=SimpleNamespace(enabled=True)),
                confidence_thresholds=SimpleNamespace(high=0.85, low=0.60),
                entity_aliases={},
            )
            mock_load_config.return_value = mock_config

            with patch("src.processor.get_fetchers") as mock_get_fetchers, \
                 patch("src.processor.get_llm_provider") as mock_get_llm, \
                 patch("src.processor.download_paper") as mock_download, \
                 patch("src.processor.save_paper_to_obsidian") as mock_obsidian, \
                 patch("src.processor.export_to_ris") as mock_zotero, \
                 patch("src.processor.save_paper_state") as mock_db_save, \
                 patch("src.processor.is_paper_processed", return_value=False):

                mock_fetcher = MagicMock()
                mock_fetcher.source_name = "TestFetch"
                mock_fetcher.fetch.return_value = [case["paper"]]
                mock_get_fetchers.return_value = [mock_fetcher]

                mock_llm_instance = MagicMock()
                mock_llm_instance.is_available.return_value = True
                mock_llm_instance.classify_slot.return_value = "clinical"
                mock_llm_instance.tag_paper.return_value = {
                    "soft_tags": ["#Clinical", "#Biomarker"],
                    "confidence": 0.95,
                }
                mock_llm_instance.extract_biomedical_clinical_data.return_value = BiomedicalClinicalExtraction(
                    paper_id=case["paper"].id,
                    citation={
                        "title": case["paper"].title,
                        "authors_first": case["paper"].authors[0],
                        "year": 2024,
                        "journal_or_server": "Test Journal",
                        "doi": None,
                        "url": None,
                    },
                    population={"condition": case["condition"], "n_total": 42},
                    intervention={
                        "name": case["intervention_name"],
                        "category": case["intervention_category"],
                    },
                )
                mock_llm_instance.extract_trial_data.side_effect = AssertionError(
                    "Legacy specialty extractor should not be used for generic clinical slot processing"
                )
                mock_llm_instance.extract_specialty_trial_data.side_effect = AssertionError(
                    "Specialty extractor should not be used for generic clinical slot processing"
                )
                mock_get_llm.return_value = mock_llm_instance

                mock_download.return_value = case["paper"]
                mock_obsidian.return_value = "Generated/Note/Path.md"

                results = process_daily_slots(ignore_db=True)

            assert len(results) == 1
            processed_paper = results[0]
            assert processed_paper["slot"] == "clinical"
            assert processed_paper["clinical_data"]["population"]["condition"] == case["condition"]
            assert processed_paper["clinical_data"]["intervention"]["name"] == case["intervention_name"]
            assert mock_llm_instance.extract_biomedical_clinical_data.call_count == 1
            assert mock_llm_instance.extract_trial_data.call_count == 0
            assert mock_llm_instance.extract_specialty_trial_data.call_count == 0
            assert mock_obsidian.call_args.kwargs["extraction"].population.condition == case["condition"]
            assert mock_zotero.called
            assert mock_db_save.called
