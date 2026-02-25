#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="$(command -v python3 || command -v python)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi

if [[ ! -f "config.yaml" ]]; then
  cat > config.yaml <<'YAML'
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "./Library"
  obsidian_vault: "./obsidian"
  index_all: "00_Index/paper_collection.csv"
  index_clinical: "00_Index/mct_mci_trials.csv"
  upload_dir: "./NotebookLM_Upload"
  export_dir: "./export"
  watch_folder: "./Inbox"
  library_dir: "./Library"
  downloads_watch_dir: "./Downloads"
  pdf_storage_dir: "./storage/pdfs"

search:
  constraints:
    min_pubmed: 1
    max_preprint: 1
  slots:
    mechanism:
      query: "test"
      source: "pubmed"

llm:
  mode: "local"
  local:
    provider: "ollama"
    base_url: "http://127.0.0.1:11434"
    models:
      classifier: "llama3:8b"
      tagger: "biomistral:7b"
      embedder: "nomic-embed-text"
      judge: "openhermes-2.5-mistral"
      chat: "phi3"
  cloud:
    provider: "openai"
    api_key: ""
    model: "gpt-4o-mini"
  features:
    trial_extraction:
      enabled: false
      model: "gpt-4o-mini"
    slot_classification:
      enabled: false
      model: "gpt-4o-mini"
    one_liner:
      enabled: false
      model: "gpt-4o-mini"
  timeout_seconds: 15
  max_retries: 1

unpaywall:
  email: null

confidence_thresholds:
  high: 0.9
  low: 0.7

ranking:
  bibliometrics:
    enabled: false
    weights:
      novelty: 0.4
      impact: 0.4
      venue: 0.2
    thresholds:
      min_citations: 0.0
      min_h_index: 0.0

sources: {}
entity_aliases: {}
agents:
  enabled: false
  backend: "ollama_adapter"
  main_model: "llama3:latest"
  rag_index_path: "./storage/rag/"
  feedback_index_path: "./storage/feedback_index/"
  tools:
    retrieval: true
    python_repl: true
    web_search: false
  logging:
    trace_file: "logs/agent_trace.jsonl"
YAML
fi

"${PYTHON_BIN}" - <<'PY'
import sqlite3
from pathlib import Path

root = Path.cwd()
db_path = root / "storage" / "state.db"
db_path.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(db_path)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS papers (
        paper_id TEXT PRIMARY KEY,
        title TEXT,
        pdf_path TEXT,
        updated_at TEXT
    )
    """
)
pdf = root / "tests" / "temp_rag_test" / "Library" / "Test_ID.pdf"
conn.execute(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-001",
        "E2E Seed Paper",
        str(pdf.resolve()),
    ),
)
conn.commit()
conn.close()
PY

"${PYTHON_BIN}" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
