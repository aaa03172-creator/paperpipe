
import logging
import json
import sys
from typing import Optional, Dict, Any

from src.agents.adapter import OllamaModelAdapter
from src.schemas.agent_artifacts import DocumentArtifact, ClaimSet, ScientificClaim, EvidenceSpan
from src.contracts.document_artifact_v2 import DocumentArtifactV2
from src.contracts.artifact_views import get_artifact_header, iter_text_sections
from effgen.core.agent import Agent, AgentConfig

logger = logging.getLogger(__name__)

class ReaderAgent:
    """
    Agent responsible for critical scientific reading and claim extraction.
    Uses a 'Senior Postdoc' persona and structured JSON output.
    """
    
    def __init__(self, model_name: str = "llama3:latest", persona_hint: Optional[str] = None):
        self.model_name = model_name
        self.adapter = OllamaModelAdapter(model_name=model_name)
        
        # Define strict I/O schema for the model to follow
        self.output_schema = ClaimSet.model_json_schema()
        
        self.system_prompt = """You are a highly analytical and rigorous Senior Postdoc researcher in a Biomedical Convergence and Cognitive Science laboratory. Your role is to mentor and assist the Lead Researcher by critically deep-reading papers. 

Your goal is NOT to summarize the paper. Your goal is to dissect the methodology, challenge the findings, and connect the dots.

Follow these strict directives:
1. **Critical Dissection over Summary:** Focus on the 'Gap'. Identify what the authors failed to control, potential confounding variables, and limitations in their experimental models (e.g., specific in-vivo/in-vitro models, behavioral assays).
2. **Data-Driven Skepticism:** Extract the exact evidence spans. Question if the sample size (N) is adequately powered for the claims made in the results.
3. **Domain Expertise:** Pay extreme attention to molecular mechanisms (e.g., neurodegeneration, receptor interactions) and their translation to clinical/cognitive outcomes.
4. **Actionable Insights:** Conclude your analysis by suggesting one concrete, testable hypothesis or next experimental step based on this paper's flaws or findings.
5. **Format:** You must strictly output your analysis matching the provided JSON schema.
"""
        if persona_hint:
            self.system_prompt += f"\n\nPersona override:\n{persona_hint}\n"

    def analyze(self, doc: DocumentArtifact | DocumentArtifactV2) -> Optional[ClaimSet]:
        """
        Analyzes the DocumentArtifact and returns a ClaimSet.
        """
        header = get_artifact_header(doc)
        # Prepare content from artifact
        # We'll use a simplified representation for the prompt context
        doc_text = f"Title: {header.title}\nAuthors: {', '.join(header.authors)}\n\n"
        
        for section in iter_text_sections(doc):
            doc_text += f"## {section.name.upper()}\n{section.text}\n\n"
            
        # Construct the task prompt
        # Create a concrete example for the model to follow
        example_claim = ScientificClaim(
            claim_id="CLM-001",
            type="efficacy",
            statement="Caffeine increases coding speed by 20%.",
            evidence_spans=[
                EvidenceSpan(
                    page=2,
                    chunk_id="chunk_12", 
                    raw_text="Speed increased by 20% compared to placebo...",
                    quote="Speed increased by 20%",
                    rationale="The results section explicitly states the percentage increase derived from the t-test.",
                    section="Results"
                )
            ],
            limitations=["Small sample size"],
            confidence=0.9
        )
        example_set = ClaimSet(doc_id="doi:10.1234/ex", claims=[example_claim])
        example_json = example_set.model_dump_json(indent=2)

        # Construct the full prompt
        full_prompt = f"""
{self.system_prompt}

TASK:
Analyze the following scientific paper content and extract key scientific claims, evidence, and limitations.

PAPER CONTENT:
{doc_text[:12000]}

INSTRUCTIONS:
1. Identify scientific claims.
2. Output a valid JSON object matching the structure below.
3. Do NOT output the schema definition. Output the DATA.

EXAMPLE FORMAT (Follow this structure exactly):
{example_json}

Ensure the 'doc_id' in your output is: "{header.doc_id}"
"""

        try:
            logger.info(f"🤖 Reader Agent analyzing: {header.title}")
            
            # Direct call to adapter with JSON format enforcement
            # effGen Agent wrapper might not support 'format' arg easily on run(),
            # so we might use the adapter directly for this structured task 
            # OR we ensure the adapter handles it if passed via kwargs.
            
            # Since we modify adapter to accept format in generate/chat, 
            # and effGen Agent.run() might not pass kwargs down to generate() easily without specific config,
            # Let's try calling adapter directly for strict JSON tasks to avoid middleware interference.
            # However, using Agent class gives us history management if needed. 
            # For this single-pass extraction, direct adapter usage is robust.
            
            result = self.adapter.generate(full_prompt, format="json")
            
            # Parse JSON with robust cleanup
            try:
                clean_text = result.text.strip()
                if "```json" in clean_text:
                    clean_text = clean_text.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_text:
                    clean_text = clean_text.split("```")[1].split("```")[0].strip()
                
                data = json.loads(clean_text)
                claim_set = ClaimSet(**data)
                return claim_set
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON output from Reader Agent")
                print(f"DEBUG: Failed JSON Parse. Raw: {result.text}", file=sys.stderr) # FORCE DEBUG
                return None
            except Exception as e:
                logger.error(f"Validation failed against ClaimSet schema: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Reader Agent failed: {e}")
            return None
