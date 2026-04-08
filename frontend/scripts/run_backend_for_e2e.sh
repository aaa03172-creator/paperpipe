#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3/python not found" >&2
  exit 127
fi

BACKEND_PORT="${E2E_BACKEND_PORT:-8000}"
E2E_RUNTIME_DIR="frontend/.e2e-backend-runtime"
E2E_CONFIG_PATH="${E2E_RUNTIME_DIR}/config.e2e.yaml"
E2E_SKILLS_POLICY_PATH="${E2E_RUNTIME_DIR}/skills_policy.e2e.yaml"
E2E_VAULT_REL="./frontend/.e2e-backend-runtime/obsidian"
E2E_LIBRARY_REL="./frontend/.e2e-backend-runtime/Library"
E2E_UPLOAD_REL="./frontend/.e2e-backend-runtime/NotebookLM_Upload"
E2E_EXPORT_REL="./frontend/.e2e-backend-runtime/export"
E2E_WATCH_REL="./frontend/.e2e-backend-runtime/Inbox"
E2E_DOWNLOADS_REL="./frontend/.e2e-backend-runtime/Downloads"
E2E_PDF_STORAGE_REL="./frontend/.e2e-backend-runtime/storage/pdfs"
E2E_CHART_PACKS_REL="./frontend/.e2e-backend-runtime/storage/chart_packs"
E2E_METHOD_COMPARISONS_REL="./frontend/.e2e-backend-runtime/storage/method_comparisons"
E2E_IMAGE_EVIDENCE_REL="./frontend/.e2e-backend-runtime/storage/image_evidence"
E2E_PROTOCOL_CARDS_REL="./frontend/.e2e-backend-runtime/storage/protocol_cards"
E2E_DB_REL="./frontend/.e2e-backend-runtime/storage/state.db"

rm -rf "${E2E_RUNTIME_DIR}"
mkdir -p "${E2E_RUNTIME_DIR}"
find backend src -type d -name "__pycache__" -prune -exec rm -rf {} +
export PAPERPIPE_CONFIG_PATH="${E2E_CONFIG_PATH}"
export PAPERPIPE_SKILLS_POLICY_PATH="${E2E_SKILLS_POLICY_PATH}"
export PAPERPIPE_CHART_PACKS_DIR="${E2E_CHART_PACKS_REL}"
export PAPERPIPE_METHOD_COMPARISONS_DIR="${E2E_METHOD_COMPARISONS_REL}"
export PAPERPIPE_IMAGE_EVIDENCE_DIR="${E2E_IMAGE_EVIDENCE_REL}"
export PAPERPIPE_PROTOCOL_CARDS_DIR="${E2E_PROTOCOL_CARDS_REL}"
export PAPERPIPE_DB_PATH="${E2E_DB_REL}"
export PAPERPIPE_INCLUDE_TEST_FIXTURES="1"

cat > "${E2E_CONFIG_PATH}" <<YAML
system:
  backfill_limit_days: 3
  log_level: "INFO"

paths:
  zotero_base_dir: "${E2E_LIBRARY_REL}"
  obsidian_vault: "${E2E_VAULT_REL}"
  index_all: "00_Index/paper_collection.csv"
  index_clinical: "00_Index/mct_mci_trials.csv"
  upload_dir: "${E2E_UPLOAD_REL}"
  export_dir: "${E2E_EXPORT_REL}"
  watch_folder: "${E2E_WATCH_REL}"
  library_dir: "${E2E_LIBRARY_REL}"
  downloads_watch_dir: "${E2E_DOWNLOADS_REL}"
  pdf_storage_dir: "${E2E_PDF_STORAGE_REL}"

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
    specialty_trial_extraction:
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

cat > "${E2E_SKILLS_POLICY_PATH}" <<YAML
version: 1

defaults:
  enabled: false
  sandbox: native
  network: none
  timeout_seconds: 45

project_scoped_skills:
  - markitdown
  - citation-management
  - pyzotero
  - peer-review

actions:
  extract_markdown:
    enabled: true
    category: core-safe
    source_skill: markitdown
    license: MIT
    sandbox: native
    network: none
    timeout_seconds: 60
    notes: "Prefer local-only markdown extraction."

  validate_citations:
    enabled: true
    category: core-safe
    source_skill: citation-management
    license: MIT
    sandbox: native
    network: allowlist
    network_allowlist:
      - api.openalex.org
      - doi.org
    timeout_seconds: 30
    notes: "Validate DOI and local Zotero references only."

  critical_appraisal:
    enabled: true
    category: core-safe
    source_skill: peer-review
    license: MIT
    sandbox: docker
    network: none
    secrets_required:
      - E2E_REVIEW_SECRET
    timeout_seconds: 30
    notes: "Requires local review secret before appraisal can run."
YAML

"${PYTHON_BIN}" - <<'PY'
import copy
import json
import shutil
import sqlite3
from pathlib import Path
import textwrap

root = Path.cwd()
e2e_runtime = root / "frontend" / ".e2e-backend-runtime"
vault_path = e2e_runtime / "obsidian"
shutil.rmtree(vault_path, ignore_errors=True)
db_path = root / "frontend" / ".e2e-backend-runtime" / "storage" / "state.db"
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
paper_columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
if "issues" not in paper_columns:
    conn.execute("ALTER TABLE papers ADD COLUMN issues INTEGER")
if "issues_label" not in paper_columns:
    conn.execute("ALTER TABLE papers ADD COLUMN issues_label TEXT")
if "issues_state" not in paper_columns:
    conn.execute("ALTER TABLE papers ADD COLUMN issues_state TEXT")
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        run_id TEXT,
        paper_id TEXT,
        persona_id TEXT DEFAULT 'default',
        reasoning_persona TEXT,
        profile_id TEXT,
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
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS execution_runs (
        run_id TEXT PRIMARY KEY,
        paper_id TEXT,
        trigger_source TEXT,
        pipeline_profile TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        started_at TEXT,
        finished_at TEXT,
        params_json TEXT,
        metrics_json TEXT
    )
    """
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS job_events (
        event_id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        run_id TEXT,
        ts TEXT NOT NULL,
        level TEXT NOT NULL,
        event_type TEXT NOT NULL,
        message TEXT,
        payload_json TEXT
    )
    """
)
e2e_paper_ids = [
    "paper-e2e-001",
    "paper-e2e-parser-fallback-001",
    "paper-e2e-note-backed-bbox-001",
    "paper-e2e-methodcmp-alpha-001",
    "paper-e2e-methodcmp-beta-001",
    "paper-e2e-content-review-001",
    "paper-e2e-content-review-unavailable-001",
    "paper-e2e-list-missing-stats-001",
    "paper-e2e-repair-001",
    "paper-e2e-rebuild-001",
]
conn.executemany("DELETE FROM jobs WHERE paper_id = ?", [(paper_id,) for paper_id in e2e_paper_ids])
conn.executemany("DELETE FROM execution_runs WHERE paper_id = ?", [(paper_id,) for paper_id in e2e_paper_ids])
conn.executemany("DELETE FROM papers WHERE paper_id = ?", [(paper_id,) for paper_id in e2e_paper_ids])
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS user_actions (
        action_id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        paper_id TEXT,
        action_type TEXT NOT NULL,
        source TEXT NOT NULL,
        payload_json TEXT
    )
    """
)
conn.executemany("DELETE FROM user_actions WHERE paper_id = ?", [(paper_id,) for paper_id in e2e_paper_ids])

artifacts_root = root / "storage" / "artifacts"
for paper_id in e2e_paper_ids:
    shutil.rmtree(artifacts_root / paper_id, ignore_errors=True)

logs_root = root / "logs" / "jobs"
if logs_root.exists():
    for path in logs_root.glob("job-e2e-*.log"):
        path.unlink(missing_ok=True)

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
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-parser-fallback-001",
        "E2E Parser Fallback Paper",
        str(pdf.resolve()),
    ),
)
conn.execute(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-note-backed-bbox-001",
        "E2E Note-backed BBox Fixture",
        str(pdf.resolve()),
    ),
)
conn.execute(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-methodcmp-alpha-001",
        "E2E Method Comparison Alpha",
        str(pdf.resolve()),
    ),
)
conn.execute(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-methodcmp-beta-001",
        "E2E Method Comparison Beta",
        str(pdf.resolve()),
    ),
)
conn.execute(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, issues, issues_label, issues_state, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-content-review-001",
        "E2E Content Review Paper",
        str(pdf.resolve()),
        2,
        "2 mapping ambiguities",
        "flagged",
    ),
)
conn.execute(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, issues, issues_label, issues_state, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-content-review-unavailable-001",
        "E2E Content Review Unavailable Paper",
        str(pdf.resolve()),
        0,
        "Not analyzed",
        "unavailable",
    ),
)
conn.execute(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, issues, issues_label, issues_state, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-list-missing-stats-001",
        "E2E List Missing Stats Paper",
        str(pdf.resolve()),
        0,
        "No critical issues",
        "clear",
    ),
)
conn.execute(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-repair-001",
        "E2E Repair Stats Paper",
        str(pdf.resolve()),
    ),
)
conn.execute(
    """
    INSERT OR REPLACE INTO papers (paper_id, title, pdf_path, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    """,
    (
        "paper-e2e-rebuild-001",
        "E2E Rebuild Stats Paper",
        str(pdf.resolve()),
    ),
)

vault_papers_dir = vault_path / "Inbox" / "PaperPipe"
vault_papers_dir.mkdir(parents=True, exist_ok=True)

seed_pdf_uri = pdf.resolve().as_uri()

primary_slug = "zoteroduboisAlzheimerDiseaseClinicalBiological2024"
note_backed_slug = "zoteroe2eNoteBackedBBox2026"
note_backed_workbench_id = "paper-e2e-note-backed-bbox-001"
methodcmp_alpha_slug = "paper-e2e-methodcmp-alpha-001"
methodcmp_beta_slug = "paper-e2e-methodcmp-beta-001"
related_slug = "zoteroduboisAmnesticMCIProdromal2004"
third_slug = "zoteroduboisBloodBiomarkersClinicalPracticeTrials2022"
structured_slug = "zoterostructuredSkillsClaimset2026"
structured_signal_peer_slug = "zoterostructuredSignalsPeer2026"
action_slug = "zoteroliveValidateCitations2026"
quiet_action_slug = "zoteroquietValidateCitations2026"

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
    pp:
      structured_path: .pp/{primary_slug}/state.json
      last_run: 2026-02-26T13:00:03Z
      actions_done:
        - critical_appraisal
      signals:
        has_claimset: true
        claim_count: 2
        evidence_count: 2
        run_count: 1
        last_run_id: skill-20260226T130003000000+0000-critical_appraisal
        last_action: critical_appraisal
        last_status: succeeded
        last_appraisal: Strongly Approved
        citation_count: 2
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

note_backed_note = textwrap.dedent(
    f"""\
    ---
    id: {note_backed_workbench_id}
    aliases:
      - "E2E Note-backed BBox Fixture"
    tags:
      - Medicine/Neurology
      - E2E
    date_processed: 2026-02-24
    confidence: 0.92
    status: INDEXED
    pdf_url: {seed_pdf_uri}
    pp:
      structured_path: .pp/{note_backed_slug}/state.json
      last_run: 2026-02-26T13:00:03Z
      actions_done:
        - critical_appraisal
      signals:
        has_claimset: true
        claim_count: 2
        evidence_count: 2
        run_count: 1
        last_run_id: skill-20260226T130003000000+0000-critical_appraisal
        last_action: critical_appraisal
        last_status: succeeded
    ---

    # E2E Note-backed BBox Fixture

    ## One-Line Summary
    This fixture proves that Workbench prefers canonical state.json bbox highlights over stale artifact text matches.
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

    ## Critical Review (ClaimSet)
    Structured JSON is the source of truth for automation results in this note.

    ## 🔗 References
    - [Open PDF]({seed_pdf_uri})
    - [DOI Link](https://doi.org/10.1016/S1474-4422(26)00009-4)
    - [Publisher Link](https://example.org/structured-skills)
    - [Zotero](zotero://select/items/1_STRUCTURED)
    """
)

structured_signal_peer_note = textwrap.dedent(
    """\
    ---
    id: zotero:structuredSignalsPeer2026
    aliases:
      - "Structured Signals Peer Fixture"
    tags:
      - Workflow/Automation
      - Notes/Related
    date_processed: 2026-03-08
    confidence: 0.84
    status: INDEXED
    doi: 10.1016/S1474-4422(26)00011-2
    ---

    # Structured Signals Peer Fixture

    ## One-Line Summary
    This fixture overlaps through structured entities and outcomes rather than frontmatter tags.
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
    This fixture starts without structured runs but with a stale citation summary so backend e2e can validate changed and new signal updates.

    ## 🔗 References
    - [Publisher Link](https://example.org/live-validate-citations)
    """
)

quiet_action_note = textwrap.dedent(
    f"""\
    ---
    id: zotero:quietValidateCitations2026
    aliases:
      - "Quiet Validate Citations Fixture"
    tags:
      - Medicine/Neurology
      - Workflow/Automation
    date_processed: 2026-03-09
    confidence: 0.79
    status: INDEXED
    doi: 10.1016/S1474-4422(26)00012-4
    zotero_link: zotero://select/items/1_QUIETACTION
    pdf_url: {seed_pdf_uri}
    pp:
      signals:
        citation_count: 3
    ---

    # Quiet Validate Citations Fixture

    ## One-Line Summary
    This fixture starts without structured runs, keeps a stale citation summary, and verifies that quiet skill runs can skip markdown body appends.

    ## 🔗 References
    - [Publisher Link](https://example.org/quiet-validate-citations)
    """
)

repair_note = textwrap.dedent(
    f"""\
    ---
    id: paper-e2e-repair-001
    aliases:
      - "E2E Repair Stats Note"
    tags:
      - Medicine/Neurology
      - Ops/Repair
    date_processed: 2026-02-25
    confidence: 0.67
    status: INDEXED
    ---

    # E2E Repair Stats Note

    ## One-Line Summary
    This fixture note mirrors a paper whose ClaimSet exists but Stats Snapshot is missing.

    ## Critical Analysis
    - Intended for backend e2e coverage of Repair Stats entry points.
    """
)

parser_fallback_note = textwrap.dedent(
    """\
    ---
    id: paper-e2e-parser-fallback-001
    aliases:
      - "E2E Parser Fallback Note"
    tags:
      - Medicine/Neurology
      - Ops/ParserPilot
    date_processed: 2026-03-24
    confidence: 0.76
    status: INDEXED
    ---

    # E2E Parser Fallback Note

    ## One-Line Summary
    This fixture proves the workbench distinguishes requested parser overrides from the resolved runtime backend.
    """
)

rebuild_note = textwrap.dedent(
    """\
    ---
    id: paper-e2e-rebuild-001
    aliases:
      - "E2E Rebuild Stats Note"
    tags:
      - Medicine/Neurology
      - Ops/Repair
    date_processed: 2026-02-27
    confidence: 0.73
    status: INDEXED
    ---

    # E2E Rebuild Stats Note

    ## One-Line Summary
    This fixture keeps a stale Stats Snapshot so backend e2e can validate the overwrite-only rebuild path.

    ## Critical Analysis
    - Intended for backend e2e coverage of Advanced actions > Rebuild Stats.
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

methodcmp_alpha_note = textwrap.dedent(
    """\
    ---
    id: paper-e2e-methodcmp-alpha-001
    aliases:
      - "E2E Method Comparison Alpha"
    tags:
      - Medicine/Neurology
      - E2E
      - MethodComparison
    date_processed: 2026-03-18
    confidence: 0.81
    status: INDEXED
    ---

    # E2E Method Comparison Alpha

    ## One-Line Summary
    Stable fixture note for multi-paper Method Comparison backend smoke.
    """
)

methodcmp_beta_note = textwrap.dedent(
    """\
    ---
    id: paper-e2e-methodcmp-beta-001
    aliases:
      - "E2E Method Comparison Beta"
    tags:
      - Medicine/Neurology
      - E2E
      - MethodComparison
    date_processed: 2026-03-18
    confidence: 0.79
    status: INDEXED
    ---

    # E2E Method Comparison Beta

    ## One-Line Summary
    Stable fixture note for row-order and multi-column Method Comparison smoke.
    """
)

(vault_papers_dir / f"{primary_slug}.md").write_text(primary_note, encoding="utf-8")
(vault_papers_dir / f"{note_backed_slug}.md").write_text(note_backed_note, encoding="utf-8")
(vault_papers_dir / f"{methodcmp_alpha_slug}.md").write_text(methodcmp_alpha_note, encoding="utf-8")
(vault_papers_dir / f"{methodcmp_beta_slug}.md").write_text(methodcmp_beta_note, encoding="utf-8")
(vault_papers_dir / f"{related_slug}.md").write_text(related_note, encoding="utf-8")
(vault_papers_dir / f"{third_slug}.md").write_text(third_note, encoding="utf-8")
(vault_papers_dir / f"{structured_slug}.md").write_text(structured_note, encoding="utf-8")
(vault_papers_dir / f"{structured_signal_peer_slug}.md").write_text(structured_signal_peer_note, encoding="utf-8")
(vault_papers_dir / f"{action_slug}.md").write_text(action_note, encoding="utf-8")
(vault_papers_dir / f"{quiet_action_slug}.md").write_text(quiet_action_note, encoding="utf-8")
(vault_papers_dir / "paper-e2e-parser-fallback-001.md").write_text(parser_fallback_note, encoding="utf-8")
(vault_papers_dir / "paper-e2e-repair-001.md").write_text(repair_note, encoding="utf-8")
(vault_papers_dir / "paper-e2e-rebuild-001.md").write_text(rebuild_note, encoding="utf-8")
(vault_papers_dir / "paper-e2e-list-missing-stats-001.md").write_text(list_missing_stats_note, encoding="utf-8")

structured_state_dir = vault_path / ".pp" / structured_slug
structured_runs_dir = structured_state_dir / "runs"
structured_runs_dir.mkdir(parents=True, exist_ok=True)
structured_signal_peer_state_dir = vault_path / ".pp" / structured_signal_peer_slug
structured_signal_peer_state_dir.mkdir(parents=True, exist_ok=True)

structured_state_payload = {
    "schema_version": "2026-03-09.chat-hooks.v1",
    "paper_slug": structured_slug,
    "updated_at": "2026-03-09T09:00:00Z",
    "runs": [
        {
            "id": "skill-20260309T090000Z-critical_appraisal",
            "action": "critical_appraisal",
            "ts": "2026-03-09T09:00:00Z",
            "status": "succeeded",
            "summary": "Strong: 2 claims, avg confidence 0.81, 0 inconsistent checks.",
            "artifacts": {"claimset_source": "state.json", "sandbox": "native-fallback"},
            "data": {
                "appraisal": {
                    "label": "Strong",
                    "claim_count": 2,
                    "evidence_count": 3,
                    "avg_confidence": 0.81,
                    "verified_checks": 2,
                    "inconsistent_checks": 0,
                }
            },
        },
        {
            "id": "skill-20260309T083000Z-validate_citations",
            "action": "validate_citations",
            "ts": "2026-03-09T08:30:00Z",
            "status": "succeeded",
            "summary": "Checked 4 references: 1 verified, 2 local, 1 need review.",
            "artifacts": {"engine": "citation-management"},
            "data": {"reference_count": 4},
        },
    ],
    "signals": {
        "has_claimset": True,
        "claim_count": 2,
        "evidence_count": 3,
        "run_count": 2,
        "last_run_id": "skill-20260309T090000Z-critical_appraisal",
        "last_action": "critical_appraisal",
        "last_status": "succeeded",
        "citation_count": 4,
        "last_appraisal": "Strong",
    },
    "claimset": [
        {
            "id": "claim_structured_001",
            "run_id": "skill-20260309T090000Z-critical_appraisal",
            "claim": "CSF biomarker evidence aligns with early detection criteria.",
            "evidence_ids": ["evidence_structured_001", "evidence_structured_002"],
            "evidence": [
                {
                    "id": "evidence_structured_001",
                    "claim_id": "claim_structured_001",
                    "run_id": "skill-20260309T090000Z-critical_appraisal",
                    "text": "CSF amyloid and tau shifts separate early-stage cases from controls.",
                    "page": 2,
                    "section": "Results",
                    "source": "text_match",
                    "locator": {
                        "page": 2,
                        "span": [18, 74],
                        "section": "Results",
                        "source": "text_match",
                    },
                },
                {
                    "id": "evidence_structured_002",
                    "claim_id": "claim_structured_001",
                    "run_id": "skill-20260309T090000Z-critical_appraisal",
                    "text": "The biomarker panel remained stable across repeat measurements.",
                    "page": 3,
                    "section": "Supplement",
                    "source": "table_cell",
                    "locator": {
                        "page": 3,
                        "span": [4, 29],
                        "section": "Supplement",
                        "source": "table_cell",
                        "table_id": "tbl-1",
                        "cell_id": "r2c3",
                    },
                },
            ],
            "confidence": 0.86,
            "tags": ["biomarker", "early-detection"],
            "outcomes": ["memory"],
        },
        {
            "id": "claim_structured_002",
            "run_id": "skill-20260309T090000Z-critical_appraisal",
            "claim": "The longitudinal signal supports trial stratification rather than standalone diagnosis.",
            "evidence_ids": ["evidence_structured_003"],
            "evidence": [
                {
                    "id": "evidence_structured_003",
                    "claim_id": "claim_structured_002",
                    "run_id": "skill-20260309T090000Z-critical_appraisal",
                    "text": "Longitudinal signal improved cohort selection for follow-up assessment.",
                    "page": 4,
                    "section": "Discussion",
                    "source": "text_match",
                    "locator": {
                        "page": 4,
                        "span": [11, 52],
                        "section": "Discussion",
                        "source": "text_match",
                    },
                }
            ],
            "confidence": 0.76,
            "tags": ["trial-stratification"],
            "outcomes": ["cohort-design"],
        },
    ],
    "entities": ["Amyloid", "Tau"],
    "mesh": ["Neurology"],
    "outcomes": ["memory", "cohort-design"],
}

(structured_state_dir / "state.json").write_text(
    json.dumps(structured_state_payload, indent=2),
    encoding="utf-8",
)
(structured_runs_dir / "20260309T090000Z_critical_appraisal.json").write_text(
    json.dumps(
        {
            "paper_slug": structured_slug,
            "run": structured_state_payload["runs"][0],
            "policy": {"network": "none", "sandbox": "docker", "license": "MIT"},
            "logs": ["Loaded structured ClaimSet fixture."],
            "data": structured_state_payload["runs"][0]["data"],
        },
        indent=2,
    ),
    encoding="utf-8",
)
(structured_runs_dir / "20260309T083000Z_validate_citations.json").write_text(
    json.dumps(
        {
            "paper_slug": structured_slug,
            "run": structured_state_payload["runs"][1],
            "policy": {"network": "none", "sandbox": "native", "license": "MIT"},
            "logs": ["Validated DOI, local PDF, Zotero URI, and publisher link."],
            "data": structured_state_payload["runs"][1]["data"],
        },
        indent=2,
    ),
    encoding="utf-8",
)
(structured_signal_peer_state_dir / "state.json").write_text(
    json.dumps(
        {
            "schema_version": "2026-03-09.chat-hooks.v1",
            "paper_slug": structured_signal_peer_slug,
            "updated_at": "2026-03-09T08:45:00Z",
            "runs": [
                {
                    "id": "skill-20260309T084500Z-critical_appraisal",
                    "action": "critical_appraisal",
                    "ts": "2026-03-09T08:45:00Z",
                    "status": "succeeded",
                    "summary": "Mixed: 1 claim, avg confidence 0.74, 0 inconsistent checks.",
                    "artifacts": {"claimset_source": "state.json", "sandbox": "native-fallback"},
                    "data": {
                        "appraisal": {
                            "label": "Mixed",
                            "claim_count": 1,
                            "evidence_count": 1,
                            "avg_confidence": 0.74,
                            "verified_checks": 1,
                            "inconsistent_checks": 0,
                        }
                    },
                }
            ],
            "signals": {
                "has_claimset": True,
                "claim_count": 1,
                "evidence_count": 1,
                "run_count": 1,
                "last_run_id": "skill-20260309T084500Z-critical_appraisal",
                "last_action": "critical_appraisal",
                "last_status": "succeeded",
                "citation_count": 2,
                "last_appraisal": "Mixed",
            },
            "claimset": [
                {
                    "id": "claim_structured_peer_001",
                    "run_id": "skill-20260309T084500Z-critical_appraisal",
                    "claim": "Amyloid-linked longitudinal signals are useful for cohort selection.",
                    "evidence_ids": ["evidence_structured_peer_001"],
                    "evidence": [
                        {
                            "id": "evidence_structured_peer_001",
                            "claim_id": "claim_structured_peer_001",
                            "run_id": "skill-20260309T084500Z-critical_appraisal",
                            "text": "Amyloid-linked longitudinal trends improved cohort assignment stability.",
                            "page": 1,
                            "section": "Results",
                            "source": "text_match",
                            "locator": {
                                "page": 1,
                                "span": [9, 48],
                                "section": "Results",
                                "source": "text_match",
                            },
                        }
                    ],
                    "confidence": 0.74,
                    "tags": ["biomarker"],
                    "outcomes": ["memory"],
                }
            ],
            "entities": ["Amyloid"],
            "mesh": ["Neurology"],
            "outcomes": ["memory"],
        },
        indent=2,
    ),
    encoding="utf-8",
)

conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_user_actions_paper ON user_actions(paper_id, ts)"
)

job_columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
if "persona_id" not in job_columns:
    conn.execute("ALTER TABLE jobs ADD COLUMN persona_id TEXT DEFAULT 'default'")
if "reasoning_persona" not in job_columns:
    conn.execute("ALTER TABLE jobs ADD COLUMN reasoning_persona TEXT")
if "profile_id" not in job_columns:
    conn.execute("ALTER TABLE jobs ADD COLUMN profile_id TEXT")
if "run_verify" not in job_columns:
    conn.execute("ALTER TABLE jobs ADD COLUMN run_verify INTEGER DEFAULT 0")
if "clean_reindex" not in job_columns:
    conn.execute("ALTER TABLE jobs ADD COLUMN clean_reindex INTEGER DEFAULT 0")

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
            "type": "efficacy",
            "statement": "The intervention shows an initial improvement window during early follow-up.",
            "confidence": 0.9,
            "limitations": [],
            "evidence_spans": [
                {
                    "page": 0,
                    "raw_text": "Initial improvement window observed during early follow-up period.",
                    "quote": "Initial improvement window observed during early follow-up period.",
                    "rationale": "Supports early response trajectory in treated arm.",
                    "bbox_pct": {"left": 0.08, "top": 0.1, "width": 0.4, "height": 0.2},
                    "highlight_source": "bbox",
                }
            ],
        },
        {
            "claim_id": "e2e-claim-2",
            "type": "efficacy",
            "statement": "A secondary response appears in a separate region on the same page.",
            "confidence": 0.72,
            "limitations": [],
            "evidence_spans": [
                {
                    "page": 0,
                    "raw_text": "Secondary response appears in a distinct region of the analysis.",
                    "quote": "Secondary response appears in a distinct region of the analysis.",
                    "rationale": "Independent region indicates secondary signal.",
                    "bbox_pct": {"left": 520, "top": 364, "width": 320, "height": 280},
                    "highlight_source": "bbox",
                }
            ],
        },
        {
            "claim_id": "e2e-claim-3",
            "type": "safety",
            "statement": "No severe adverse events were reported in the observed cohort.",
            "confidence": 0.74,
            "limitations": [],
            "evidence_spans": [
                {
                    "page": 1,
                    "raw_text": "No severe adverse events were reported in the observed cohort.",
                    "quote": "No severe adverse events were reported in the observed cohort.",
                    "rationale": "Safety statement supported by adverse-event summary.",
                    "bbox_pct": {"left": 14, "top": 60, "width": 44, "height": 18},
                    "highlight_source": "bbox",
                }
            ],
        },
    ],
}

document_payload = {
    "doc_id": paper_id,
    "pages": [
        {
            "page_index": 0,
            "width": 1000,
            "height": 1400,
            "blocks": [],
        },
        {
            "page_index": 1,
            "width": 1000,
            "height": 1400,
            "blocks": [],
        },
    ],
}

stats_payload = {
    "doc_id": paper_id,
    "run_id": run_id,
    "checks": [
        {
            "check_id": "stats-check-1",
            "hypothesis": "Primary intervention consistency",
            "test_type": "consistency",
            "code": "print('ok')",
            "outputs": "ok",
            "verdict": "verified",
            "decision_error": False,
            "notes": "Initial window response aligns with primary claim.",
            "evidence": [
                {
                    "page": 0,
                    "raw_text": "Initial improvement window observed during early follow-up period.",
                    "quote": "Initial improvement window observed during early follow-up period.",
                }
            ],
        },
        {
            "check_id": "stats-check-2",
            "hypothesis": "No severe adverse events were reported in the observed cohort.",
            "test_type": "effect-size-disambiguation",
            "code": "print('ok')",
            "outputs": "ok",
            "verdict": "verified",
            "decision_error": False,
            "notes": "Map safety check to adverse-events claim even when evidence page overlaps primary page hint.",
            "evidence": [
                {
                    "page": 0,
                    "raw_text": "No severe adverse events were reported in the observed cohort.",
                    "quote": "No severe adverse events were reported in the observed cohort.",
                }
            ],
        },
    ],
}

bootstrap_payload = {
    "artifact_document_written": True,
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

structured_state_payload = {
    "schema_version": "2026-03-09.chat-hooks.v1",
    "paper_slug": primary_slug,
    "updated_at": "2026-02-26T13:00:03Z",
    "runs": [
        {
            "id": "skill-20260226T130003000000+0000-critical_appraisal",
            "action": "critical_appraisal",
            "ts": "2026-02-26T13:00:03Z",
            "status": "succeeded",
            "summary": "Structured claimset ready for review.",
            "artifacts": {
                "sandbox": "docker",
                "claimset_source": "state.json",
            },
            "data": {
                "inconsistency_count": 0,
            },
        }
    ],
    "signals": {
        "has_claimset": True,
        "claim_count": 2,
        "evidence_count": 2,
        "run_count": 1,
        "last_run_id": "skill-20260226T130003000000+0000-critical_appraisal",
        "last_action": "critical_appraisal",
        "last_status": "succeeded",
        "last_appraisal": "Strongly Approved",
        "citation_count": 2,
    },
    "claimset": [
        {
            "id": "claim_c0ffee000001",
            "source_claim_id": "e2e-claim-1",
            "run_id": "skill-20260226T130003000000+0000-critical_appraisal",
            "claim": "The intervention shows an initial improvement window during early follow-up.",
            "evidence_ids": ["evidence_deadbeef0001"],
            "evidence": [
                {
                    "id": "evidence_deadbeef0001",
                    "claim_id": "claim_c0ffee000001",
                    "run_id": "skill-20260226T130003000000+0000-critical_appraisal",
                    "text": "Initial improvement window observed during early follow-up period.",
                    "page": 0,
                    "section": "Key Findings & Evidence",
                    "source": "bbox",
                    "locator": {
                        "page": 0,
                        "span": [0, 57],
                        "section": "Key Findings & Evidence",
                        "chunk_id": "chunk-e2e-001",
                        "bbox_pct": {"left": 8, "top": 10, "width": 40, "height": 20},
                        "source": "bbox",
                    },
                }
            ],
            "confidence": 0.9,
            "tags": ["efficacy", "biomarker"],
            "outcomes": ["diagnostic criteria"],
        },
        {
            "id": "claim_c0ffee000002",
            "source_claim_id": "e2e-claim-3",
            "run_id": "skill-20260226T130003000000+0000-critical_appraisal",
            "claim": "No severe adverse events were reported in the observed cohort.",
            "evidence_ids": ["evidence_deadbeef0002"],
            "evidence": [
                {
                    "id": "evidence_deadbeef0002",
                    "claim_id": "claim_c0ffee000002",
                    "run_id": "skill-20260226T130003000000+0000-critical_appraisal",
                    "text": "No severe adverse events were reported in the observed cohort.",
                    "page": 1,
                    "section": "Critical Review (ClaimSet)",
                    "source": "text_match",
                    "locator": {
                        "page": 1,
                        "span": [0, 61],
                        "section": "Critical Review (ClaimSet)",
                        "chunk_id": "chunk-e2e-002",
                        "source": "text_match",
                    },
                }
            ],
            "confidence": 0.74,
            "tags": ["safety"],
            "outcomes": ["adverse events"],
        },
    ],
    "entities": ["Alzheimer Disease"],
    "mesh": ["Biomarkers"],
    "outcomes": ["diagnostic criteria", "adverse events"],
}

(artifact_dir / "claimset.resolved.json").write_text(json.dumps(claimset_payload, indent=2), encoding="utf-8")
(artifact_dir / "claimset.json").write_text(json.dumps(claimset_payload, indent=2), encoding="utf-8")
(artifact_dir / "document_artifact.json").write_text(json.dumps(document_payload, indent=2), encoding="utf-8")
(artifact_dir / "stats_report.json").write_text(json.dumps(stats_payload, indent=2), encoding="utf-8")
(artifact_dir / "bootstrap_meta.json").write_text(json.dumps(bootstrap_payload, indent=2), encoding="utf-8")
(artifact_dir / "run_meta.json").write_text(
    json.dumps({"paper_id": paper_id, "run_id": run_id, "status": "completed"}, indent=2),
    encoding="utf-8",
)
(vault_path / ".pp" / primary_slug / "state.json").parent.mkdir(parents=True, exist_ok=True)
(vault_path / ".pp" / primary_slug / "state.json").write_text(
    json.dumps(structured_state_payload, indent=2),
    encoding="utf-8",
)
note_backed_structured_state_payload = copy.deepcopy(structured_state_payload)
note_backed_structured_state_payload["paper_slug"] = note_backed_slug
(vault_path / ".pp" / note_backed_slug / "state.json").parent.mkdir(parents=True, exist_ok=True)
(vault_path / ".pp" / note_backed_slug / "state.json").write_text(
    json.dumps(note_backed_structured_state_payload, indent=2),
    encoding="utf-8",
)

note_backed_paper_id = note_backed_workbench_id
note_backed_run_id = "run_e2e_note_backed_bbox_001"
note_backed_artifact_dir = root / "storage" / "artifacts" / note_backed_paper_id / note_backed_run_id
note_backed_artifact_dir.mkdir(parents=True, exist_ok=True)

parser_fallback_paper_id = "paper-e2e-parser-fallback-001"
parser_fallback_run_id = "run_e2e_parser_fallback_001"
parser_fallback_job_id = "job-e2e-parser-fallback-001"
parser_fallback_artifact_dir = root / "storage" / "artifacts" / parser_fallback_paper_id / parser_fallback_run_id
parser_fallback_artifact_dir.mkdir(parents=True, exist_ok=True)

parser_fallback_claimset_payload = copy.deepcopy(claimset_payload)
parser_fallback_claimset_payload["doc_id"] = parser_fallback_paper_id
parser_fallback_document_payload = copy.deepcopy(document_payload)
parser_fallback_document_payload["doc_id"] = parser_fallback_paper_id
parser_fallback_stats_payload = copy.deepcopy(stats_payload)
parser_fallback_stats_payload["doc_id"] = parser_fallback_paper_id
parser_fallback_stats_payload["run_id"] = parser_fallback_run_id
parser_fallback_bootstrap_payload = copy.deepcopy(bootstrap_payload)
parser_fallback_bootstrap_payload["parser_backend"] = "fitz_pdfplumber"

(parser_fallback_artifact_dir / "claimset.resolved.json").write_text(
    json.dumps(parser_fallback_claimset_payload, indent=2),
    encoding="utf-8",
)
(parser_fallback_artifact_dir / "claimset.json").write_text(
    json.dumps(parser_fallback_claimset_payload, indent=2),
    encoding="utf-8",
)
(parser_fallback_artifact_dir / "document_artifact.json").write_text(
    json.dumps(parser_fallback_document_payload, indent=2),
    encoding="utf-8",
)
(parser_fallback_artifact_dir / "stats_report.json").write_text(
    json.dumps(parser_fallback_stats_payload, indent=2),
    encoding="utf-8",
)
(parser_fallback_artifact_dir / "bootstrap_meta.json").write_text(
    json.dumps(parser_fallback_bootstrap_payload, indent=2),
    encoding="utf-8",
)
(parser_fallback_artifact_dir / "run_meta.json").write_text(
    json.dumps(
        {"paper_id": parser_fallback_paper_id, "run_id": parser_fallback_run_id, "status": "completed"},
        indent=2,
    ),
    encoding="utf-8",
)

note_backed_claimset_payload = {
    "doc_id": note_backed_paper_id,
    "claims": [
        {
            "claim_id": "stale-artifact-claim-1",
            "type": "efficacy",
            "statement": "Stale artifact claim should be replaced by canonical sidecar state.",
            "confidence": 0.42,
            "limitations": [],
            "evidence_spans": [
                {
                    "page": 0,
                    "raw_text": "Artifact-only text match span.",
                    "quote": "Artifact-only text match span.",
                    "rationale": "Old artifact fallback without bbox.",
                    "highlight_source": "text_match",
                }
            ],
        }
    ],
}
note_backed_document_payload = copy.deepcopy(document_payload)
note_backed_document_payload["doc_id"] = note_backed_paper_id
note_backed_stats_payload = {
    "doc_id": note_backed_paper_id,
    "run_id": note_backed_run_id,
    "checks": [
        {
            "check_id": "note-backed-check-1",
            "hypothesis": "Canonical state should drive bbox-backed highlighting",
            "test_type": "consistency",
            "code": "print('ok')",
            "outputs": "ok",
            "verdict": "verified",
            "decision_error": False,
            "notes": "Structured sidecar should override stale artifact text-match fallback.",
            "evidence": [
                {
                    "page": 0,
                    "raw_text": "Initial improvement window observed during early follow-up period.",
                    "quote": "Initial improvement window observed during early follow-up period.",
                }
            ],
        }
    ],
}
note_backed_bootstrap_payload = copy.deepcopy(bootstrap_payload)

(note_backed_artifact_dir / "claimset.resolved.json").write_text(
    json.dumps(note_backed_claimset_payload, indent=2),
    encoding="utf-8",
)
(note_backed_artifact_dir / "claimset.json").write_text(
    json.dumps(note_backed_claimset_payload, indent=2),
    encoding="utf-8",
)
(note_backed_artifact_dir / "document_artifact.json").write_text(
    json.dumps(note_backed_document_payload, indent=2),
    encoding="utf-8",
)
(note_backed_artifact_dir / "stats_report.json").write_text(
    json.dumps(note_backed_stats_payload, indent=2),
    encoding="utf-8",
)
(note_backed_artifact_dir / "bootstrap_meta.json").write_text(
    json.dumps(note_backed_bootstrap_payload, indent=2),
    encoding="utf-8",
)
(note_backed_artifact_dir / "run_meta.json").write_text(
    json.dumps({"paper_id": note_backed_paper_id, "run_id": note_backed_run_id, "status": "completed"}, indent=2),
    encoding="utf-8",
)

methodcmp_alpha_paper_id = "paper-e2e-methodcmp-alpha-001"
methodcmp_alpha_run_id = "run_e2e_methodcmp_alpha_001"
methodcmp_alpha_artifact_dir = root / "storage" / "artifacts" / methodcmp_alpha_paper_id / methodcmp_alpha_run_id
methodcmp_alpha_artifact_dir.mkdir(parents=True, exist_ok=True)
methodcmp_alpha_claimset_payload = {
    "doc_id": methodcmp_alpha_paper_id,
    "claims": [
        {
            "claim_id": "methodcmp-alpha-claim-1",
            "type": "methods",
            "statement": "Intervention: Ketone ester. Comparator: Placebo. Primary outcome: ADAS-Cog score. Participants were treated with Ketone ester for 12 weeks.",
            "sample_size": 48,
            "confidence": 0.87,
            "limitations": [],
            "evidence_spans": [
                {
                    "page": 1,
                    "raw_text": "Intervention: Ketone ester. Comparator: Placebo. Primary outcome: ADAS-Cog score. Participants were treated with Ketone ester for 12 weeks. Sample size: 48.",
                    "quote": "Intervention: Ketone ester. Comparator: Placebo. Primary outcome: ADAS-Cog score. Participants were treated with Ketone ester for 12 weeks. Sample size: 48.",
                    "rationale": "Seeded explicit method-comparison fixture for alpha.",
                    "highlight_source": "text_match",
                }
            ],
        }
    ],
}
(methodcmp_alpha_artifact_dir / "claimset.resolved.json").write_text(
    json.dumps(methodcmp_alpha_claimset_payload, indent=2),
    encoding="utf-8",
)
(methodcmp_alpha_artifact_dir / "claimset.json").write_text(
    json.dumps(methodcmp_alpha_claimset_payload, indent=2),
    encoding="utf-8",
)
(methodcmp_alpha_artifact_dir / "run_meta.json").write_text(
    json.dumps({"paper_id": methodcmp_alpha_paper_id, "run_id": methodcmp_alpha_run_id, "status": "completed"}, indent=2),
    encoding="utf-8",
)

methodcmp_beta_paper_id = "paper-e2e-methodcmp-beta-001"
methodcmp_beta_run_id = "run_e2e_methodcmp_beta_001"
methodcmp_beta_artifact_dir = root / "storage" / "artifacts" / methodcmp_beta_paper_id / methodcmp_beta_run_id
methodcmp_beta_artifact_dir.mkdir(parents=True, exist_ok=True)
methodcmp_beta_claimset_payload = {
    "doc_id": methodcmp_beta_paper_id,
    "claims": [
        {
            "claim_id": "methodcmp-beta-claim-1",
            "type": "methods",
            "statement": "Intervention: MCT oil. Comparator: Standard care. Primary outcome: MMSE score. Timepoint: week 24.",
            "sample_size": 32,
            "confidence": 0.85,
            "limitations": [],
            "evidence_spans": [
                {
                    "page": 2,
                    "raw_text": "Intervention: MCT oil. Comparator: Standard care. Primary outcome: MMSE score. Timepoint: week 24. Sample size: 32.",
                    "quote": "Intervention: MCT oil. Comparator: Standard care. Primary outcome: MMSE score. Timepoint: week 24. Sample size: 32.",
                    "rationale": "Seeded explicit method-comparison fixture for beta.",
                    "highlight_source": "text_match",
                }
            ],
        }
    ],
}
(methodcmp_beta_artifact_dir / "claimset.resolved.json").write_text(
    json.dumps(methodcmp_beta_claimset_payload, indent=2),
    encoding="utf-8",
)
(methodcmp_beta_artifact_dir / "claimset.json").write_text(
    json.dumps(methodcmp_beta_claimset_payload, indent=2),
    encoding="utf-8",
)
(methodcmp_beta_artifact_dir / "run_meta.json").write_text(
    json.dumps({"paper_id": methodcmp_beta_paper_id, "run_id": methodcmp_beta_run_id, "status": "completed"}, indent=2),
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
        job_id, run_id, paper_id, persona_id, reasoning_persona, profile_id, run_verify, clean_reindex,
        status, progress, stage, created_at, started_at, finished_at,
        artifact_dir, log_path, error_code, error_message
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'), ?, ?, NULL, NULL)
    """,
    (
        job_id,
        run_id,
        paper_id,
        "default",
        "researcher",
        "coglab",
        1,
        0,
        "completed",
        100,
        "completed",
        str(artifact_dir.resolve()),
        str(log_path.resolve()),
    ),
)
conn.execute(
    """
    INSERT OR REPLACE INTO user_actions (
        action_id, ts, paper_id, action_type, source, payload_json
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    (
        "action-e2e-primary-001",
        "2026-02-26T13:00:00Z",
        paper_id,
        "deepread_enqueued",
        "ui",
        json.dumps({"run_id": run_id}),
    ),
)

parser_fallback_log_path = log_dir / f"{parser_fallback_job_id}.log"
parser_fallback_log_lines = [
    {
        "timestamp": "2026-03-24T09:00:01Z",
        "stage": "ingest",
        "progress": 25,
        "level": "INFO",
        "message": "Requested parser override: docling",
    },
    {
        "timestamp": "2026-03-24T09:00:02Z",
        "stage": "ingest",
        "progress": 55,
        "level": "INFO",
        "message": "Resolved runtime backend: fitz_pdfplumber",
    },
    {
        "timestamp": "2026-03-24T09:00:03Z",
        "stage": "completed",
        "progress": 100,
        "level": "INFO",
        "message": "Parser fallback fixture completed",
    },
]
parser_fallback_log_path.write_text(
    "\n".join(json.dumps(line) for line in parser_fallback_log_lines) + "\n",
    encoding="utf-8",
)

conn.execute(
    """
    INSERT OR REPLACE INTO jobs (
        job_id, run_id, paper_id, persona_id, reasoning_persona, profile_id, run_verify, clean_reindex,
        status, progress, stage, created_at, started_at, finished_at,
        artifact_dir, log_path, error_code, error_message
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'), ?, ?, NULL, NULL)
    """,
    (
        parser_fallback_job_id,
        parser_fallback_run_id,
        parser_fallback_paper_id,
        "default",
        "researcher",
        "parser_pilot",
        0,
        0,
        "completed",
        100,
        "completed",
        str(parser_fallback_artifact_dir.resolve()),
        str(parser_fallback_log_path.resolve()),
    ),
)
conn.execute(
    """
    INSERT OR REPLACE INTO execution_runs (
        run_id, paper_id, trigger_source, pipeline_profile, status, created_at, started_at, finished_at,
        params_json, metrics_json
    )
    VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'), ?, ?)
    """,
    (
        parser_fallback_run_id,
        parser_fallback_paper_id,
        "ui",
        "deepread",
        "completed",
        json.dumps(
            {
                "persona_id": "default",
                "reasoning_persona": "researcher",
                "profile_id": "parser_pilot",
                "parser_backend": "docling",
            }
        ),
        json.dumps({"requested_parser_backend": "docling", "resolved_parser_backend": "fitz_pdfplumber"}),
    ),
)

content_review_paper_id = "paper-e2e-content-review-001"
content_review_run_id = "run_e2e_content_review_001"
content_review_job_id = "job-e2e-content-review-001"
content_review_artifact_dir = root / "storage" / "artifacts" / content_review_paper_id / content_review_run_id
content_review_artifact_dir.mkdir(parents=True, exist_ok=True)

content_review_claimset_payload = copy.deepcopy(claimset_payload)
content_review_claimset_payload["doc_id"] = content_review_paper_id
content_review_claimset_payload["claims"][0]["statement"] = "A flagged content review cue should still be distinct from artifact health."
content_review_claimset_payload["claims"][1]["statement"] = "Secondary flagged content review cue remains compatible with a healthy stats snapshot."

content_review_document_payload = copy.deepcopy(document_payload)
content_review_document_payload["doc_id"] = content_review_paper_id

content_review_stats_payload = copy.deepcopy(stats_payload)
content_review_stats_payload["doc_id"] = content_review_paper_id
content_review_stats_payload["run_id"] = content_review_run_id
content_review_stats_payload["checks"][0]["notes"] = "Artifact health remains healthy even when content review flags exist."

content_review_bootstrap_payload = copy.deepcopy(bootstrap_payload)

(content_review_artifact_dir / "claimset.resolved.json").write_text(
    json.dumps(content_review_claimset_payload, indent=2),
    encoding="utf-8",
)
(content_review_artifact_dir / "claimset.json").write_text(
    json.dumps(content_review_claimset_payload, indent=2),
    encoding="utf-8",
)
(content_review_artifact_dir / "document_artifact.json").write_text(
    json.dumps(content_review_document_payload, indent=2),
    encoding="utf-8",
)
(content_review_artifact_dir / "stats_report.json").write_text(
    json.dumps(content_review_stats_payload, indent=2),
    encoding="utf-8",
)
(content_review_artifact_dir / "bootstrap_meta.json").write_text(
    json.dumps(content_review_bootstrap_payload, indent=2),
    encoding="utf-8",
)
(content_review_artifact_dir / "run_meta.json").write_text(
    json.dumps({"paper_id": content_review_paper_id, "run_id": content_review_run_id, "status": "completed"}, indent=2),
    encoding="utf-8",
)

content_review_log_path = log_dir / f"{content_review_job_id}.log"
content_review_log_lines = [
    {
        "timestamp": "2026-02-26T13:01:01Z",
        "stage": "ingest",
        "progress": 25,
        "level": "INFO",
        "message": "Loaded paper for content review fixture",
    },
    {
        "timestamp": "2026-02-26T13:01:02Z",
        "stage": "read",
        "progress": 70,
        "level": "INFO",
        "message": "Detected 2 content review flags",
    },
    {
        "timestamp": "2026-02-26T13:01:03Z",
        "stage": "completed",
        "progress": 100,
        "level": "INFO",
        "message": "Healthy artifact fixture completed",
    },
]
content_review_log_path.write_text(
    "\n".join(json.dumps(line) for line in content_review_log_lines) + "\n",
    encoding="utf-8",
)

conn.execute(
    """
    INSERT OR REPLACE INTO jobs (
        job_id, run_id, paper_id, persona_id, reasoning_persona, profile_id, run_verify, clean_reindex,
        status, progress, stage, created_at, started_at, finished_at,
        artifact_dir, log_path, error_code, error_message
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'), ?, ?, NULL, NULL)
    """,
    (
        content_review_job_id,
        content_review_run_id,
        content_review_paper_id,
        "default",
        "extractor_reviewer",
        "metabolism_review",
        1,
        0,
        "completed",
        100,
        "completed",
        str(content_review_artifact_dir.resolve()),
        str(content_review_log_path.resolve()),
    ),
)

content_review_unavailable_paper_id = "paper-e2e-content-review-unavailable-001"
content_review_unavailable_run_id = "run_e2e_content_review_unavailable_001"
content_review_unavailable_job_id = "job-e2e-content-review-unavailable-001"
content_review_unavailable_artifact_dir = root / "storage" / "artifacts" / content_review_unavailable_paper_id / content_review_unavailable_run_id
content_review_unavailable_artifact_dir.mkdir(parents=True, exist_ok=True)

content_review_unavailable_claimset_payload = copy.deepcopy(claimset_payload)
content_review_unavailable_claimset_payload["doc_id"] = content_review_unavailable_paper_id
content_review_unavailable_claimset_payload["claims"][0]["statement"] = "Content review availability should stay distinct from a healthy artifact state."
content_review_unavailable_claimset_payload["claims"][1]["statement"] = "A healthy stats snapshot can coexist with unavailable content review metadata."

content_review_unavailable_document_payload = copy.deepcopy(document_payload)
content_review_unavailable_document_payload["doc_id"] = content_review_unavailable_paper_id

content_review_unavailable_stats_payload = copy.deepcopy(stats_payload)
content_review_unavailable_stats_payload["paper_id"] = content_review_unavailable_paper_id

content_review_unavailable_bootstrap_payload = copy.deepcopy(bootstrap_payload)
content_review_unavailable_bootstrap_payload.update(
    {
        "paper_id": content_review_unavailable_paper_id,
        "run_id": content_review_unavailable_run_id,
        "job_id": content_review_unavailable_job_id,
    }
)

(content_review_unavailable_artifact_dir / "claimset.resolved.json").write_text(
    json.dumps(content_review_unavailable_claimset_payload, indent=2),
    encoding="utf-8",
)
(content_review_unavailable_artifact_dir / "claimset.json").write_text(
    json.dumps(content_review_unavailable_claimset_payload, indent=2),
    encoding="utf-8",
)
(content_review_unavailable_artifact_dir / "document_artifact.json").write_text(
    json.dumps(content_review_unavailable_document_payload, indent=2),
    encoding="utf-8",
)
(content_review_unavailable_artifact_dir / "stats_report.json").write_text(
    json.dumps(content_review_unavailable_stats_payload, indent=2),
    encoding="utf-8",
)
(content_review_unavailable_artifact_dir / "bootstrap_meta.json").write_text(
    json.dumps(content_review_unavailable_bootstrap_payload, indent=2),
    encoding="utf-8",
)
(content_review_unavailable_artifact_dir / "run_meta.json").write_text(
    json.dumps(
        {
            "paper_id": content_review_unavailable_paper_id,
            "run_id": content_review_unavailable_run_id,
            "status": "completed",
        },
        indent=2,
    ),
    encoding="utf-8",
)

content_review_unavailable_log_path = log_dir / f"{content_review_unavailable_job_id}.log"
content_review_unavailable_log_path.write_text(
    "\n".join(json.dumps(line) for line in log_lines) + "\n",
    encoding="utf-8",
)

conn.execute(
    """
    INSERT OR REPLACE INTO jobs (
        job_id, run_id, paper_id, persona_id, reasoning_persona, profile_id, run_verify, clean_reindex,
        status, progress, stage, created_at, started_at, finished_at,
        artifact_dir, log_path, error_code, error_message
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'), ?, ?, NULL, NULL)
    """,
    (
        content_review_unavailable_job_id,
        content_review_unavailable_run_id,
        content_review_unavailable_paper_id,
        "default",
        "extractor_reviewer",
        "metabolism_review",
        1,
        0,
        "completed",
        100,
        "completed",
        str(content_review_unavailable_artifact_dir.resolve()),
        str(content_review_unavailable_log_path.resolve()),
    ),
)

repair_paper_id = "paper-e2e-repair-001"
repair_run_id = "run_e2e_repair_001"
repair_job_id = "job-e2e-repair-001"
repair_artifact_dir = root / "storage" / "artifacts" / repair_paper_id / repair_run_id
repair_artifact_dir.mkdir(parents=True, exist_ok=True)

repair_claimset_payload = {
    "doc_id": repair_paper_id,
    "claims": [
        {
            "claim_id": "repair-claim-1",
            "type": "efficacy",
            "statement": "The intervention improved biomarker alignment during the follow-up window.",
            "confidence": 0.84,
            "limitations": [],
            "evidence_spans": [
                {
                    "page": 0,
                    "raw_text": "Biomarker alignment improved during the follow-up window.",
                    "quote": "Biomarker alignment improved during the follow-up window.",
                    "rationale": "Primary efficacy statement for repair fixture.",
                    "bbox_pct": {"left": 12, "top": 18, "width": 42, "height": 18},
                    "highlight_source": "bbox",
                }
            ],
        }
    ],
}

repair_bootstrap_payload = {
    "artifact_document_written": False,
    "artifact_index_written": False,
    "artifact_claimset_written": True,
    "artifact_stats_written": False,
    "claimset_readiness": "ready",
    "claimset_ready": True,
    "claimset_claim_count": 1,
    "claimset_readiness_reason": "claims_present",
    "claimset_readiness_badge": "READY",
    "claimset_ops_action": "manual_review_queued",
    "claimset_ops_alert": True,
    "claimset_ops_note": "stats_missing",
}

(repair_artifact_dir / "claimset.resolved.json").write_text(json.dumps(repair_claimset_payload, indent=2), encoding="utf-8")
(repair_artifact_dir / "claimset.json").write_text(json.dumps(repair_claimset_payload, indent=2), encoding="utf-8")
(repair_artifact_dir / "bootstrap_meta.json").write_text(json.dumps(repair_bootstrap_payload, indent=2), encoding="utf-8")
(repair_artifact_dir / "run_meta.json").write_text(
    json.dumps({"paper_id": repair_paper_id, "run_id": repair_run_id, "status": "completed"}, indent=2),
    encoding="utf-8",
)
repair_stats_path = repair_artifact_dir / "stats_report.json"
if repair_stats_path.exists():
    repair_stats_path.unlink()

repair_log_path = log_dir / f"{repair_job_id}.log"
repair_log_lines = [
    {
        "timestamp": "2026-02-26T13:05:01Z",
        "stage": "read",
        "progress": 70,
        "level": "INFO",
        "message": "Claimset ready; stats artifact missing",
    },
    {
        "timestamp": "2026-02-26T13:05:02Z",
        "stage": "completed",
        "progress": 100,
        "level": "INFO",
        "message": "Repair fixture loaded",
    },
]
repair_log_path.write_text("\n".join(json.dumps(line) for line in repair_log_lines) + "\n", encoding="utf-8")

conn.execute(
    """
    INSERT OR REPLACE INTO jobs (
        job_id, run_id, paper_id, persona_id, reasoning_persona, profile_id, run_verify, clean_reindex,
        status, progress, stage, created_at, started_at, finished_at,
        artifact_dir, log_path, error_code, error_message
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'), ?, ?, NULL, NULL)
    """,
    (
        repair_job_id,
        repair_run_id,
        repair_paper_id,
        "default",
        "extractor_reviewer",
        "repair_ops",
        0,
        0,
        "completed",
        100,
        "completed",
        str(repair_artifact_dir.resolve()),
        str(repair_log_path.resolve()),
    ),
)
rebuild_paper_id = "paper-e2e-rebuild-001"
rebuild_run_id = "run_e2e_rebuild_001"
rebuild_job_id = "job-e2e-rebuild-001"
rebuild_artifact_dir = root / "storage" / "artifacts" / rebuild_paper_id / rebuild_run_id
rebuild_artifact_dir.mkdir(parents=True, exist_ok=True)

rebuild_claimset_payload = {
    "doc_id": rebuild_paper_id,
    "claims": [
        {
            "claim_id": "rebuild-claim-1",
            "type": "efficacy",
            "statement": "The current snapshot should be regenerated from the latest claimset fallback.",
            "confidence": 0.81,
            "limitations": [],
            "evidence_spans": [
                {
                    "page": 0,
                    "raw_text": "The latest claimset is newer than the existing stats snapshot.",
                    "quote": "The latest claimset is newer than the existing stats snapshot.",
                    "rationale": "Primary evidence for the rebuild fixture.",
                    "bbox_pct": {"left": 22, "top": 28, "width": 36, "height": 14},
                    "highlight_source": "bbox",
                }
            ],
        }
    ],
}

rebuild_bootstrap_payload = {
    "artifact_document_written": False,
    "artifact_index_written": False,
    "artifact_claimset_written": True,
    "artifact_stats_written": True,
    "claimset_readiness": "ready",
    "claimset_ready": True,
    "claimset_claim_count": 1,
    "claimset_readiness_reason": "claims_present",
    "claimset_readiness_badge": "READY",
    "claimset_ops_action": "manual_review_queued",
    "claimset_ops_alert": False,
    "claimset_ops_note": "stats_present",
}

rebuild_stats_payload = {
    "doc_id": rebuild_paper_id,
    "run_id": rebuild_run_id,
    "input_tables_used": [],
    "checks": [
        {
            "check_id": "legacy-stats-check",
            "hypothesis": "Legacy snapshot still points to the earlier stats bundle.",
            "test_type": "legacy-check",
            "method": "legacy_method",
            "reported_stat": None,
            "reported_df_tuple": None,
            "df_parse_status": "unknown",
            "reported_p": None,
            "alpha_used": 0.05,
            "computed_p": None,
            "decision_error": False,
            "confidence_interval_consistency": None,
            "code": "# legacy snapshot",
            "outputs": "legacy snapshot",
            "verdict": "verified",
            "notes": "LEGACY_STATS_FIXTURE",
            "evidence": [
                {
                    "page": 0,
                    "raw_text": "Legacy stats snapshot still exists.",
                    "quote": "Legacy stats snapshot still exists.",
                    "rationale": "Preloaded stats fixture for rebuild coverage.",
                    "section": "results",
                    "highlight_source": "text_match",
                }
            ],
        }
    ],
}

(rebuild_artifact_dir / "claimset.resolved.json").write_text(json.dumps(rebuild_claimset_payload, indent=2), encoding="utf-8")
(rebuild_artifact_dir / "claimset.json").write_text(json.dumps(rebuild_claimset_payload, indent=2), encoding="utf-8")
(rebuild_artifact_dir / "bootstrap_meta.json").write_text(json.dumps(rebuild_bootstrap_payload, indent=2), encoding="utf-8")
(rebuild_artifact_dir / "run_meta.json").write_text(
    json.dumps({"paper_id": rebuild_paper_id, "run_id": rebuild_run_id, "status": "completed"}, indent=2),
    encoding="utf-8",
)
(rebuild_artifact_dir / "stats_report.json").write_text(json.dumps(rebuild_stats_payload, indent=2), encoding="utf-8")

rebuild_log_path = log_dir / f"{rebuild_job_id}.log"
rebuild_log_lines = [
    {
        "timestamp": "2026-02-26T13:06:01Z",
        "stage": "verify",
        "progress": 88,
        "level": "INFO",
        "message": "Legacy stats snapshot detected",
    },
    {
        "timestamp": "2026-02-26T13:06:02Z",
        "stage": "completed",
        "progress": 100,
        "level": "INFO",
        "message": "Rebuild fixture loaded",
    },
]
rebuild_log_path.write_text("\n".join(json.dumps(line) for line in rebuild_log_lines) + "\n", encoding="utf-8")

conn.execute(
    """
    INSERT OR REPLACE INTO jobs (
        job_id, run_id, paper_id, persona_id, reasoning_persona, profile_id, run_verify, clean_reindex,
        status, progress, stage, created_at, started_at, finished_at,
        artifact_dir, log_path, error_code, error_message
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'), ?, ?, NULL, NULL)
    """,
    (
        rebuild_job_id,
        rebuild_run_id,
        rebuild_paper_id,
        "default",
        "extractor_reviewer",
        "repair_ops",
        0,
        0,
        "completed",
        100,
        "completed",
        str(rebuild_artifact_dir.resolve()),
        str(rebuild_log_path.resolve()),
    ),
)

list_missing_paper_id = "paper-e2e-list-missing-stats-001"
list_missing_run_id = "run_e2e_list_missing_stats_001"
list_missing_artifact_dir = root / "storage" / "artifacts" / list_missing_paper_id / list_missing_run_id
list_missing_artifact_dir.mkdir(parents=True, exist_ok=True)

list_missing_claimset_payload = {
    "doc_id": list_missing_paper_id,
    "claims": [
        {
            "claim_id": "list-missing-claim-1",
            "type": "efficacy",
            "statement": "List fixture has ClaimSet data but no stats artifact yet.",
            "confidence": 0.78,
            "limitations": [],
            "evidence_spans": [
                {
                    "page": 0,
                    "raw_text": "ClaimSet exists but Stats Snapshot has not been rebuilt yet.",
                    "quote": "ClaimSet exists but Stats Snapshot has not been rebuilt yet.",
                    "rationale": "Keeps the list fixture in action-needed state.",
                    "bbox_pct": {"left": 18, "top": 24, "width": 38, "height": 16},
                    "highlight_source": "bbox",
                }
            ],
        }
    ],
}

(list_missing_artifact_dir / "claimset.resolved.json").write_text(
    json.dumps(list_missing_claimset_payload, indent=2),
    encoding="utf-8",
)
(list_missing_artifact_dir / "claimset.json").write_text(
    json.dumps(list_missing_claimset_payload, indent=2),
    encoding="utf-8",
)

conn.commit()
conn.close()
PY

if [[ "${E2E_BOOTSTRAP_ONLY:-0}" == "1" ]]; then
  echo "E2E backend runtime bootstrap completed."
  exit 0
fi

WORKER_PID=""
cleanup() {
  if [[ -n "${WORKER_PID}" ]]; then
    kill "${WORKER_PID}" >/dev/null 2>&1 || true
    wait "${WORKER_PID}" >/dev/null 2>&1 || true
  fi
}

if [[ "${E2E_ENABLE_FAKE_WORKER:-0}" == "1" ]]; then
  trap cleanup EXIT INT TERM
  "${PYTHON_BIN}" frontend/scripts/run_fake_worker_for_e2e.py &
  WORKER_PID="$!"
fi

"${PYTHON_BIN}" -m uvicorn backend.main:app --host 127.0.0.1 --port "${BACKEND_PORT}"
