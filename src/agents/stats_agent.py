import logging
from typing import TypedDict, List, Optional, Any, Dict
from langgraph.graph import StateGraph, END

from src.schemas.agent_artifacts import (
    DocumentArtifact,
    ClaimSet,
    StatsReport,
)
from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.sandbox.docker_runner import DockerSandbox
from src.agents.adapter import OllamaModelAdapter
from src.agents.stats_agent_workflow import (
    build_dataframes_code,
    build_stats_report,
    extract_stats_via_model,
    generate_python_code_via_model,
    parse_reflection_entries,
    plan_verification_via_model,
    run_sandbox_code,
    should_retry_from_state,
)
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
        state["dataframes_code"] = build_dataframes_code(tables)
        return state

    def node_extract_stats(self, state: StatsAgentState) -> StatsAgentState:
        """Extract reported stats from claims to verify."""
        logger.info(f"🔍 [Node: Extract] Identifying statistical claims from text...")
        state["extraction_result"] = extract_stats_via_model(self.model, state["claims"])
        logger.info(f"   Model extracted {len(state['extraction_result'])} potential checks.")
            
        return state

    def node_plan_verification(self, state: StatsAgentState) -> StatsAgentState:
        """Plan which tests to run based on extracted stats and available tables."""
        logger.info(f"🧠 [Node: Plan] Formulating verification strategy...")
        state["verification_plan"] = plan_verification_via_model(
            self.model,
            state["dataframes_code"],
            state["extraction_result"],
        )
        return state

    def node_generate_code(self, state: StatsAgentState) -> StatsAgentState:
        """Generate Python code to execute the plan."""
        logger.info(f"💻 [Node: Code] Generating Python verification script...")
        state["python_code"] = generate_python_code_via_model(
            self.model,
            state["dataframes_code"],
            state["verification_plan"],
        )
        return state

    def node_execute_sandbox(self, state: StatsAgentState) -> StatsAgentState:
        """Run code in Docker."""
        logger.info(f"📦 [Node: Schema] Spinning up Docker MicroVM...")
        execution_output, execution_error = run_sandbox_code(
            sandbox_cls=DockerSandbox,
            job_id=state["job_id"],
            python_code=state["python_code"],
        )
        logger.info(
            "   Execution finished (Error: %s)",
            "yes" if execution_error else "no",
        )
        state["execution_output"] = execution_output
        state["execution_error"] = execution_error
            
        return state

    def node_reflect_analyze(self, state: StatsAgentState) -> StatsAgentState:
        """Analyze Sandbox output and generate final report."""
        checks = parse_reflection_entries(
            model=self.model,
            execution_output=state["execution_output"],
            execution_error=state["execution_error"],
            python_code=state["python_code"],
        )
        report = build_stats_report(
            doc=state["doc"],
            job_id=state["job_id"],
            checks=checks,
        )
        state["final_report"] = report
        state["retry_count"] += 1
        return state

    def should_retry(self, state: StatsAgentState) -> str:
        """Decide whether to retry code generation."""
        return should_retry_from_state(
            execution_error=state["execution_error"],
            retry_count=state["retry_count"],
        )
