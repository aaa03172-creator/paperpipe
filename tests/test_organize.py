
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import shutil
import tempfile
from src.cli import organize
from src.schemas import Paper
from datetime import datetime

class TestOrganize(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.source_dir = Path(self.test_dir) / "source"
        self.source_dir.mkdir()
        
        # Create dummy PDF files
        self.pdf1 = self.source_dir / "paper1.pdf"
        self.pdf1.touch()
        
        self.pdf2 = self.source_dir / "paper2.pdf"
        self.pdf2.touch()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('src.config.load_config')
    @patch('src.utils.create_paper_from_pdf')
    def test_organize_command(self, mock_create, mock_load_config):
        print("\n--- Test: Organize Command ---")
        
        # Mock Config
        mock_config = MagicMock()
        mock_config.paths.library_dir = Path(self.test_dir) / "Library"
        mock_load_config.return_value = mock_config
        
        # Mock create_paper_from_pdf
        # Paper 1: Known Metadata
        paper1 = Paper(
            id="p1", title="Deep Learning for Medical Imaging",
            source="Test", published="2023-01-01",
            authors=["John Smith", "Alice Check"],
            summary="", link="", local_pdf_path=self.pdf1
        )
        # Paper 2: Unknown Metadata (Fallback)
        paper2 = Paper(
            id="p2", title="Unknown Paper",
            source="Test", published=datetime.now().strftime("%Y-%m-%d"),
            authors=[],
            summary="", link="", local_pdf_path=self.pdf2
        )
        
        mock_create.side_effect = [paper1, paper2]
        
        # Run Command
        # We need to invoke the function directly or via Click runner
        # Since it is a Typer/Click command, calling it as function works if logic is simple
        # But here it is decorated. We'll import the function logic if separated or invoke via module.
        # Actually src.cli.organize is decorated, calling it might trigger Click context.
        # Let's import the logic function if possible, or use Typer runner.
        # For simplicity, I'll mock the internal components and call the function 
        # but pure function call on Typer command works if no context required.
        
        try:
             organize(str(self.source_dir))
        except SystemExit:
             pass # Typer might exit
             
        # Verify Results
        lib_dir = mock_config.paths.library_dir
        
        # Check Paper 1: 2023_Smith_Deep_Learning_for_Medical_Imaging.pdf
        # Note: clean_filename replaces spaces with underscores
        expected_name1 = "2023_Check_Deep_Learning_for_Medical_Imaging.pdf" 
        # Wait, generate_filename uses LAST author only? 
        # utils.py: parts[-1] of first author "John Smith" -> "Smith"
        # Let's check logic: first_author = authors[0] -> "John Smith". parts -> ["John", "Smith"]. author -> "Smith".
        expected_name1 = "2023_Smith_Deep_Learning_for_Medical_Imaging.pdf"
        
        # Check Paper 2: Unknown_Unknown_Unknown_Paper.pdf?
        # Year: "2024" (current year fallback in create_paper, but generate uses paper.published)
        # In utils.py: year = today[:4] if paper.published is empty/invalid.
        # Authors: "Unknown".
        # Title: "Unknown_Paper".
        # Name: {Year}_Unknown_Unknown_Paper.pdf
        current_year = datetime.now().strftime("%Y")
        expected_name2 = f"{current_year}_Unknown_Unknown_Paper.pdf"
        
        path1 = lib_dir / "2023" / expected_name1
        # Check if exists (mocking file move might be needed if standard library used, but we didn't mock shutil.move in the test function scope, so it should act on real files in temp dir)
        # But create_paper_from_pdf was mocked, so it returned paper objects.
        # organize calls shutil.move(pdf, final_path).
        
        print(f"Checking {path1}...")
        
        # We need to be careful: create_paper_from_pdf returns paper with local_pdf_path=self.pdf1
        # So shutil.move(self.pdf1, final_path) should happen.
        
        # We might need to handle 'Smith' vs 'Check' (Last name logic).
        # And capitalization/underscore logic in utils.py.
        
        # Let's just list files in Library/2023
        files_2023 = list((lib_dir / "2023").glob("*.pdf"))
        print(f"Files in 2023: {[f.name for f in files_2023]}")
        
        assert len(files_2023) == 1
        assert "Smith" in files_2023[0].name
        assert "Deep_Learning" in files_2023[0].name

        # Verify fallback for paper 2
        files_unknown = list((lib_dir / current_year).glob("*.pdf"))
        # Note: both might be in same year if logic defaults to current year
        
        if "2023" == current_year:
             # Both in same folder
             assert len(files_unknown) == 2
        else:
             print(f"Files in {current_year}: {[f.name for f in files_unknown]}")
             assert len(files_unknown) == 1
             assert "Unknown" in files_unknown[0].name
             
        print("✅ Organize Test Passed!")

if __name__ == "__main__":
    unittest.main()
