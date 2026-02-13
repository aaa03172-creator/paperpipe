---
trigger: always_on
---

# PaperPipe Master Rules

## 1. Safety & Boundaries (CRITICAL)
- **Zotero Safety:** READ-ONLY for the database. NEVER write to `zotero.sqlite` directly. Always generate `.ris` or `.bib` files in the `export/` directory for import.
- **Fail-Safe Processing:** If a specific paper fails (e.g., download error, parsing error), LOG the error with a traceback and `status: failed`, then **CONTINUE** to the next paper. Do not crash the entire pipeline.
- **File Operations:** Never perform destructive actions (bulk delete) without user confirmation.

## 2. Methodology & Intelligence (From Research)
- **Hierarchical Prompting:** When classifying papers into Slots (A/B/C), DO NOT ask a single yes/no question. Use a step-by-step logic (Domain -> Topic -> Specific Keywords).
- **Hybrid Tagging Strategy:**
  - **Extraction (Hard Fields):** Use Regex or KeyBERT to extract *exact* values present in the text (e.g., `dose`, `sample_size`). If not found, set to `unknown`.
  - **Generation (Soft Tags):** Use LLM to generate high-level context tags (e.g., `#topic/autophagy`) even if the exact word is missing.
- **Chunking:** When processing PDFs for summary/triage, prefer **Section-level Chunking** (Intro/Methods/Results) over raw full-text dumps.

## 3. Technology Stack
- **Language:** Python 3.10+
- **Configuration:** All adjustable parameters (queries, paths, thresholds) MUST be in `config.yaml`. No hardcoding.
- **Typing:** Use Python `typing` and `Pydantic` models for all data schemas.
- **Logging:** Use the standard `logging` module. All significant events must be logged to a file.