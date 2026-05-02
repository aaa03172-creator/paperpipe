import shutil
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.processor import process_paper
from src.schemas import Paper, PaperStatus
from src.config import AppConfig, PathsConfig, LLMConfig, LLMFeatures, FeatureConfig, SearchConfig, SlotConfig, SystemConfig, ConfidenceThresholds

def test_notebooklm_upload():
    # 1. Setup Test Paths
    test_pdf_path = Path("tests/dummy_paper.pdf")
    upload_dir = Path("tests/notebooklm_upload")
    
    # Create dummy PDF
    with open(test_pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 dummy content")
        
    # Clean previous run
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    
    # 2. Mock Config
    mock_config = AppConfig(
        system=SystemConfig(),
        paths=PathsConfig(
            zotero_base_dir=Path("./zotero"),
            obsidian_vault=Path("./obsidian"),
            upload_dir=upload_dir, # Target for Verification
            export_dir=Path("./export")
        ),
        search=SearchConfig(slots={"test": SlotConfig(query="test")}),
        llm=LLMConfig(
            features=LLMFeatures(
                specialty_trial_extraction=FeatureConfig(),
                slot_classification=FeatureConfig(),
                one_liner=FeatureConfig()
            )
        )
    )
    
    # 3. Dummy Paper Data
    paper = Paper(
        id="10.1234/test",
        title="Test NotebookLM Copy",
        authors=["Test Author"],
        published="2023-01-01",
        source="test",
        summary="summary",
        link="http://example.com"
    )
    paper.local_pdf_path = test_pdf_path # Pre-set local path
    
    paper_data = {'paper': paper, 'slot': 'test', 'tags': []}
    
    # 4. Run Process Paper (Mocking Downloader and LLM)
    # We mock download_paper to just return the paper (since we set local_pdf_path already)
    with patch('src.processor.download_paper', return_value=paper) as mock_download:
        
        # We pass None as llm_provider to skip AI steps
        result = process_paper(paper_data, mock_config, llm_provider=None, is_deep_target=False)
        
    # 5. Verify
    dest_path = upload_dir / test_pdf_path.name
    
    if dest_path.exists():
        print(f"✅ PDF Copied Successfully to: {dest_path}")
    else:
        print(f"❌ Failed to copy PDF to: {dest_path}")
        exit(1)
        
    # Cleanup
    if test_pdf_path.exists():
        test_pdf_path.unlink()
    if upload_dir.exists():
        shutil.rmtree(upload_dir)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_notebooklm_upload()
