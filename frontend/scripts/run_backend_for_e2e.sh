#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="$(command -v python3 || command -v python)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi

BACKEND_PORT="${E2E_BACKEND_PORT:-8000}"
E2E_RUNTIME_DIR="frontend/.e2e-backend-runtime"
E2E_CONFIG_PATH="${E2E_RUNTIME_DIR}/config.e2e.yaml"
E2E_STORAGE_DIR="${E2E_RUNTIME_DIR}/storage"
E2E_ARTIFACTS_DIR="${E2E_STORAGE_DIR}/artifacts"

rm -rf "${E2E_RUNTIME_DIR}"
mkdir -p "${E2E_STORAGE_DIR}"
export PAPERPIPE_CONFIG_PATH="${E2E_CONFIG_PATH}"
export PAPERPIPE_STORAGE_DIR="${E2E_STORAGE_DIR}"
export PAPERPIPE_ARTIFACTS_DIR="${E2E_ARTIFACTS_DIR}"

cat > "${E2E_CONFIG_PATH}" <<'YAML'
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "./frontend/.e2e-backend-runtime/Library"
  obsidian_vault: "./frontend/.e2e-backend-runtime/obsidian"
  index_all: "00_Index/paper_collection.csv"
  index_clinical: "00_Index/mct_mci_trials.csv"
  upload_dir: "./frontend/.e2e-backend-runtime/NotebookLM_Upload"
  export_dir: "./frontend/.e2e-backend-runtime/export"
  watch_folder: "./frontend/.e2e-backend-runtime/Inbox"
  library_dir: "./frontend/.e2e-backend-runtime/Library"
  downloads_watch_dir: "./frontend/.e2e-backend-runtime/Downloads"
  pdf_storage_dir: "./frontend/.e2e-backend-runtime/storage/pdfs"

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

"${PYTHON_BIN}" - <<'PY'
import json
import sqlite3
from pathlib import Path
import textwrap
import yaml

root = Path.cwd()
e2e_runtime = root / "frontend" / ".e2e-backend-runtime"
db_path = e2e_runtime / "storage" / "state.db"
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
conn.executemany(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    """,
    [
        (
            "paper-e2e-001",
            "E2E Seed Paper",
            str(pdf.resolve()),
        ),
        (
            "paper-e2e-spans-001",
            "E2E Spans Seed Paper",
            str(pdf.resolve()),
        ),
    ],
)

config_raw = {}
config_path = e2e_runtime / "config.e2e.yaml"
if config_path.exists():
    try:
        config_raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        config_raw = {}

configured_vault = ((config_raw.get("paths") or {}).get("obsidian_vault")) or "./obsidian"
vault_path = Path(str(configured_vault)).expanduser()
if not vault_path.is_absolute():
    vault_path = (root / vault_path).resolve()
vault_papers_dir = vault_path / "Inbox" / "PaperPipe"
vault_papers_dir.mkdir(parents=True, exist_ok=True)

seed_pdf_uri = pdf.resolve().as_uri()

primary_slug = "zoteroduboisAlzheimerDiseaseClinicalBiological2024"
related_slug = "zoteroduboisAmnesticMCIProdromal2004"
third_slug = "zoteroduboisBloodBiomarkersClinicalPracticeTrials2022"
structured_slug = "structuredSkillsClaimset2026"
action_slug = "liveValidateCitations2026"
list_missing_slug = "paper-e2e-list-missing-stats-001"

primary_note = textwrap.dedent(
    f"""\
    ---
    id: zotero:duboisAlzheimerDiseaseClinicalBiological2024
    aliases:
      - "Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation"
    tags:
      - Medicine/Neurology
      - Alzheimers_Disease
      - ClinicalTrial
    date_processed: 2026-02-24
    confidence: 0.9
    status: INDEXED
    doi: 10.1016/S1474-4422(24)00001-2
    zotero_link: zotero://select/items/1_ABCDE
    pdf_url: {seed_pdf_uri}
    ---

    # Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation

    ## One-Line Summary
    Since 2018, Alzheimer's disease definitions increasingly focus on biological evidence.

    ## Critical Analysis
    - Study Design: Narrative working-group recommendation
    - Professor's Verdict: Strongly Approved (0.9)

    ## Key Findings & Evidence
    - The revised criteria support biological evidence as a defining axis.
    - [[Inbox/PaperPipe/{related_slug}|Amnestic MCI or prodromal Alzheimer's disease?]] is discussed as adjacent scope.

    ## Critical Review (ClaimSet)
    ### Claim 1
    - Claim: AD diagnosis can be refined through biomarker-first criteria.
    - Evidence: quote="biological evidence first", page_num=N/A
    - Confidence: 0.9

    ## 🔗 Related Papers
    - [[Inbox/PaperPipe/{related_slug}|Amnestic MCI or prodromal Alzheimer's disease?]] (shared tags: Alzheimers_Disease, Medicine/Neurology)
    - [[Inbox/PaperPipe/{third_slug}|Blood biomarkers for Alzheimer's disease in clinical practice and trials]] (shared tags: Alzheimers_Disease, Medicine/Neurology)

    ## 🔗 References
    - [Open PDF]({seed_pdf_uri})
    - [Publisher Link](https://example.org/ad-construct)
    """
)

related_note = textwrap.dedent(
    """\
    ---
    id: zotero:duboisAmnesticMCIProdromal2004
    aliases:
      - "Amnestic MCI or prodromal Alzheimer's disease?"
    tags:
      - Medicine/Neurology
      - Alzheimers_Disease
    date_processed: 2026-02-20
    confidence: 0.82
    status: INDEXED
    doi: 10.1016/S1474-4422(04)70020-4
    ---

    # Amnestic MCI or prodromal Alzheimer's disease?

    ## One-Line Summary
    Prodromal framing has clinical utility but requires careful criteria boundaries.
    """
)

third_note = textwrap.dedent(
    """\
    ---
    id: zotero:duboisBloodBiomarkersClinicalPracticeTrials2022
    aliases:
      - "Blood biomarkers for Alzheimer's disease in clinical practice and trials"
    tags:
      - Medicine/Neurology
      - Alzheimers_Disease
      - Biomarker
    date_processed: 2026-02-10
    confidence: 0.78
    status: INDEXED
    doi: 10.1016/S1474-4422(22)00414-9
    ---

    # Blood biomarkers for Alzheimer's disease in clinical practice and trials

    ## One-Line Summary
    Blood biomarkers are increasingly practical for large-scale screening and trials.
    """
)

structured_note = textwrap.dedent(
    f"""\
    ---
    id: zotero:structuredSkillsClaimset2026
    aliases:
      - "Structured Skills ClaimSet Fixture"
    tags:
      - Medicine/Neurology
      - Biomarker
      - Outcome/Memory
    date_processed: 2026-03-09
    confidence: 0.86
    status: INDEXED
    doi: 10.1016/S1474-4422(26)00009-4
    zotero_link: zotero://select/items/1_STRUCTURED
    pdf_url: {seed_pdf_uri}
    pp:
      structured_path: .pp/{structured_slug}/state.json
      last_run: "2026-03-09T09:00:00Z"
      actions_done:
        - validate_citations
        - critical_appraisal
      signals:
        citation_count: 4
        has_claimset: true
        last_appraisal: Strong
    ---

    # Structured Skills ClaimSet Fixture

    ## One-Line Summary
    This fixture note exists to prove structured automation cards render from sidecar state instead of markdown dumps.
    """
)

action_note = textwrap.dedent(
    f"""\
    ---
    id: zotero:liveValidateCitations2026
    aliases:
      - "Live Validate Citations Fixture"
    tags:
      - Medicine/Neurology
      - Workflow/Automation
    date_processed: 2026-03-09
    confidence: 0.8
    status: INDEXED
    doi: 10.1016/S1474-4422(26)00010-0
    zotero_link: zotero://select/items/1_LIVEACTION
    pdf_url: {seed_pdf_uri}
    pp:
      signals:
        citation_count: 3
    ---

    # Live Validate Citations Fixture

    ## One-Line Summary
    This fixture starts without structured runs so the list can verify the Structured only filter.
    """
)

list_missing_stats_note = textwrap.dedent(
    """\
    ---
    id: paper-e2e-list-missing-stats-001
    aliases:
      - "E2E List Missing Stats Note"
    tags:
      - Medicine/Neurology
      - Ops/Repair
    date_processed: 2026-02-26
    confidence: 0.71
    status: INDEXED
    ---

    # E2E List Missing Stats Note

    ## One-Line Summary
    This fixture stays in the action-needed state so the paper notes list can verify workbench-aligned vocabulary.
    """
)

(vault_papers_dir / f"{primary_slug}.md").write_text(primary_note, encoding="utf-8")
(vault_papers_dir / f"{related_slug}.md").write_text(related_note, encoding="utf-8")
(vault_papers_dir / f"{third_slug}.md").write_text(third_note, encoding="utf-8")
(vault_papers_dir / f"{structured_slug}.md").write_text(structured_note, encoding="utf-8")
(vault_papers_dir / f"{action_slug}.md").write_text(action_note, encoding="utf-8")
(vault_papers_dir / f"{list_missing_slug}.md").write_text(list_missing_stats_note, encoding="utf-8")

structured_state_dir = vault_path / ".pp" / structured_slug
structured_state_dir.mkdir(parents=True, exist_ok=True)
(structured_state_dir / "state.json").write_text(
    json.dumps(
        {
            "paper_slug": structured_slug,
            "updated_at": "2026-03-09T09:00:00Z",
            "runs": [],
            "claimset": [
                {
                    "id": "claim_structured_001",
                    "claim": "Amyloid and tau signals support a biomarker-led review workflow.",
                    "evidence": [{"text": "Amyloid-linked longitudinal trends improved cohort assignment stability."}],
                    "tags": ["biomarker"],
                }
            ],
            "entities": ["Amyloid", "Tau"],
            "mesh": ["Neurology"],
            "outcomes": ["memory"],
        },
        indent=2,
    ),
    encoding="utf-8",
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
artifact_dir = e2e_runtime / "storage" / "artifacts" / paper_id / run_id
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
                    "bbox_pct": {"left": 0.08, "top": 0.10, "width": 0.40, "height": 0.20},
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
                    "left": 0.52,
                    "top": 0.26,
                    "width": 0.36,
                    "height": 0.28,
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
                    "bbox": {"x": 0.14, "y": 0.60, "w": 0.44, "h": 0.18},
                }
            ],
        },
    ],
}

stats_payload = {
    "doc_id": paper_id,
    "run_id": run_id,
    "input_tables_used": [],
    "checks": [
        {
            "check_id": "check-1",
            "hypothesis": "Primary endpoint difference",
            "test_type": "t-test",
            "method": "manual_check",
            "reported_p": "0.05",
            "alpha_used": 0.05,
            "computed_p": 0.04,
            "decision_error": False,
            "code": "print('ok')",
            "outputs": "ok",
            "verdict": "verified",
            "evidence": [
                {
                    "page": 0,
                    "raw_text": "Initial improvement window observed during early follow-up period.",
                    "quote": "Initial improvement window observed during early follow-up period.",
                    "rationale": "Primary endpoint evidence used by the E2E chart-pack fixture.",
                    "highlight_source": "text_match",
                }
            ],
        },
        {
            "check_id": "check-2",
            "hypothesis": "N consistency",
            "test_type": "consistency-check",
            "method": "manual_check",
            "reported_p": "0.12",
            "alpha_used": 0.05,
            "computed_p": 0.12,
            "decision_error": False,
            "code": "print('warning')",
            "outputs": "warning",
            "verdict": "partially_verified",
            "notes": "Fixture warning for chart status counts.",
            "evidence": [
                {
                    "page": 0,
                    "raw_text": "Cohort size remained stable across the reported subgroups.",
                    "quote": "Cohort size remained stable across the reported subgroups.",
                    "rationale": "Secondary consistency evidence for the chart-pack fixture.",
                    "highlight_source": "text_match",
                }
            ],
        },
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

list_missing_paper_id = "paper-e2e-list-missing-stats-001"
list_missing_run_id = "run_e2e_list_missing_stats_001"
list_missing_artifact_dir = e2e_runtime / "storage" / "artifacts" / list_missing_paper_id / list_missing_run_id
list_missing_artifact_dir.mkdir(parents=True, exist_ok=True)
(list_missing_artifact_dir / "claimset.json").write_text(
    json.dumps(
        {
            "doc_id": list_missing_paper_id,
            "claims": [
                {
                    "claim_id": "list-missing-claim-1",
                    "statement": "The fixture intentionally omits the stats report artifact.",
                    "confidence": "medium",
                    "evidence": [{"page": 0, "quote": "Stats report intentionally omitted for recovery coverage."}],
                }
            ],
        },
        indent=2,
    ),
    encoding="utf-8",
)
(list_missing_artifact_dir / "run_meta.json").write_text(
    json.dumps({"paper_id": list_missing_paper_id, "run_id": list_missing_run_id, "status": "completed"}, indent=2),
    encoding="utf-8",
)

log_dir = e2e_runtime / "logs" / "jobs"
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

paper_id_spans = "paper-e2e-spans-001"
run_id_spans = "run_e2e_spans_001"
job_id_spans = "job-e2e-spans-001"
artifact_dir_spans = e2e_runtime / "storage" / "artifacts" / paper_id_spans / run_id_spans
artifact_dir_spans.mkdir(parents=True, exist_ok=True)

claimset_payload_spans = {
    "doc_id": paper_id_spans,
    "claims": [
        {
            "claim_id": "span-claim-1",
            "statement": "Section-aware method achieved a hit rate of 0.85.",
            "confidence": "high",
            "evidence_spans": [
                {
                    "page": 0,
                    "raw_text": "Section-aware method achieved a Hit Rate@5 of 0.85.",
                    "quote": "Section-aware method achieved a Hit Rate@5 of 0.85.",
                    "bbox_pct": {"left": 0.18, "top": 0.22, "width": 0.46, "height": 0.14},
                }
            ],
        },
        {
            "claim_id": "span-claim-2",
            "statement": "Limitations include reliance on clear PDF headers.",
            "confidence": "medium",
            "evidence_spans": [
                {
                    "page": 1,
                    "raw_text": "Limitations include the reliance on clear PDF headers.",
                    "quote": "Limitations include the reliance on clear PDF headers.",
                    "bbox": {"x": 0.12, "y": 0.48, "w": 0.66, "h": 0.14},
                }
            ],
        },
    ],
}

stats_payload_spans = {
    "doc_id": paper_id_spans,
    "run_id": run_id_spans,
    "input_tables_used": [],
    "checks": [
        {
            "check_id": "span-check-1",
            "hypothesis": "Hit-rate superiority",
            "test_type": "ranking-eval",
            "method": "manual_check",
            "reported_p": "0.03",
            "alpha_used": 0.05,
            "computed_p": 0.03,
            "decision_error": False,
            "code": "print('ok')",
            "outputs": "ok",
            "verdict": "verified",
            "evidence": [
                {
                    "page": 0,
                    "raw_text": "Section-aware method achieved a Hit Rate@5 of 0.85.",
                    "quote": "Section-aware method achieved a Hit Rate@5 of 0.85.",
                    "rationale": "Ranking-eval evidence for the spans fixture.",
                    "highlight_source": "text_match",
                }
            ],
        },
        {
            "check_id": "span-check-2",
            "hypothesis": "Header dependency risk",
            "test_type": "risk-check",
            "method": "manual_check",
            "reported_p": "0.11",
            "alpha_used": 0.05,
            "computed_p": 0.11,
            "decision_error": False,
            "code": "print('warning')",
            "outputs": "warning",
            "verdict": "partially_verified",
            "notes": "Header dependency remains a documented caveat.",
            "evidence": [
                {
                    "page": 1,
                    "raw_text": "Limitations include the reliance on clear PDF headers.",
                    "quote": "Limitations include the reliance on clear PDF headers.",
                    "rationale": "Risk evidence for the spans fixture.",
                    "highlight_source": "text_match",
                }
            ],
        },
    ]
}

bootstrap_payload_spans = {
    "artifact_document_written": False,
    "artifact_index_written": False,
    "artifact_claimset_written": True,
    "artifact_stats_written": True,
    "claimset_readiness": "ready",
    "claimset_ready": True,
    "claimset_claim_count": 2,
    "claimset_readiness_reason": "claims_present",
    "claimset_readiness_badge": "READY",
    "claimset_ops_action": "none",
    "claimset_ops_alert": False,
    "claimset_ops_note": "ready",
}

(artifact_dir_spans / "claimset.json").write_text(json.dumps(claimset_payload_spans, indent=2), encoding="utf-8")
(artifact_dir_spans / "stats_report.json").write_text(json.dumps(stats_payload_spans, indent=2), encoding="utf-8")
(artifact_dir_spans / "bootstrap_meta.json").write_text(json.dumps(bootstrap_payload_spans, indent=2), encoding="utf-8")
(artifact_dir_spans / "run_meta.json").write_text(
    json.dumps({"paper_id": paper_id_spans, "run_id": run_id_spans, "status": "completed"}, indent=2),
    encoding="utf-8",
)

log_path_spans = log_dir / f"{job_id_spans}.log"
log_lines_spans = [
    {
        "timestamp": "2026-03-09T08:10:01Z",
        "stage": "ingest",
        "progress": 20,
        "level": "INFO",
        "message": "Loaded evidence_spans fixture",
    },
    {
        "timestamp": "2026-03-09T08:10:02Z",
        "stage": "read",
        "progress": 70,
        "level": "INFO",
        "message": "Extracted 2 claims",
    },
    {
        "timestamp": "2026-03-09T08:10:03Z",
        "stage": "completed",
        "progress": 100,
        "level": "INFO",
        "message": "Pipeline completed successfully",
    },
]
log_path_spans.write_text("\n".join(json.dumps(line) for line in log_lines_spans) + "\n", encoding="utf-8")

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
        job_id_spans,
        run_id_spans,
        paper_id_spans,
        "default",
        1,
        0,
        "completed",
        100,
        "completed",
        str(artifact_dir_spans.resolve()),
        str(log_path_spans.resolve()),
    ),
)

conn.commit()
conn.close()
PY

"${PYTHON_BIN}" -m uvicorn backend.main:app --host 127.0.0.1 --port "${BACKEND_PORT}"
