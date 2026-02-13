import shutil
import logging
import csv
from pathlib import Path
from src.zotero import export_to_ris
from src.obsidian import save_paper_to_obsidian, update_csv_index
from src.schemas import Paper, PaperStatus
from src.config import AppConfig, PathsConfig, LLMConfig, LLMFeatures, FeatureConfig, SearchConfig, SlotConfig, SystemConfig

def test_outputs():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("VERIFY")
    
    # 1. Setup Test Env
    test_dir = Path("tests/output_test")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)
    
    zotero_dir = test_dir / "zotero"
    obsidian_dir = test_dir / "obsidian"
    upload_dir = test_dir / "notebooklm"
    
    # Mock Config
    mock_config = AppConfig(
        system=SystemConfig(),
        paths=PathsConfig(
            zotero_base_dir=zotero_dir,
            obsidian_vault=obsidian_dir,
            upload_dir=upload_dir,
            export_dir=zotero_dir
        ),
        search=SearchConfig(slots={"test": SlotConfig(query="test")}),
        llm=LLMConfig(
            features=LLMFeatures(
                trial_extraction=FeatureConfig(),
                slot_classification=FeatureConfig(),
                one_liner=FeatureConfig()
            )
        )
    )
    
    # 2. Prepare Dummy Data (Paper 1)
    paper1_data = {
        'id': '10.1001/paper1',
        'doi': '10.1001/paper1',
        'title': 'First Paper on Ketones',
        'authors': ['Doe J'],
        'published': '2025-01-01',
        'source': 'PubMed',
        'summary': 'This is the abstract of paper 1.',
        'link': 'http://paper1.com',
        'slot': 'mechanism',
        'tags': ['#Ketones', '#MCI'], # Flat tags
        'hybrid_tags': {
            'soft_tags': ['#Ketones', '#MCI'],
            'hard_tags': {'dose': '20g'},
            'confidence': 0.95,
            'evidence_span': 'Evidence 1'
        },
        'processing_status': PaperStatus.AUTO_APPROVED,
        'local_pdf_path': str(test_dir / "paper1.pdf")
    }
    
    # Create dummy PDF
    with open(test_dir / "paper1.pdf", "wb") as f:
        f.write(b"PDF Content")

    # 3. Test Zotero Export
    logger.info("Testing Zotero Export...")
    ris_path = export_to_ris(paper1_data, zotero_dir)
    
    with open(ris_path, "r") as f:
        ris_content = f.read()
        
    # Check assertions
    assert "AB  - This is the abstract of paper 1." in ris_content, "Abstract missing in RIS"
    assert "KW  - Ketones" in ris_content, "Soft tag missing in RIS"
    assert "KW  - dose:20g" in ris_content, "Hard tag missing in RIS"
    assert f"L1  - file://{Path(test_dir / 'paper1.pdf').absolute()}" in ris_content, "File link missing or incorrect"
    print("✅ Zotero RIS Export Verified")

    # 4. Test Obsidian Smart Linking (Paper 1 then Paper 2)
    logger.info("Testing Obsidian Smart Linking...")
    
    # Save Paper 1 -> Should create index entry
    save_paper_to_obsidian(paper1_data, mock_config)
    
    # Paper 2: Shares tags with Paper 1
    paper2_data = {
        'id': '10.1001/paper2',
        'doi': '10.1001/paper2',
        'title': 'Second Paper on Ketones',
        'authors': ['Smith A'],
        'published': '2025-02-01',
        'source': 'PubMed',
        'summary': 'Abstract 2',
        'link': 'http://paper2.com',
        'slot': 'mechanism',
        'tags': ['#Ketones', '#Alzheimers'], # Shares #Ketones and same slot
        'hybrid_tags': {'soft_tags': ['#Ketones', '#Alzheimers']},
        'processing_status': PaperStatus.AUTO_APPROVED
    }
    
    # Save Paper 2 -> Should find Paper 1 as related
    note_path_2 = save_paper_to_obsidian(paper2_data, mock_config)
    
    with open(note_path_2, "r") as f:
        note_content = f.read()
        
    # Check Frontmatter
    assert 'aliases: ["Second Paper on Ketones"]' in note_content, "Aliases missing in Frontmatter"
    assert 'cssclasses: ["paper-note"]' in note_content, "CSS Classes missing"
    assert 'tags: ["#Ketones", "#Alzheimers"]' in note_content.replace("'", '"'), "Tags list format incorrect"

    # Check Smart Linking
    # Paper 1 has #Ketones. Paper 2 has #Ketones.
    # Logic: Overlap >= 2 OR (Same Slot + Overlap >= 1).
    # Both are slot='mechanism'. Overlap is {'#Ketones'}. So it should match.
    
    if "First Paper on Ketones" in note_content:
        print("✅ Smart Linking Verified: Found link to Paper 1")
    else:
        print("❌ Smart Linking Failed: Did not find link to Paper 1")
        print("Note Content:\n", note_content)
        exit(1)

    # Cleanup
    shutil.rmtree(test_dir)
    print("✅ All Tests Passed")

if __name__ == "__main__":
    test_outputs()
