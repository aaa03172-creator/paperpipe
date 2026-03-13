
import logging
try:
    from effgen import Agent
    from effgen.core.agent import AgentConfig
    from effgen.tools.builtin import Retrieval, PythonREPL
except ImportError:
    Agent = None
    AgentConfig = None
    # Dummy classes for import error handling
    class Retrieval: 
        def __init__(self, **kwargs): pass
    class PythonREPL:
         def __init__(self, **kwargs): pass

from src.config import load_config
from src.agents.adapter import OllamaModelAdapter

logger = logging.getLogger(__name__)

class DeepReadAgent:
    def __init__(self):
        self.config = load_config()
        self.agent = None
        
        if not self.config.agents.enabled:
            logger.warning("Agents are disabled in config.")
            return

        if Agent is None:
            logger.error("effgen library not found. Please run 'pip install effgen'.")
            return
            
        self._initialize_agent()

    def _initialize_agent(self):
        try:
            # 1. Setup Model Adapter
            # effGen usually expects a loaded model object. 
            # We pass our adapter which mimics a model.
            logger.info(f"Initializing DeepReadAgent with backend: {self.config.agents.backend}")
            model_adapter = OllamaModelAdapter(model_name=self.config.agents.main_model)
            
            # 2. Setup Tools
            tools = []
            if self.config.agents.tools.python_repl:
                tools.append(PythonREPL())
            
            if self.config.agents.tools.retrieval:
                from src.agents.utils import get_retrieval_tool
                retrieval_tool = get_retrieval_tool(self.config, logger)
                if retrieval_tool:
                    tools.append(retrieval_tool)
                
            # 3. Configure Agent
            system_prompt = """You are a highly analytical and rigorous Senior Postdoc researcher in a Biomedical Convergence and Cognitive Science laboratory. Your role is to mentor and assist the Lead Researcher by critically deep-reading papers that have already passed initial triage. 

Your goal is NOT to summarize the paper—the researcher already knows the basic context. Your goal is to dissect the methodology, challenge the findings, and connect the dots.

Follow these strict directives:
1. **Critical Dissection over Summary:** Focus on the 'Gap'. Identify what the authors failed to control, potential confounding variables, and limitations in their experimental models (e.g., specific in-vivo/in-vitro models, behavioral assays).
2. **Data-Driven Skepticism:** Always question the statistics. Use your `PythonREPL` tool to verify P-values, calculate effect sizes, or check if the sample size (N) is adequately powered for the claims made in the Main Figure.
3. **Domain Expertise:** Pay extreme attention to molecular mechanisms (e.g., neurodegeneration, receptor interactions) and their translation to clinical/cognitive outcomes (e.g., behavioral changes, cognitive impairment).
4. **Actionable Insights:** Conclude your analysis by suggesting one concrete, testable hypothesis or next experimental step the Lead Researcher could take based on this paper's flaws or findings.
5. **Format:** Output your findings in concise Markdown. Never use fluffy language. Be direct, professional, and intellectually demanding.
"""
            
            agent_config = AgentConfig(
                name="DeepReader",
                model=model_adapter,
                tools=tools,
                system_prompt=system_prompt
            )
            
            self.agent = Agent(config=agent_config)
            logger.info("DeepReadAgent initialized successfully.")
            
        except Exception as e:
            logger.error(f"Failed to initialize DeepReadAgent: {e}")
            self.agent = None

    def run(self, paper_content: str, paper_meta: dict) -> str:
        """
        Executes the Deep Read task.
        """
        if not self.agent:
            return "❌ Agent not initialized (Check config or dependencies)."
            
        prompt = f"""
Perform a critical Deep Read on this paper:

Title: {paper_meta.get('title')}
Authors: {paper_meta.get('authors')}
published: {paper_meta.get('published')}

Content Snippet:
{paper_content[:5000]}... (truncated)

Task:
1. Identify the core claim and the evidence provided.
2. Critique the methodology (sample size, controls, statistical tests).
3. Check for any logical fallacies or overclaims.
4. Output a report in Markdown format.
"""
        try:
            logger.info(f"🤖 Agent running Deep Read on: {paper_meta.get('title')}")
            result = self.agent.run(prompt)
            return result.output if hasattr(result, 'output') else str(result)
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return f"❌ Agent execution failed: {e}"
