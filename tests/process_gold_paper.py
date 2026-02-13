import shutil
import logging
from pathlib import Path
from src.processor import process_paper
from src.config import AppConfig, PathsConfig, LLMConfig, LLMFeatures, FeatureConfig, SearchConfig, SlotConfig, SystemConfig
from src.schemas import Paper
from src.llm_provider import get_llm_provider

def process_gold_paper():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("PILOT")
    
    # 1. Setup Temp Vault
    vault_dir = Path("tests/gold_vault")
    if vault_dir.exists():
        shutil.rmtree(vault_dir)
    vault_dir.mkdir(parents=True)
    
    # 2. Config (Point to Temp Vault)
    config = AppConfig(
        system=SystemConfig(),
        paths=PathsConfig(
            zotero_base_dir=Path("tests/zotero"),
            obsidian_vault=vault_dir,
            upload_dir=Path("tests/upload"),
            export_dir=Path("tests/export")
        ),
        search=SearchConfig(slots={"clinical": SlotConfig(query="test")}),
        llm=LLMConfig(
            features=LLMFeatures(
                trial_extraction=FeatureConfig(enabled=True),
                slot_classification=FeatureConfig(),
                one_liner=FeatureConfig(enabled=True)
            )
        )
    )
    
    # 3. Define Paper (10.3390/nu17193125)
    # Real data to match Gold Set
    paper = Paper(
        id="10.3390/nu17193125",
        doi="10.3390/nu17193125",
        title="Clinical Benefits of Exogenous Ketosis in Adults with Disease: A Systematic Review.",
        authors=["Author A", "Author B"],
        published="2025-01-01",
        source="PubMed",
        summary="Background: Exogenous ketones are being explored for various diseases. Methods: Systematic review... Results: Improved cognition in some MCI cases... Conclusions: Promising.",
        link="https://doi.org/10.3390/nu17193125",
        pdf_link="http://example.com/file.pdf"
    )
    
    # 4. LLM Provider (Real or Mock?)
    # User asked to "Actually process". If we have API Key, we use Real. 
    # If not, we Mock.
    # Checking Env...
    import os
    if os.getenv("OPENAI_API_KEY"):
        logger.info("🔑 Using REAL LLM Provider")
        llm_provider = get_llm_provider(config.llm, config.entity_aliases)
    else:
        logger.warning("⚠️ No API Key found. Using MOCK Provider.")
        from unittest.mock import MagicMock
        llm_provider = MagicMock()
        llm_provider.tag_paper.return_value = {
            'soft_tags': ['#Ketosis', '#SystematicReview', '#Adults', '#Clinical', '#Review_Needed'],
            'hard_tags': {'study_type': 'Systematic Review'},
            'confidence': 0.85,
            'evidence_span': 'Systematic review of exogenous ketones'
        }
        llm_provider.extract_trial_data.return_value = None
        llm_provider.generate_one_liner.return_value = "Systematic review shows potential benefits of exogenous ketones."

    # 5. Process
    paper_data = {'paper': paper, 'slot': 'clinical', 'tags': []}
    
    logger.info(f"🚀 Processing Paper: {paper.title}")
    process_paper(paper_data, config, llm_provider, is_deep_target=True)
    
    logger.info(f"✅ Processing Complete. Vault: {vault_dir}")

if __name__ == "__main__":
    process_gold_paper()
