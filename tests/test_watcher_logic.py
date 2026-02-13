
import logging
from pathlib import Path
from src.processor import process_local_pdf
from src.schemas import Paper
from unittest.mock import patch, MagicMock

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_process_local_pdf_logic():
    print("\n--- Test: process_local_pdf Logic ---")
    
    # Create a dummy PDF file
    dummy_pdf = Path("test_paper.pdf")
    with open(dummy_pdf, "wb") as f:
        f.write(b"%PDF-1.4 header dummy content")
    
    try:
        # Mock load_config to avoid Pydantic validation errors from real config
        with patch('src.processor.load_config') as mock_load_config:
            # Create a minimal Mock Config
            mock_config = MagicMock()
            mock_config.paths.watch_folder = Path("Download/PaperPipe_Watch")
            mock_config.llm.features.one_liner.enabled = False 
            # ... add other necessary fields if accessed
            mock_load_config.return_value = mock_config

            # Mock process_paper to avoid full pipeline execution
            with patch('src.processor.process_paper') as mock_process:
                # Mock pypdf.PdfReader
                with patch('pypdf.PdfReader') as MockReader:
                    instance = MockReader.return_value
                    instance.metadata = {'/Title': 'Test Local Paper Title'}
                    
                    # Mock shutil.move
                    with patch('shutil.move') as mock_move:
                         process_local_pdf(dummy_pdf)
                         
                         # Verify process_paper token called
                         assert mock_process.called
                         args, _ = mock_process.call_args
                         paper_data = args[0]
                         
                         print(f"✅ Extracted Title: {paper_data['paper'].title}")
                         print(f"✅ Paper Source: {paper_data['paper'].source}")
                         print("✅ Pipeline triggered successfully.")


    except Exception as e:
        print(f"❌ Test Failed: {e}")
    finally:
        if dummy_pdf.exists():
            dummy_pdf.unlink()

if __name__ == "__main__":
    test_process_local_pdf_logic()
