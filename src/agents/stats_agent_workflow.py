from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from src.contracts.artifact_views import get_artifact_header
from src.schemas.agent_artifacts import (
    ClaimSet,
    DocumentArtifact,
    StatCheckEntry,
    StatsReport,
)
from src.contracts.document_artifact_v2 import DocumentArtifactV2

logger = logging.getLogger(__name__)


def build_dataframes_code(tables: list[Any]) -> str:
    code_lines = ["import pandas as pd", "import numpy as np", ""]

    for table in tables:
        try:
            if not table.data:
                continue
            headers = table.data[0]
            rows = table.data[1:]
            headers_json = json.dumps(headers)
            rows_json = json.dumps(rows)

            code_lines.append(f"# Table {table.table_id}: {table.caption[:50]}...")
            code_lines.append(f"columns_{table.table_id} = {headers_json}")
            code_lines.append(f"data_{table.table_id} = {rows_json}")
            code_lines.append(
                f"df_{table.table_id} = pd.DataFrame(data_{table.table_id}, columns=columns_{table.table_id})"
            )
            code_lines.append("")
        except Exception as exc:
            logger.warning(f"Failed to parse table {table.table_id}: {exc}")

    return "\n".join(code_lines)


def extract_stats_via_model(model: Any, claims: ClaimSet) -> list[dict]:
    claims_text = "\n".join([f"- {claim.statement}" for claim in claims.claims])

    prompt = f"""
        Extract statistical claims from the following list. 
        For each claim that contains statistical results (p-values, test names, sample sizes, means, SDs), extract them into a JSON list.
        
        Claims:
        {claims_text}
        
        Output JSON format:
        [
          {{
            "claim_text": "...",
            "test_type": "t-test/ANOVA/etc",
            "reported_p": "0.05",
            "variables": ["group A", "group B"],
            "values": {{ "mean_a": 10.2, "sd_a": 1.1, ... }}
          }}
        ]
        """
    response = model.generate(prompt, format="json")
    try:
        return json.loads(response.text)
    except Exception:
        return []


def plan_verification_via_model(model: Any, dataframes_code: str, extraction_result: list[dict]) -> str:
    prompt = f"""
        You are a Statistical Verification Planner.
        
        Available Dataframes (Code):
        {dataframes_code}
        
        Extracted Claims:
        {json.dumps(extraction_result, indent=2)}
        
        Task: Create a plan to verify these claims using the dataframes. 
        If data is missing for a claim, note it as UNVERIFIABLE.
        Only plan for claims where data seems present in the tables.
        
        Output formatted text plan.
        """
    response = model.generate(prompt)
    return response.text


def generate_python_code_via_model(model: Any, dataframes_code: str, verification_plan: str) -> str:
    prompt = f"""
        generate a Python script to perform the statistical verification.
        
        Context:
        - We have `import pandas as pd`, `import numpy as np`.
        - We have the following DataFrame definitions (I will prepend them).
        
        Data Loading Code:
        {dataframes_code}
        
        Plan:
        {verification_plan}
        
        Requirements:
        1. Perform the statistical tests (ttest_ind, etc.) using scipy.stats or statsmodels.
        2. Print the results in a structured JSON format at the end.
        3. The JSON should be printed to stdout.
        4. Handle NaN or type conversions carefully (e.g. "10.2 (±1.1)" string parsing).
        
        Structure the output as a dictionary keyed by 'claim_id' or verification item.
        Example Output:
        {{
           "check_1": {{ "computed_p": 0.04, "verdict": "consistent" }},
           ...
        }}
        """
    response = model.generate(prompt)
    code = response.text
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0]
    elif "```" in code:
        code = code.split("```")[0]
    return dataframes_code + "\n\n" + code


def run_sandbox_code(sandbox_cls: Any, job_id: str, python_code: str) -> tuple[str, Optional[str]]:
    sandbox = sandbox_cls(job_id=job_id, work_dir=f"storage/sandbox/{job_id}")
    exit_code, stdout, stderr = sandbox.run_code(python_code)

    output = stdout + "\n" + stderr
    if exit_code != 0:
        return output, f"Exit Code {exit_code}\n{stderr}"
    return output, None


def parse_reflection_entries(
    model: Any,
    execution_output: str,
    execution_error: Optional[str],
    python_code: str,
) -> list[StatCheckEntry]:
    prompt = f"""
        Analyze the execution output of the verification script.
        
        Output:
        {execution_output}
        
        Error (if any):
        {execution_error}
        
        Construct a list of StatCheckEntry objects (JSON).
        Determine the 'verdict' (verified, partially_verified, inconsistent, unverifiable).
        """
    response = model.generate(prompt, format="json")

    checks: list[StatCheckEntry] = []
    try:
        entries_data = json.loads(response.text)
        if isinstance(entries_data, list):
            entries_iter = entries_data
        elif isinstance(entries_data, dict) and "checks" in entries_data:
            entries_iter = entries_data["checks"]
        else:
            entries_iter = []

        for entry in entries_iter:
            if "verdict" not in entry:
                entry["verdict"] = "unverifiable"
            if "code" not in entry:
                entry["code"] = python_code if python_code else "N/A"
            if "outputs" not in entry:
                entry["outputs"] = execution_output if execution_output else "N/A"
            checks.append(StatCheckEntry(**entry))
    except Exception as exc:
        logger.error(f"Failed to parse reflexion: {exc}")
    return checks


def build_stats_report(
    doc: DocumentArtifact | DocumentArtifactV2,
    job_id: str,
    checks: list[StatCheckEntry],
) -> StatsReport:
    return StatsReport(
        doc_id=get_artifact_header(doc).doc_id,
        run_id=job_id,
        checks=checks,
    )


def should_retry_from_state(execution_error: Optional[str], retry_count: int) -> str:
    if execution_error and retry_count < 2:
        return "retry"
    return "end"
