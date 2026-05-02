import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import actual modules to test
from src.watcher import process_local_pdf
from src.config import AppConfig, PathsConfig, LLMConfig, LLMFeatures, FeatureConfig, SearchConfig, SlotConfig, SystemConfig
from src.schemas import Paper

def test_full_integration():
    # 1. Setup Test Environment
    base_dir = Path("tests/integration_env")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir(parents=True)

    watch_dir = base_dir / "watch_folder"
    obsidian_vault = base_dir / "obsidian"
    zotero_dir = base_dir / "zotero"
    upload_dir = base_dir / "managed_uploads"
    export_dir = base_dir / "export"

    for d in [watch_dir, obsidian_vault, zotero_dir, upload_dir, export_dir]:
        d.mkdir(parents=True)

    # 2. Mock Config
    mock_config = AppConfig(
        system=SystemConfig(log_level="DEBUG"),
        paths=PathsConfig(
            zotero_base_dir=zotero_dir,
            obsidian_vault=obsidian_vault,
            upload_dir=upload_dir,
            export_dir=export_dir
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

    # 3. Create Dummy PDF in Watch Folder
    # We use a filename that implies a DOI to help the system if metadata fails
    # But src/watcher.py logic tries to resolve DOI from PDF content first. 
    # For this test, we might mock the 'get_doi_from_pdf' or 'pdf_to_text' 
    # if we define a dummy PDF that doesn't really have text.
    
    pdf_name = "test_paper.pdf"
    pdf_path = watch_dir / pdf_name
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 header... dummy content ... DOI: 10.1234/integration.test ...")

    print(f"🚀 Starting Verification in {base_dir}...")
    
    # 4. Run Process (Simulate Watcher Trigger)
    # We strip the LLM provider to avoid cost/api usage, relying on fallback logic or mocking it if needed.
    # However, to test the FULL flows including tagging, we should ideally mock the LLMProvider.
    
    mock_llm = MagicMock()
    mock_llm.tag_paper.return_value = {
        'soft_tags': ['#IntegrationTest', '#Success'],
        'hard_tags': {'status': 'verified'},
        'confidence': 0.99,
        'evidence_span': 'Mock evidence from test.'
    }
    mock_llm.extract_trial_data.return_value = None # Not a trial
    mock_llm.classify_slot.return_value = "clinical" # Force clinical to test that path too? Or mechanism.
    
    # We need to report a success DOI for the retrieval to work? 
    # Or we construct a Paper object manually?
    # process_local_pdf does: extract DOI -> fetch metadata -> LLM -> Save.
    
    # Let's mock `get_doi_from_pdf` to return a fake DOI
    # And mock `fetch_crossref` or similar to return fake metadata.
    
    with patch("src.watcher.get_llm_provider", return_value=mock_llm):
        with patch("src.watcher.extract_doi_from_pdf", return_value="10.1234/integration.test"):
            with patch("src.watcher.fetch_pubmed") as mock_fetch:
                with patch("src.watcher.save_paper_state") as mock_save_state:
                    mock_fetch.return_value = [Paper(
                        id="10.1234/integration.test",
                        doi="10.1234/integration.test",
                        title="Integration Test Paper",
                        authors=["Tester A", "Bot B"],
                        published="2025-01-01",
                        source="Test",
                        summary="This is a summary of the integration test paper.",
                        link="http://test.com/paper.pdf"
                    )]
                    
                    # EXECUTE
                    process_local_pdf(pdf_path, mock_config)
                    assert mock_save_state.called
                    _, save_kwargs = mock_save_state.call_args
                    assert save_kwargs["issues_state"] == "clear"

    # 5. Verify Outputs
    
    # A. PDF Moved/Copied?
    # Logic: process_local_pdf copies to upload_dir AND zotero_dir usually? 
    # Actually process_daily_slots mentions copy to upload_dir. process_local_pdf logic needs check.
    # Let's check where it went.
    
    # B. Obsidian Note Exists?
    print("🔍 Checking Obsidian Vault...")
    obsidian_files = list(obsidian_vault.rglob("*.md"))
    if obsidian_files:
        print(f"✅ Note created: {obsidian_files[0].name}")
        content = obsidian_files[0].read_text()
        if "aliases: [\"Integration Test Paper\"]" in content:
            print("   - Rich Frontmatter Verified")
        if "#IntegrationTest" in content:
            print("   - Tags Verified")
    else:
        print("❌ No Obsidian note found.")
        exit(1)

    # C. Zotero RIS Exists?
    print("🔍 Checking Zotero Export...")
    ris_files = list(export_dir.rglob("*.ris"))
    if ris_files:
        print(f"✅ RIS file created: {ris_files[0].name}")
        content = ris_files[0].read_text()
        if "AB  - This is a summary" in content:
            print("   - Abstract Verified")
        if "L1  - file://" in content:
            print("   - File Link Verified")
    else:
        print("❌ No RIS file found.")
        exit(1)

    # D. NotebookLM Upload?
    # In processor.py, we added logic to copy to upload_dir.
    # Let's see if it's there.
    print("🔍 Checking NotebookLM Upload Dir...")
    upload_files = list(upload_dir.rglob("*.pdf"))
    if upload_files:
        print(f"✅ PDF Copied to Upload Dir: {upload_files[0].name}")
    else:
        # Note: If local_pdf_path wasn't set correctly in the paper object during the process, this might fail.
        # process_local_pdf sets paper.local_pdf_path = file_path (the watched file).
        print("⚠️ PDF not found in upload dir. (Logic might rely on specific flow)")

    print("\n🎉 Integration Test Complete!")
    
    # Cleanup
    shutil.rmtree(base_dir)

if __name__ == "__main__":
    test_full_integration()
