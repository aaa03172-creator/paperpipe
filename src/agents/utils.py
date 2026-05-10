
import os
import logging
from pathlib import Path
try:
    from effgen.tools.builtin import Retrieval
except ImportError:
    Retrieval = None

def get_retrieval_tool(config, logger=None):
    """
    Initializes and syncs the Retrieval tool with the RAG directory.
    """
    if not logger:
        logger = logging.getLogger(__name__)

    if Retrieval is None:
        logger.error("effgen not installed.")
        return None

    rag_path = config.agents.rag_index_path
    rag_dir = Path(rag_path)
    
    if not rag_dir.exists():
        rag_dir.mkdir(parents=True, exist_ok=True)
    
    index_file = rag_dir / "effgen_index.json"
    
    # Strategy: Rebuild index on every load for MVP correctness (given local file store).
    # In production, we'd load 'index_file' and append only new files.
    tool = Retrieval() 
    
    count = 0
    for f in os.listdir(rag_dir):
        if f.endswith(".md"):
            try:
                # add_from_file signature: (file_path, file_type='auto', chunk=True)
                tool.add_from_file(str(rag_dir / f))
                count += 1
            except Exception as e:
                logger.warning(f"Failed to add {f} to index: {e}")
    
    if count > 0:
        try:
            tool.save_index(str(index_file))
            logger.info(f"RAG Index rebuilt/saved to {index_file} with {count} documents.")
        except Exception as e:
            logger.warning(f"Failed to save index: {e}")
            
    return tool
