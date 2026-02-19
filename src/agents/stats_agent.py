import json
import logging
from typing import TypedDict, List, Optional, Any, Dict
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

from src.schemas.agent_artifacts import (
    DocumentArtifact, ClaimSet, StatsReport, StatCheckEntry, VerificationStatus,
    TableData, EvidenceSpan
)
from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.contracts.artifact_views import get_artifact_header
from src.sandbox.docker_runner import DockerSandbox
from src.agents.adapter import OllamaModelAdapter
from src.config import load_config

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 1. State Definition
# -----------------------------------------------------------------------------

class StatsAgentState(TypedDict):
    # Inputs
    job_id: str
    doc: DocumentArtifact | DocumentArtifactV2
    claims: ClaimSet
    
    # Internal State
    dataframes_code: str       # Pandas code reconstructing tables
    extraction_result: List[Dict] # Extracted stats from text (JSON)
    verification_plan: str     # Plan text
    python_code: str           # Generated verification code
    execution_output: str      # Stdout/Stderr from Docker
    execution_error: Optional[str]
    retry_count: int
    
    # Outputs
    final_report: Optional[StatsReport]

# -----------------------------------------------------------------------------
# 2. Agent Class
# -----------------------------------------------------------------------------

class StatsVerificationAgent:
    def __init__(self):
        self.config = load_config()
        self.model = OllamaModelAdapter(model_name="llama3:latest") # Or from config
        self.workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(StatsAgentState)
        
        # Add Nodes
        workflow.add_node("parse_tables", self.node_parse_tables)
        workflow.add_node("extract_stats", self.node_extract_stats)
        workflow.add_node("plan_verification", self.node_plan_verification)
        workflow.add_node("generate_code", self.node_generate_code)
        workflow.add_node("execute_sandbox", self.node_execute_sandbox)
        workflow.add_node("reflect_analyze", self.node_reflect_analyze)
        
        # Add Edges
        workflow.set_entry_point("parse_tables")
        workflow.add_edge("parse_tables", "extract_stats")
        workflow.add_edge("extract_stats", "plan_verification")
        workflow.add_edge("plan_verification", "generate_code")
        workflow.add_edge("generate_code", "execute_sandbox")
        workflow.add_edge("execute_sandbox", "reflect_analyze")
        
        # Conditional Edge from Reflect: Retry or End
        workflow.add_conditional_edges(
            "reflect_analyze",
            self.should_retry,
            {
                "retry": "generate_code",
                "end": END
            }
        )
        
        return workflow.compile()

    def run(self, job_id: str, doc: DocumentArtifact | DocumentArtifactV2, claims: ClaimSet) -> StatsReport:
        """Run the verification agent."""
        initial_state = StatsAgentState(
            job_id=job_id,
            doc=doc,
            claims=claims,
            dataframes_code="",
            extraction_result=[],
            verification_plan="",
            python_code="",
            execution_output="",
            execution_error=None,
            retry_count=0,
            final_report=None
        )
        
        final_state = self.workflow.invoke(initial_state)
        return final_state.get("final_report")

    # -------------------------------------------------------------------------
    # Node Implementations
    # -------------------------------------------------------------------------

    def node_parse_tables(self, state: StatsAgentState) -> StatsAgentState:
        """Convert tables to Pandas DataFrame reconstruction code."""
        tables = state["doc"].tables
        logger.info(f"📊 [Node: Parse] Converting {len(tables)} tables to Pandas code...")
        code_lines = ["import pandas as pd", "import numpy as np", ""]
        
        for t in tables:
            # Simple list-of-lists to DataFrame conversion
            # Handle potential header issues in a real impl, simpler here.
            try:
                if not t.data:
                    continue
                headers = t.data[0]
                rows = t.data[1:]
                # Sanitize strings
                import json
                headers_json = json.dumps(headers)
                rows_json = json.dumps(rows)
                
                code_lines.append(f"# Table {t.table_id}: {t.caption[:50]}...")
                code_lines.append(f"columns_{t.table_id} = {headers_json}")
                code_lines.append(f"data_{t.table_id} = {rows_json}")
                code_lines.append(f"df_{t.table_id} = pd.DataFrame(data_{t.table_id}, columns=columns_{t.table_id})")
                code_lines.append("")
            except Exception as e:
                logger.warning(f"Failed to parse table {t.table_id}: {e}")
        
        state["dataframes_code"] = "\n".join(code_lines)
        return state

    def node_extract_stats(self, state: StatsAgentState) -> StatsAgentState:
        """Extract reported stats from claims to verify."""
        logger.info(f"🔍 [Node: Extract] Identifying statistical claims from text...")
        # Using LLM to extract structured stats from the text of claims
        claims_text = "\n".join([f"- {c.statement}" for c in state["claims"].claims])
        
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
        response = self.model.generate(prompt, format="json")
        try:
            state["extraction_result"] = json.loads(response.text)
            logger.info(f"   Model extracted {len(state['extraction_result'])} potential checks.")
        except:
            state["extraction_result"] = []
            
        return state

    def node_plan_verification(self, state: StatsAgentState) -> StatsAgentState:
        """Plan which tests to run based on extracted stats and available tables."""
        logger.info(f"🧠 [Node: Plan] Formulating verification strategy...")
        # LLM Reasoning: Can we verify this claim using df_table_X?
        prompt = f"""
        You are a Statistical Verification Planner.
        
        Available Dataframes (Code):
        {state['dataframes_code']}
        
        Extracted Claims:
        {json.dumps(state['extraction_result'], indent=2)}
        
        Task: Create a plan to verify these claims using the dataframes. 
        If data is missing for a claim, note it as UNVERIFIABLE.
        Only plan for claims where data seems present in the tables.
        
        Output formatted text plan.
        """
        response = self.model.generate(prompt)
        state["verification_plan"] = response.text
        return state

    def node_generate_code(self, state: StatsAgentState) -> StatsAgentState:
        """Generate Python code to execute the plan."""
        logger.info(f"💻 [Node: Code] Generating Python verification script...")
        prompt = f"""
        generate a Python script to perform the statistical verification.
        
        Context:
        - We have `import pandas as pd`, `import numpy as np`.
        - We have the following DataFrame definitions (I will prepend them).
        
        Data Loading Code:
        {state['dataframes_code']}
        
        Plan:
        {state['verification_plan']}
        
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
        response = self.model.generate(prompt)
        # simplistic extraction of code block
        code = response.text
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[0]
            
        state["python_code"] = state["dataframes_code"] + "\n\n" + code
        return state

    def node_execute_sandbox(self, state: StatsAgentState) -> StatsAgentState:
        """Run code in Docker."""
        logger.info(f"📦 [Node: Schema] Spinning up Docker MicroVM...")
        sandbox = DockerSandbox(job_id=state["job_id"], work_dir=f"storage/sandbox/{state['job_id']}")
        exit_code, stdout, stderr = sandbox.run_code(state["python_code"])
        
        logger.info(f"   Execution finished (Exit Code: {exit_code})")
        state["execution_output"] = stdout + "\n" + stderr
        if exit_code != 0:
            state["execution_error"] = f"Exit Code {exit_code}\n{stderr}"
        else:
            state["execution_error"] = None
            
        return state

    def node_reflect_analyze(self, state: StatsAgentState) -> StatsAgentState:
        """Analyze Sandbox output and generate final report."""
        output = state["execution_output"]
        
        # If error and retries left, we might retry.
        # For MVP, we'll try to parse results or mark as failed.
        
        # Parse the JSON output from the script
        # This assumes the script printed valid JSON at the end.
        # We might use an LLM to parse the messy stdout if needed.
        
        checks = []
        
        # Simple parsing logic (or use LLM to interpret output)
        prompt = f"""
        Analyze the execution output of the verification script.
        
        Output:
        {output}
        
        Error (if any):
        {state['execution_error']}
        
        Construct a list of StatCheckEntry objects (JSON).
        Determine the 'verdict' (verified, partially_verified, inconsistent, unverifiable).
        """
        response = self.model.generate(prompt, format="json")
        try:
            entries_data = json.loads(response.text)
            # Map back to Pydantic models
            if isinstance(entries_data, list):
                for e in entries_data:
                    # Sanitize & Inject Context
                    if "verdict" not in e: e["verdict"] = "unverifiable"
                    # Inject code/output if missing (LLM usually omits these big fields)
                    if "code" not in e: e["code"] = state["python_code"] if state["python_code"] else "N/A"
                    if "outputs" not in e: e["outputs"] = state["execution_output"] if state["execution_output"] else "N/A"
                    
                    checks.append(StatCheckEntry(**e))
            elif isinstance(entries_data, dict) and "checks" in entries_data:
                 for e in entries_data["checks"]:
                    # Sanitize & Inject Context
                    if "verdict" not in e: e["verdict"] = "unverifiable"
                    if "code" not in e: e["code"] = state["python_code"] if state["python_code"] else "N/A"
                    if "outputs" not in e: e["outputs"] = state["execution_output"] if state["execution_output"] else "N/A"
                    
                    checks.append(StatCheckEntry(**e))
        except Exception as e:
            logger.error(f"Failed to parse reflexion: {e}")
            # Fallback report
            
        report = StatsReport(
            doc_id=get_artifact_header(state["doc"]).doc_id,
            run_id=state["job_id"], # reusing job_id as run_id for now
            checks=checks
        )
        
        state["final_report"] = report
        state["retry_count"] += 1
        return state

    def should_retry(self, state: StatsAgentState) -> str:
        """Decide whether to retry code generation."""
        if state["execution_error"] and state["retry_count"] < 2:
            return "retry"
        return "end"
