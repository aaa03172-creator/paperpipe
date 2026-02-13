
import logging
import sys
from pathlib import Path
from src.agents.ingest_agent import IngestAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ingest(pdf_path):
    if not Path(pdf_path).exists():
        logger.error(f"Test PDF not found: {pdf_path}")
        return

    agent = IngestAgent()
    artifact = agent.process(pdf_path)
    
    if artifact:
        print("\n✅ Ingest Successful!")
        print(f"Doc ID: {artifact.doc_id}")
        print(f"Title: {artifact.metadata.title}")
        print(f"Sections: {len(artifact.sections)}")
        print(f"Tables: {len(artifact.tables)}")
        
        # Verify JSON serialization
        json_output = artifact.model_dump_json(indent=2)
        print("\nSerialized JSON Preview (First 500 chars):")
        print(json_output[:500])
    else:
        print("\n❌ Ingest Failed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/test_ingest.py <path_to_pdf>")
    else:
        test_ingest(sys.argv[1])
