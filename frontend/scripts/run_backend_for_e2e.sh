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
import json
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

conn.execute(
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        run_id TEXT,
        paper_id TEXT,
        persona_id TEXT DEFAULT 'default',
        run_verify INTEGER DEFAULT 0,
        clean_reindex INTEGER DEFAULT 0,
        status TEXT DEFAULT 'queued',
        progress INTEGER DEFAULT 0,
        stage TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        finished_at TIMESTAMP,
        artifact_dir TEXT,
        log_path TEXT,
        error_code TEXT,
        error_message TEXT
    )
    """
)

paper_id = "paper-e2e-001"
run_id = "run_e2e_fixture_001"
job_id = "job-e2e-fixture-001"
artifact_dir = root / "storage" / "artifacts" / paper_id / run_id
artifact_dir.mkdir(parents=True, exist_ok=True)

claimset_payload = {
    "doc_id": paper_id,
    "claims": [
        {
            "claim_id": "e2e-claim-1",
            "statement": "The intervention shows an initial improvement window during early follow-up.",
            "confidence": "high",
            "evidence": [
                {
                    "page": 0,
                    "quote": "Initial improvement window observed during early follow-up period.",
                    "bbox_pct": {"left": 8, "top": 10, "width": 40, "height": 20},
                }
            ],
        },
        {
            "claim_id": "e2e-claim-2",
            "statement": "A secondary response appears in a separate region on the same page.",
            "confidence": "medium",
            "evidence": [
                {
                    "page": 0,
                    "quote": "Secondary response appears in a distinct region of the analysis.",
                    "bbox_pct": {"left": 52, "top": 26, "width": 36, "height": 28},
                }
            ],
        },
        {
            "claim_id": "e2e-claim-3",
            "statement": "No severe adverse events were reported in the observed cohort.",
            "confidence": "medium",
            "evidence": [
                {
                    "page": 0,
                    "quote": "No severe adverse events were reported in the observed cohort.",
                    "bbox_pct": {"left": 14, "top": 60, "width": 44, "height": 18},
                }
            ],
        },
    ],
}

stats_payload = {
    "checks": [
        {"check_id": "check-1", "hypothesis": "Primary endpoint difference", "verdict": "pass"},
        {"check_id": "check-2", "hypothesis": "N consistency", "verdict": "warning"},
    ]
}

bootstrap_payload = {
    "artifact_document_written": False,
    "artifact_index_written": False,
    "artifact_claimset_written": True,
    "artifact_stats_written": True,
    "claimset_readiness": "ready",
    "claimset_ready": True,
    "claimset_claim_count": 3,
    "claimset_readiness_reason": "claims_present",
    "claimset_readiness_badge": "READY",
    "claimset_ops_action": "none",
    "claimset_ops_alert": False,
    "claimset_ops_note": "ready",
}

(artifact_dir / "claimset.json").write_text(json.dumps(claimset_payload, indent=2), encoding="utf-8")
(artifact_dir / "stats_report.json").write_text(json.dumps(stats_payload, indent=2), encoding="utf-8")
(artifact_dir / "bootstrap_meta.json").write_text(json.dumps(bootstrap_payload, indent=2), encoding="utf-8")
(artifact_dir / "run_meta.json").write_text(
    json.dumps({"paper_id": paper_id, "run_id": run_id, "status": "completed"}, indent=2),
    encoding="utf-8",
)

log_dir = root / "logs" / "jobs"
log_dir.mkdir(parents=True, exist_ok=True)
log_path = log_dir / f"{job_id}.log"
log_lines = [
    {
        "timestamp": "2026-02-26T13:00:01Z",
        "stage": "ingest",
        "progress": 25,
        "level": "INFO",
        "message": "Ingested 1 page",
    },
    {
        "timestamp": "2026-02-26T13:00:02Z",
        "stage": "read",
        "progress": 70,
        "level": "INFO",
        "message": "Extracted 3 claims",
    },
    {
        "timestamp": "2026-02-26T13:00:03Z",
        "stage": "completed",
        "progress": 100,
        "level": "INFO",
        "message": "Pipeline completed successfully",
    },
]
log_path.write_text("\n".join(json.dumps(line) for line in log_lines) + "\n", encoding="utf-8")

conn.execute(
    """
    INSERT OR REPLACE INTO jobs (
        job_id, run_id, paper_id, persona_id, run_verify, clean_reindex,
        status, progress, stage, created_at, started_at, finished_at,
        artifact_dir, log_path, error_code, error_message
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'), ?, ?, NULL, NULL)
    """,
    (
        job_id,
        run_id,
        paper_id,
        "default",
        1,
        0,
        "completed",
        100,
        "completed",
        str(artifact_dir.resolve()),
        str(log_path.resolve()),
    ),
)

conn.commit()
conn.close()
PY

"${PYTHON_BIN}" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
