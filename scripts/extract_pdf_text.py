import sys
from pathlib import Path
import pypdf

def extract_text(pdf_path, pages=3):
    try:
        reader = pypdf.PdfReader(pdf_path)
        text = ""
        for i in range(min(pages, len(reader.pages))):
            text += reader.pages[i].extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_pdf_text.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    print(extract_text(pdf_path))
