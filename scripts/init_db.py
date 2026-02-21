import sqlite3
import logging
from pathlib import Path

# Config
DB_PATH = Path("storage/state.db")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")

def init_db():
    """
    Initialize the SQLite database for PaperPipe v2.1.1 (Phase 1).
    Implements the Schema from Spec 10.1 and State Machine from Spec 6.
    """
    # Ensure storage directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    logger.info(f"🔌 Connected to database at {DB_PATH}")

    # ---------------------------------------------------------
    # Table: papers
    # Core metadata and State Machine tracking
    # ---------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS papers (
        -- Identity
        paper_id TEXT PRIMARY KEY,          -- DOI priority, else PMID/ArXiv/Hash
        doi TEXT,                           -- Normalized DOI
        title TEXT NOT NULL,
        year INTEGER,
        venue TEXT,
        source TEXT,                        -- e.g., 'zotero', 'pubmed', 'manual'
        
        -- Classification (HierPrompt)
        slot TEXT,                          -- 'mechanism', 'clinical', 'methods', etc.
        
        -- State Machine (Spec Section 6)
        -- States: NEW, FETCHED, CLASSIFIED, TAGGED, GATED, 
        --         APPROVED, PENDING_REVIEW, QUARANTINED,
        --         PDF_ATTEMPTED, PDF_DOWNLOADED, PDF_MISSING,
        --         QUARANTINED_DONE, EXPORTED, NOTED, INDEXED, DONE
        status TEXT NOT NULL DEFAULT 'NEW',
        
        -- Quality Gates (Spec Section 5.3)
        confidence REAL,                    -- 0.0 to 1.0 (LLM Confidence)
        gate_decision TEXT,                 -- 'APPROVED', 'PENDING_REVIEW', 'QUARANTINED'
        gate_reason TEXT,                   -- Why was it gated?
        evidence_snippet TEXT,              -- Critical evidence for triage/slot
        
        -- Assets
        pdf_status TEXT,                    -- 'downloaded', 'missing', 'manual'
        pdf_path TEXT,                      -- Relative path in Library/ or Storage/
        obsidian_path TEXT,                 -- Path to Markdown note
        ris_path TEXT,                      -- Path to generated RIS file
        
        -- Data Preservation & Audit
        feedback_json TEXT,                 -- JSON dump of full analysis (Golden Data / Recovery)
        agent_version TEXT,                 -- e.g., '2.1.1'
        prompt_version TEXT,                -- e.g., 'triage.v3'
        
        -- Timestamps
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_slot ON papers(slot);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);")
    
    # ---------------------------------------------------------
    # Table: review_queue (Spec Section 10.2)
    # HITL Workflow Management
    # ---------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS review_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paper_id TEXT NOT NULL,
        decision TEXT NOT NULL,             -- 'PENDING', 'QUARANTINED'
        reason TEXT,
        owner TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP,
        resolution TEXT,                    -- 'APPROVED', 'REJECTED', 'MANUAL_FIX'
        FOREIGN KEY(paper_id) REFERENCES papers(paper_id)
    );
    """)
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_review_queue_open_unique
        ON review_queue (paper_id, decision)
        WHERE resolved_at IS NULL
        """
    )

    conn.commit()
    conn.close()
    logger.info("✅ Database initialized successfully.")

if __name__ == "__main__":
    init_db()
