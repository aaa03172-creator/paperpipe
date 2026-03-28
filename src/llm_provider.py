import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI, APITimeoutError, RateLimitError, APIStatusError
import json
import time
import numpy as np
import ollama

from src.config import LLMConfig
from src.schemas import TrialExtraction, PaperTagging
from src.json_repair import repair_and_parse_json

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Canonical research text should remain English/original by default.
# Localized display layers can derive from these outputs later.
CANONICAL_SUMMARY_LANGUAGE = "English"

ESCALATION_BIOMEDICAL_SCOPE_TERMS = (
    "biomedical",
    "disease",
    "diseases",
    "patient",
    "patients",
    "cohort",
    "clinical",
    "trial",
    "randomized",
    "translational",
    "diagnosis",
    "diagnostic",
    "biomarker",
    "blood biomarker",
    "plasma biomarker",
    "csf biomarker",
    "oncology",
    "cancer",
    "tumor",
    "tumour",
    "immunology",
    "immune",
    "autoimmune",
    "inflammation",
    "cell",
    "cellular",
    "gene",
    "genetic",
    "molecular",
    "therapeutic",
    "treatment",
    "bioengineering",
    "biomaterial",
    "device",
    "implant",
    "hydrogel",
    "scaffold",
    "regenerative",
    "cartilage",
    "wound healing",
    "wound",
    "osteoarthritis",
    "brain",
    "neuroscience",
    "alzheimer",
    "alzheimers",
    "mci",
    "dementia",
    "microglia",
    "neuroinflammation",
)

ESCALATION_CONDITION_TERMS = (
    "mci",
    "mild cognitive impairment",
    "disease",
    "diseases",
    "cancer",
    "tumor",
    "tumour",
    "lymphoma",
    "leukemia",
    "melanoma",
    "colitis",
    "arthritis",
    "infection",
    "sepsis",
    "fibrosis",
    "diabetes",
    "obesity",
    "osteoarthritis",
    "cartilage",
    "wound",
    "dementia",
    "alzheimer",
    "alzheimers",
)

ESCALATION_OUT_OF_SCOPE_TERMS = (
    "sports performance",
    "collegiate cyclists",
    "endurance performance",
    "athletes",
    "football",
    "soccer",
    "basketball",
    "macroeconomic",
    "stock market",
    "consumer behavior",
    "supply chain",
    "semiconductor",
    "materials engineering",
    "synthetic polymer",
    "polymer films",
    "sustainable materials",
    "astrophysics",
    "particle physics",
    "quantum computing",
)

ESCALATION_REVIEW_STYLE_TERMS = (
    "advances in",
    "review",
    "narrative review",
    "critical review",
    "perspective",
    "personal view",
    "hypothesis",
    "what we know",
    "remains to be explored",
)

ESCALATION_METHOD_TERMS = (
    "assay",
    "cre-loxp",
    "cre loxp",
    "cre-er",
    "tamoxifen",
    "recombination",
    "recombination efficiency",
    "protocol",
    "protocol guidance",
    "workflow",
    "sample preparation",
    "validation",
    "optimized",
    "optimization",
)

ESCALATION_GUIDANCE_TERMS = (
    "recommendation",
    "recommendations",
    "guideline",
    "guidelines",
    "consensus",
    "working group",
    "clinical practice",
)

ESCALATION_CLINICAL_DATA_TERMS = (
    "randomized",
    "trial",
    "placebo",
    "patients",
    "cohort",
    "clinical study",
    "pilot",
    "prospective",
    "follow-up",
    "followup",
    "safety",
    "functional outcome",
    "response",
    "monitoring",
)

ESCALATION_ORIGINAL_EVIDENCE_TERMS = (
    "study",
    "studied",
    "results",
    "data",
    "identified",
    "reveal",
    "revealed",
    "showed",
    "demonstrated",
    "predict",
    "analysis",
    "improves",
    "improved",
    "modulate",
    "promote",
    "measured",
    "mouse",
    "mice",
    "model",
    "models",
    "cohort",
    "trial",
    "randomized",
    "prospective",
    "in vitro",
)

ESCALATION_MECHANISTIC_EVIDENCE_TERMS = (
    "mechanism",
    "pathway",
    "regulator",
    "regulators",
    "modulate",
    "promote",
    "inhibit",
    "activation",
    "signaling",
    "microglia",
    "amyloid",
    "tau",
    "macrophage",
    "t cell",
    "crispr",
    "organoid",
    "mouse model",
    "mice",
    "in vitro",
    "fibrosis",
    "tumor microenvironment",
)

ESCALATION_RESULT_IN_TITLE_TERMS = (
    "improves",
    "improved",
    "predict",
    "predicts",
    "modulate",
    "modulates",
    "promote",
    "promotes",
    "drives",
    "reveals",
    "revealed",
    "identifies",
    "identified",
    "targets",
    "concord",
    "associated with",
)

class LLMProvider:
    """LLM 공급자 인터페이스"""
    def __init__(self, config: LLMConfig, entity_aliases: Dict[str, str] = None):
        self.config = config
        self.entity_aliases = entity_aliases or {}
        self.client = None
        
        # Base implementation init
        self._initialize()

    def _initialize(self):
        """Provider specific initialization"""
        pass

    def is_available(self) -> bool:
        """API 키가 설정되어 있고 클라이언트가 준비되었는지 확인"""
        return self.client is not None

    def _temperature_for_task(self, task: str) -> float:
        """Use deterministic decoding for gate decisions to reduce approval drift."""
        if task == "escalation":
            return 0.0
        return 0.3

    @staticmethod
    def _paper_text_blob(paper: Dict[str, Any]) -> str:
        tags = paper.get("tags", [])
        if isinstance(tags, list):
            tags_text = " ".join(str(tag) for tag in tags if tag)
        else:
            tags_text = str(tags or "")
        return " ".join(
            [
                str(paper.get("title") or ""),
                str(paper.get("summary") or ""),
                tags_text,
            ]
        ).lower()

    def _escalation_fast_reject_reason(self, paper: Dict[str, Any]) -> Optional[str]:
        text = self._paper_text_blob(paper)
        has_method_lane = any(term in text for term in ESCALATION_METHOD_TERMS)
        has_guidance_lane = any(term in text for term in ESCALATION_GUIDANCE_TERMS)
        has_clinical_data = any(term in text for term in ESCALATION_CLINICAL_DATA_TERMS)
        has_original_evidence = any(term in text for term in ESCALATION_ORIGINAL_EVIDENCE_TERMS)
        is_review_style = any(term in text for term in ESCALATION_REVIEW_STYLE_TERMS)

        if has_method_lane:
            return None
        if any(term in text for term in ESCALATION_OUT_OF_SCOPE_TERMS):
            return (
                "Out of PaperPipe's biomedical research workspace scope; keep pending review unless a human explicitly overrides."
            )
        if is_review_style and not has_guidance_lane and not has_clinical_data and not has_original_evidence:
            return (
                "Broad review-style biomedical paper without authoritative guidance or direct clinical/translational evidence; keep pending review."
            )
        if not any(term in text for term in ESCALATION_BIOMEDICAL_SCOPE_TERMS):
            return (
                "Out of PaperPipe's biomedical research workspace scope; keep pending review unless a human explicitly overrides."
            )
        return None

    def _escalation_fast_approve_reason(self, paper: Dict[str, Any]) -> Optional[str]:
        text = self._paper_text_blob(paper)
        title = str(paper.get("title") or "").lower()
        negative_scope_signals = (
            "not about",
            "did not involve",
            "does not involve",
            "not involve",
            "not relevant",
            "relevance is indirect",
            "indirect relevance",
            "not central",
        )
        if any(signal in text for signal in negative_scope_signals):
            return None
        has_biomedical_scope = any(term in text for term in ESCALATION_BIOMEDICAL_SCOPE_TERMS)
        has_condition_context = any(term in text for term in ESCALATION_CONDITION_TERMS)
        has_method_lane = any(term in text for term in ESCALATION_METHOD_TERMS)
        has_guidance_lane = any(term in text for term in ESCALATION_GUIDANCE_TERMS)
        has_clinical_data = any(term in text for term in ESCALATION_CLINICAL_DATA_TERMS)
        has_original_evidence = any(term in text for term in ESCALATION_ORIGINAL_EVIDENCE_TERMS)
        has_mechanistic_evidence = any(term in text for term in ESCALATION_MECHANISTIC_EVIDENCE_TERMS)
        has_title_result_signal = any(term in title for term in ESCALATION_RESULT_IN_TITLE_TERMS)
        is_review_style = any(term in text for term in ESCALATION_REVIEW_STYLE_TERMS)

        if has_method_lane and has_biomedical_scope:
            return "Concrete biomedical methods/protocol optimization is explicit; safe to auto-approve."

        if has_guidance_lane and has_biomedical_scope and (
            "diagnosis" in text
            or "diagnostic" in text
            or "biomarker" in text
            or "treatment" in text
            or "monitoring" in text
            or "clinical" in text
        ):
            return "Authoritative biomedical guidance is explicit; safe to auto-approve."

        if (
            has_biomedical_scope
            and has_condition_context
            and has_clinical_data
            and has_original_evidence
            and not is_review_style
        ):
            return "Direct biomedical clinical/translational evidence is explicit; safe to auto-approve."

        if (
            has_biomedical_scope
            and has_condition_context
            and has_mechanistic_evidence
            and has_original_evidence
            and has_title_result_signal
            and not is_review_style
        ):
            return "Direct biomedical mechanistic evidence is explicit; safe to auto-approve."

        return None

    def _build_escalation_prompt(self, paper: Dict[str, Any]) -> str:
        return f"""
        You are the final escalation gate for PaperPipe.
        The paper is already in "Pending Review". Your default answer is NO.

        Approve only when the title/abstract/tags make it obvious that a human does not need to inspect it.
        If there is any uncertainty, breadth, or indirect relevance, return approved=false.

        Paper:
        - Title: {paper.get('title', 'N/A')}
        - Abstract: {paper.get('summary', 'N/A')}
        - Current Tags: {paper.get('tags', [])}

        Auto-approve ONLY if all of the following are true:
        1. Direct fit to biomedical scope with immediate routing value:
           - human clinical or translational evidence in a defined disease or population
           - authoritative recommendation / consensus / guidance relevant to biomedical practice
           - concrete biomedical methods or protocol optimization
           - strong mechanistic biomedical evidence with a specific result in disease-relevant context
        2. The title/abstract/tags make the routing obvious from metadata alone.
        3. The paper looks decision-relevant now, not merely interesting.

        Reject and keep pending review when any of these apply:
        - broad review, critical review, narrative review, perspective, or hypothesis piece without a clearly authoritative recommendation
        - indirect or ambiguous biomedical relevance
        - interesting but uncertain from metadata alone
        - clearly out of PaperPipe's biomedical workspace scope

        Return JSON STRICTLY:
        {{
            "approved": boolean,
            "new_confidence": float,
            "reason": "One sentence, concrete and conservative."
        }}
        """

    def _get_model(self, task: str) -> str:
        """작업에 적합한 모델을 반환 (override 우선)"""
        # Default behavior: rely on feature config overrides if enabled, else provider default
        # This will be overridden by subclasses to map to specific model dicts (e.g. Ollama)
        if self.config.features: # Check if features config exists
            if task == "trial_extraction" and self.config.features.trial_extraction:
                return self.config.features.trial_extraction.model
            elif task == "one_liner" and self.config.features.one_liner:
                return self.config.features.one_liner.model
            elif task == "slot_classification" and self.config.features.slot_classification:
                return self.config.features.slot_classification.model
        
        # Fallback to default_model if features not configured or task not found
        if self.config.default_model:
            return self.config.default_model
        
        return "gpt-4o-mini" # Ultimate fallback

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        raise NotImplementedError

    def get_embedding(self, text: str) -> Optional[List[float]]:
        raise NotImplementedError

    def _extract_json(self, response_content: str) -> Optional[Dict[str, Any]]:
        """
        Robustly extract/repair JSON from LLM response.
        """
        if not response_content:
            return None

        try:
            parsed = repair_and_parse_json(response_content)
            
            # [Smart Unwrap Logic]
            # If the LLM wrapped the response in "data", "response", "content", etc., unwrap it.
            # For tagging, we expect hard_tags and soft_tags to be present together.
            
            def find_keys(obj, keys):
                if isinstance(obj, dict):
                    # Check if this object has the keys we want
                    if all(k in obj for k in keys):
                        return obj
                    # If not, check values (recursive descent)
                    for v in obj.values():
                        found = find_keys(v, keys)
                        if found:
                            return found
                return None

            # Try to find the schema if not at root
            # Only do this if we are looking for a specific schema structure (inferred by context or generous check)
            # For tagging, we expect hard_tags and soft_tags.
            unwrapped = find_keys(parsed, ["hard_tags", "soft_tags"])
            if unwrapped:
                return unwrapped
            
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to extract JSON from content: {response_content[:100]}... ({e})")
        return None

    def extract_trial_data(self, paper: Dict[str, Any], methods_snippet: str = "") -> Optional[TrialExtraction]:
        """임상시험 논문에서 Pydantic 모델을 사용하여 구조화된 데이터를 추출하고 검증합니다."""
        
        # [Fix] Pydantic 모델에서 JSON 스키마 추출하여 프롬프트에 주입
        try:
            schema_json = json.dumps(TrialExtraction.model_json_schema(), indent=2)
        except Exception:
            schema_json = "Schema definition unavailable."

        prompt = f"""
You are an information extraction engine for clinical trials about MCT/ketone supplementation in Mild Cognitive Impairment (MCI).
Extract structured data STRICTLY as valid JSON following the provided schema below. Do not output any Markdown, comments, or extra keys.

Schema:
{schema_json}

Rules:
- The target population is MCI-only. If the study includes AD or mixed populations and MCI-specific results are not separable, mark include_for_mci_mct_review=false and explain why.
- Primary outcomes must cover cognition AND also capture ADL/function and safety/adherence when reported.
- Ketone ester/salt interventions must be included but tagged for separate analysis (separate_analysis_tag="ketone_ester_or_salt").
- If a field is not stated, use null/0/unknown appropriately and list it in extraction_quality.missing_fields.
- **IMPORTANT**: If specific dose/product is missing in abstract, INFER 'category' and 'product_name' from Title or Context. Do not leave Intervention empty if possible.
- If the paper is a Systematic Review or Meta-analysis:
    - Set 'category' to the INTERVENTION TOPIC (e.g., 'ketogenic_diet', 'mct', 'ketone_ester').
    - Set 'product_name' to "Systematic Review".
    - Summarize the overall conclusion in 'outcomes.cognition[0].notes'.
- Always try to classify 'separate_analysis_tag' (e.g., 'primary_mct', 'ketogenic_diet') even if details are sparse.
- For 'Population', if 'mci_only' is false, provide details in 'comorbidity_notes' (e.g., "Includes AD and Healthy Controls").

Now extract from the following text:
<<<
Title: {paper.get('title', 'N/A')}
Abstract: {paper.get('summary', 'N/A')}
Methods Snippet: {methods_snippet if methods_snippet else "Not available"}
>>>
"""
        
        for i in range(2): # 최대 2번 시도 (최초 1회 + 재시도 1회)
            response_content = self._make_request("trial_extraction", prompt, is_json=True, schema=TrialExtraction.model_json_schema())
            
            if not response_content or "AI Error" in response_content:
                logger.error(f"Failed to get valid content from LLM: {response_content}")
                return None

            try:
                # [Modified] Parse using robust extractor
                data = self._extract_json(response_content)
                if not data:
                    logger.warning(f"Attempt {i+1}: Failed to extract JSON from response.")
                    continue
                
                # Ensure metadata (Robustness)
                if not data.get('paper_id'):
                    data['paper_id'] = paper.get('doi') or paper.get('link') or paper.get('title') or "unknown_id"
                
                # Citation 정보가 부실하면 원본 메타데이터로 보완
                if not data.get('citation'):
                    data['citation'] = {
                        'title': paper.get('title', ''),
                        'authors_first': str(paper.get('authors', '')).split(',')[0] if paper.get('authors') else 'Unknown',
                        'year': int(paper.get('published', '0')[:4]) if paper.get('published') and paper.get('published')[:4].isdigit() else 0,
                        'journal_or_server': paper.get('source', 'Unknown'),
                        'doi': paper.get('doi'),
                        'url': paper.get('link')
                    }

                validated_data = TrialExtraction(**data)
                logger.info("Successfully parsed and validated trial extraction data.")
                return validated_data
            except Exception as e:
                logger.error(f"Schema validation failed for LLM response: {e}")
                # 유효성 검사 실패 시 재시도 없이 종료 (프롬프트 자체의 문제일 수 있음)
                return None
        
        logger.error("Failed to get a valid and parseable JSON response after retries.")
        return None

    def generate_deep_read(self, paper: Dict[str, Any]) -> Optional[str]:
        """논문을 심도 있게 분석하는 'Deep Read' 요약 생성"""
        slot = paper.get('slot', '').lower()
        
        if slot == 'methods':
            prompt = f"""
            Analyze this METHODOLOGY paper for a neuroscientist.
            Title: {paper.get('title', 'N/A')}
            Abstract: {paper.get('summary', 'N/A')}
            
            Provide a structured report in {CANONICAL_SUMMARY_LANGUAGE} (Markdown):
            0. **Originality Summary (Triage 4-Step)**
               - **Context**: What is the broader background of this line of research?
               - **Gap**: What decisive question did prior work leave unresolved?
               - **This Paper**: How does this paper address that question?
            
            1. **Core Technique**: What is the main method or protocol?
            2. **Key Protocol And Tips**: What critical steps, reagents, or troubleshooting advice are highlighted?
            3. **Advantages And Innovation**: Why is it better than existing methods?
            4. **Limitations And Caveats**: What are the constraints or potential pitfalls?
            5. **Applications**: How can this be applied in neuroscience?
            """
        elif slot == 'mechanism':
            prompt = f"""
            Analyze this MECHANISTIC paper for a neuroscientist.
            Title: {paper.get('title', 'N/A')}
            Abstract: {paper.get('summary', 'N/A')}
            
            Provide a structured report in {CANONICAL_SUMMARY_LANGUAGE} (Markdown):
            0. **Originality Summary (Triage 4-Step)**
               - **Context**: What is the broader background of this line of research?
               - **Gap**: What decisive question did prior work leave unresolved?
               - **This Paper**: How does this paper address that question?
               
            1. **Hypothesis**: What are they testing?
            2. **Key Mechanism**: What pathway or molecule interactions are proposed (for example, A -> B -> C)?
            3. **Key Results**: What findings support the mechanism?
            4. **Implications**: What is the impact on the field?
            """
        else:
            prompt = f"""
            Analyze this paper for a neuroscientist.
            Title: {paper.get('title', 'N/A')}
            Abstract: {paper.get('summary', 'N/A')}
            
            Provide a structured report in {CANONICAL_SUMMARY_LANGUAGE} (Markdown):
            0. **Originality Summary** (Context -> Gap -> Paper)
               - **Context**: What is the broader background of this line of research?
               - **Gap**: What decisive question did prior work leave unresolved?
               - **This Paper**: How does this paper address that question?
            1. **Key Findings**
            2. **Methodology**
            3. **Implications And Limitations**
            """
        return self._make_request("deep_read", prompt)

    def generate_one_liner(self, paper: Dict[str, Any]) -> Optional[str]:
        """논문의 핵심 내용을 한 문장으로 요약"""
        prompt = f"""
        Summarize the core contribution of this paper in ONE SINGLE {CANONICAL_SUMMARY_LANGUAGE} sentence, like a TL;DR.
        Title: {paper.get('title', 'N/A')}
        Abstract: {paper.get('summary', 'N/A')}
        """
        return self._make_request("one_liner", prompt)

    def review_claimset_bundle(self, *, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Teacher-quality review over a prepared claimset bundle."""
        return self._make_request("teacher_review", prompt, is_json=True, system_prompt=system_prompt)

    def classify_slot(self, paper: Dict[str, Any], current_slot: str) -> str:
        """논문의 슬롯을 계층적(Hierarchical)으로 분류"""
        prompt = f"""
        You are a research paper classifier.
        Perform a step-by-step hierarchical classification.
        
        Target Schema (Slots):
        1. **Mechanism**: Basic science, cellular pathways, molecular interactions (e.g., autophagy, sphingolipids).
        2. **Clinical**: Human trials, patient studies, drug effects on humans (e.g., MCI, keto diet).
        3. **Methods**: New protocols, techniques, validation of assays.

        Paper Info:
        - Title: {paper.get('title', 'N/A')}
        - Abstract: {paper.get('summary', 'N/A')[:1500]}
        
        Current Rule-based Guess: {current_slot}

        Reasoning Steps:
        1. **Domain Check**: Is this Neuroscience / Cell Biology / Medicine?
        2. **Clinical Verification**: Does it involve human patients/subjects? If yes -> likely Clinical.
        3. **Methodology Verification**: Is the *primary* focus a new method? If yes -> likely Methods.
        4. **Mechanism Check**: Is it exploring a biological pathway in cells/animals? -> likely Mechanism.
        
        Return JSON STRICTLY:
        {{
            "reasoning": "Step-by-step reasoning...",
            "predicted_slot": "Mechanism" | "Clinical" | "Methods"
        }}
        """
        response_content = self._make_request("slot_classification", prompt, is_json=True)
        
        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                    predicted = data.get("predicted_slot")
                    if predicted in ["Mechanism", "Clinical", "Methods"]:
                        logger.info(f"   🤖 Slot Verified: {current_slot} -> {predicted}")
                        return predicted
            except Exception:
                pass
        
        logger.warning("   ⚠️ Classification verification failed. Keeping original slot.")
        return current_slot

    def tag_paper(self, paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Hybrid Tagging: Extraction (Hard) + Generation (Soft)"""
        # from src.schemas import PaperTagging # Delayed import to avoid circular dependency if any - already imported

        # [NEW] Alias Injection
        alias_prompt_section = ""
        if self.entity_aliases:
            alias_list = "\n".join([f"- '{alias}' -> '{standard}'" for alias, standard in self.entity_aliases.items()])
            alias_prompt_section = f"""
        5. **Entity Normalization (CRITICAL)**:
           You MUST normalize the following terms to their standard names if encountered:
           {alias_list}
           - Example: If text says "AD patients", soft tag MUST be "#AlzheimerDisease", NOT "#AD".
            """

        system_prompt = f"""
        Perform Hybrid Tagging for this research paper.
        
        1. **Analysis**: Understand the main topic, species used, and key findings.
        2. **Soft Tagging (Generation)**: Generate **at least 3 keywords** (Soft Tags).
           - **Format**: `#Category/Subcategory` or `#Concept` (Obsidian style).
           - **STRICT FORMATTING**: 
             - Use **Forward Slash (/)** for hierarchy (e.DO NOT** use `>`.
             - **NO SPACES**: Use `CamelCase` or `snake_case` (e.g., `#ClinicalTrial`, `#Alzheimers_Disease`).
             - **NO Special Characters**: Remove `&`, `:`.
           - **Authority**: Use standard MeSH terms adapted to this format.
           - **Hierarchy**: Include at least one broad category tag (e.g., `#Medicine/Neurology`).
           - **No Repeats**: **DO NOT** use words that already appear in the **TITLE**. Add NEW context.
           - **FAIL-SAFE**: Even if hard extraction fails, YOU MUST GENERATE SOFT TAGS.
        {alias_prompt_section}
           
        3. **Hard Tagging (Extraction)**: Extract exact values if present. If not found, use null.
           - 'species': 'mouse', 'human', etc.
           - 'sample_size': n number (integer)
           - 'model': e.g., '5xFAD', 'HeLa'

        4. **Evidence & Confidence (Mandatory)**:
           - **evidence_span**: Quote the EXACT sentence or phrase from the abstract/title that justifies your tags.
           - **confidence**: A score between 0.0 and 1.0 indicating how sure you are about the tags and classification.
        
        Return JSON ONLY in the following structure:
        {{
            "hard_tags": {{
                "species": "extracted species or null",
                "sample_size": integer or null, 
                "model": "extracted model or null" 
            }}, 
            "soft_tags": ["#Category/Subcategory", "#AnotherTag"],
            "evidence_span": "Quote from text...",
            "confidence": 0.8,
            "reasoning": "Reasoning..."
        }}
        
        Example Output (Structure Reference):
        {{
            "hard_tags": {{"species": null, "sample_size": 1500, "model": "Solar Dynamics Observatory"}},
            "soft_tags": ["#Astronomy/SolarPhysics", "#SolarFlares", "#MagneticReconnection"],
            "evidence_span": "We analyzed 1500 solar flares observed by SDO...",
            "confidence": 0.95,
            "reasoning": "Paper analyzes solar flare data from SDO satellite."
        }}
        
        Rules:
        - If 'hard_tags' are not found, return dictionary with null values.
        - **'soft_tags' MUST NOT be empty and MUST START WITH #.**
        - **NEVER return an empty list for 'soft_tags'.**
        - **DO NOT WRAP the response in 'content' or 'response' keys. return the schema keys at the ROOT.**
        """
        
        user_prompt = f"""
        Paper:
        - Title: {paper.get('title', 'N/A')}
        - Abstract: {paper.get('summary', 'N/A')}
        """
        
        # [NEW] Append Full Text Snippet if available
        full_text = paper.get('full_text')
        if full_text:
            snippet = full_text[:20000] # Limit to 20k chars context window
            user_prompt += f"\n- Full Text Content (First 20k chars):\n{snippet}\n"
        
        # Use System Prompt + User Prompt. Enable JSON mode for stability.
        response_content = self._make_request("tagging", user_prompt, is_json=True, schema=None, system_prompt=system_prompt)
        
        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                     # Validation
                    tagging_result = PaperTagging(**data)
                    return tagging_result.model_dump()
                else: 
                     logger.warning("Extracted JSON was None/Empty")
            except Exception as e:
                logger.error(f"Error parsing tagging result: {e}. Content: {response_content[:100]}...")
                return None
        
        return None

    def evaluate_escalation(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """Escalation Gate: Re-evaluate 'Pending Review' papers with a stricter Judge logic."""
        fast_reject_reason = self._escalation_fast_reject_reason(paper)
        if fast_reject_reason:
            return {"approved": False, "new_confidence": 0.0, "reason": fast_reject_reason}

        fast_approve_reason = self._escalation_fast_approve_reason(paper)
        if fast_approve_reason:
            return {"approved": True, "new_confidence": 0.96, "reason": fast_approve_reason}

        prompt = self._build_escalation_prompt(paper)
        
        response_content = self._make_request("escalation", prompt, is_json=True)
        
        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                    return {
                        "approved": data.get("approved", False),
                        "new_confidence": data.get("new_confidence", 0.0),
                        "reason": data.get("reason", "No reason provided")
                    }
            except Exception:
                logger.warning("Failed to parse Escalation Judge response.")
        
        return {"approved": False, "reason": "Judge Error"}

    def analyze_relevance(self, paper: Dict[str, Any], rq: str) -> Optional[Dict[str, str]]:
        """[NEW] Ticket 7: Context-Aware Summarization Logic"""
        prompt = f"""
        You are a research assistant helping to answer a specific Research Question (RQ).
        
        MY RESEARCH QUESTION: "{rq}"
        
        Analyze the following paper to extract insights relevant to my RQ.
        
        Paper:
        - Title: {paper.get('title', 'N/A')}
        - Abstract: {paper.get('summary', 'N/A')}
        
        Identify:
        1. **Gap**: What specific gap or problem does this paper address that is relevant to my RQ?
        2. **Insight**: What key finding or method in this paper directly helps answer my RQ?
        3. **Limitation**: What are the limitations of this paper in the context of my RQ?
        
        Return JSON STRICTLY:
        {{
            "gap": "1-2 sentences...",
            "insight": "1-2 sentences...",
            "limitation": "1-2 sentences..."
        }}
        """
        
        response_content = self._make_request("relevance_analysis", prompt, is_json=True)
        
        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                    return {
                        "gap": data.get("gap", "N/A"),
                        "insight": data.get("insight", "N/A"),
                        "limitation": data.get("limitation", "N/A")
                    }
            except Exception:
                logger.warning("Failed to parse Relevance Analysis response.")
        
        return None

    def find_related_papers(self, target_paper_id: str, all_papers_vectors: Dict[str, List[float]], top_k: int = 3) -> List[Any]:
        """
        Smart Linking: Finds related papers based on embedding similarity.
        Requires pre-computed embeddings for all papers.
        """
        if target_paper_id not in all_papers_vectors:
            logger.warning(f"Target paper ID '{target_paper_id}' not found in provided vectors.")
            return []
        
        target_vec = np.array(all_papers_vectors[target_paper_id])
        
        # Handle zero vector case
        if np.linalg.norm(target_vec) == 0:
            logger.warning(f"Target paper '{target_paper_id}' has a zero embedding vector. Cannot compute similarity.")
            return []

        results = []
        
        for pid, vec in all_papers_vectors.items():
            if pid == target_paper_id:
                continue
            
            current_vec = np.array(vec)
            
            # Handle zero vector case for current paper
            norm_current_vec = np.linalg.norm(current_vec)
            if norm_current_vec == 0:
                logger.debug(f"Skipping paper '{pid}' due to zero embedding vector.")
                continue

            # Cosine similarity
            similarity = np.dot(target_vec, current_vec) / (np.linalg.norm(target_vec) * norm_current_vec)
            results.append((pid, similarity))
        
        # Sort desc
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


class OpenAIProvider(LLMProvider):
    """OpenAI API를 사용하는 LLM 공급자"""
    def _initialize(self):
        # Resolve API Key based on mode or fallback
        api_key = None
        if self.config.cloud and self.config.cloud.api_key:
            api_key = self.config.cloud.api_key
        
        if not api_key:
            logger.warning("OpenAI API key is not configured. OpenAI features will be disabled.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)

    def _get_model(self, task: str) -> str:
        # If cloud config has specific model per task, use it
        if self.config.cloud and self.config.cloud.model:
            return self.config.cloud.model
        # Otherwise, fall back to the generic LLMProvider logic
        return super()._get_model(task)

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """중앙화된 API 요청 핸들러 (재시도, 타임아웃, 에러 처리)"""
        if not self.is_available():
            return None

        model = self._get_model(task)
        logger.info(f"Making LLM request to model '{model}' for task '{task}'.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": self._temperature_for_task(task),
            "timeout": self.config.timeout_seconds,
        }
        if is_json or schema: # OpenAI uses response_format for JSON, schema is not directly passed
            request_params["response_format"] = {"type": "json_object"}

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**request_params)
                return response.choices[0].message.content
            except RateLimitError:
                wait_time = 2 ** (attempt + 1) # 2초, 4초, 8초 대기
                logger.warning(f"LLM RateLimit hit on attempt {attempt + 1}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                if attempt >= self.config.max_retries:
                    logger.error("LLM RateLimit exceeded. Please check OpenAI credit balance.")
                    return "❌ AI Error: Rate Limit (Check Billing)"
            except APITimeoutError:
                logger.warning(f"LLM Timeout on attempt {attempt + 1}. Retrying...")
                if attempt >= self.config.max_retries:
                    logger.error("LLM Timeout exceeded.")
                    return "❌ AI Error: Timeout"
            except APIStatusError as e:
                logger.error(f"LLM API Error: {e.status_code} - {e.message}")
                return f"❌ AI Error: {e.message}"
            except Exception as e:
                logger.exception(f"An unexpected error occurred during LLM request: {e}")
                return "❌ AI Error: An unexpected error occurred."
        return None
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        if not self.is_available():
            return None
        try:
            # Use the embedding model specified in config, or a default
            embedding_override = getattr(self.config.cloud, "embedding_model", None) if self.config.cloud else None
            embedding_model = embedding_override or "text-embedding-3-small"
            resp = self.client.embeddings.create(input=text, model=embedding_model)
            return resp.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            return None

class OllamaProvider(LLMProvider):
    """Ollama API를 사용하는 LLM 공급자"""
    def _initialize(self):
        # Ollama client is implicit via library but we can configure base_url
        self.host = self.config.local.base_url if self.config.local else "http://localhost:11434"
        self.models = self.config.local.models if self.config.local else {}
        
        try:
            # Test connection by creating a client instance
            self.ollama_client = ollama.Client(
                host=self.host,
                timeout=self.config.timeout_seconds,
            )
            # Attempt to list models to confirm connectivity
            self.ollama_client.list()
            self.client = True # Mark as available
            logger.info(f"Ollama connected successfully at {self.host}")
        except Exception as e:
            logger.warning(f"Ollama connection failed at {self.host}: {e}. Ollama features will be disabled.")
            self.client = None
            self.ollama_client = None

    def _get_model(self, task: str) -> str:
        # Map task to local models defined in config, with fallbacks
        if self.models:
            if task == "trial_extraction":
                return self.models.get("extractor", "llama3:8b")
            if task == "slot_classification":
                return self.models.get("classifier", "llama3:8b")
            if task == "tagging":
                return self.models.get("tagger", "biomistral:7b")
            if task == "escalation":
                return self.models.get("judge", "llama3:latest")
            if task == "teacher_review":
                return self.models.get("teacher_review", self.models.get("chat", "phi3"))
            if task == "one_liner":
                return self.models.get("one_liner", "phi3")
            if task == "deep_read":
                return self.models.get("deep_read", "llama3:8b")
            if task == "relevance_analysis":
                return self.models.get("relevance_analyzer", "llama3:8b")
        
        # Fallback to a general chat model if specific task model not found
        return self.models.get("chat", "phi3")

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        if not self.is_available():
            return None

        model = self._get_model(task)
        logger.info(f"Making LLM request to Ollama model '{model}' for task '{task}'.")

        options = {
            "temperature": self._temperature_for_task(task),
            "num_predict": 4096, # Max tokens to generate
        }
        
        # Ollama handles JSON output via the 'format' parameter
        format_param = None
        if schema:
            format_param = "json" 
        elif is_json:
            format_param = "json"

        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        try:
            response = self.ollama_client.chat(
                model=model,
                messages=messages,
                format=format_param,
                options=options
            )
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama Request Failed for model '{model}': {e}")
            return f"❌ AI Error: Ollama request failed ({model}). Check server logs."

    def get_embedding(self, text: str) -> Optional[List[float]]:
        if not self.is_available():
            return None
        try:
            embedding_model = self.models.get("embedder", "nomic-embed-text")
            response = self.ollama_client.embeddings(model=embedding_model, prompt=text)
            return response['embedding']
        except Exception as e:
            logger.error(f"Ollama embedding failed for model '{embedding_model}': {e}")
            return None

class HybridProvider(LLMProvider):
    """로컬(Ollama)과 클라우드(OpenAI) LLM을 조합하여 사용하는 공급자"""
    def _initialize(self):
        self.local = OllamaProvider(self.config, self.entity_aliases)
        self.cloud = OpenAIProvider(self.config, self.entity_aliases)
        # Hybrid provider is logically available if at least one sub-provider is available
        self.client = self.local.is_available() or self.cloud.is_available()
        if not self.client:
            logger.error("Neither local nor cloud LLM providers are available in Hybrid mode.")

    def is_available(self) -> bool:
        return self.local.is_available() or self.cloud.is_available()

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        # This method should not be called directly in HybridProvider,
        # as specific tasks are routed to specific sub-providers.
        # However, if a task is not explicitly routed, we can define a fallback.
        logger.warning(f"HybridProvider: Unrouted task '{task}'. Falling back to cloud if available, else local.")
        if self.cloud.is_available():
            return self.cloud._make_request(task, prompt, is_json, schema, system_prompt=system_prompt)
        elif self.local.is_available():
            return self.local._make_request(task, prompt, is_json, schema, system_prompt=system_prompt)
        else:
            logger.error(f"HybridProvider: No LLM available for task '{task}'.")
            return "❌ AI Error: No LLM available."

    def get_embedding(self, text: str) -> Optional[List[float]]:
        # Prefer local embedding for cost/speed
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for embedding.")
            return self.local.get_embedding(text)
        elif self.cloud.is_available():
            logger.debug("HybridProvider: Using cloud for embedding.")
            return self.cloud.get_embedding(text)
        logger.error("HybridProvider: No LLM available for embedding.")
        return None

    # Routing Logic for specific tasks
    def classify_slot(self, paper: Dict[str, Any], current_slot: str) -> str:
        # L1/L2 -> Local (Fast)
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for slot classification.")
            return self.local.classify_slot(paper, current_slot)
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for slot classification, falling back to cloud.")
            return self.cloud.classify_slot(paper, current_slot)
        logger.error("HybridProvider: No LLM available for slot classification.")
        return current_slot # Fallback to original if no LLM

    def tag_paper(self, paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # High volume -> Local (BioMistral)
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for tagging.")
            return self.local.tag_paper(paper)
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for tagging, falling back to cloud.")
            return self.cloud.tag_paper(paper)
        logger.error("HybridProvider: No LLM available for tagging.")
        return None

    def generate_one_liner(self, paper: Dict[str, Any]) -> Optional[str]:
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for one-liner generation.")
            return self.local.generate_one_liner(paper)
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for one-liner, falling back to cloud.")
            return self.cloud.generate_one_liner(paper)
        logger.error("HybridProvider: No LLM available for one-liner.")
        return None
    
    def extract_trial_data(self, paper: Dict[str, Any], methods_snippet: str = "") -> Optional[TrialExtraction]:
        # Trials are critical -> Prefer Cloud for accuracy, OR Local if specified
        # Spec says: "Tagging & Linking (Ollama)", "Escalation (Cloud)".
        # Trial extraction is closer to Tagging (Extraction).
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for trial data extraction.")
            return self.local.extract_trial_data(paper, methods_snippet)
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for trial extraction, falling back to cloud.")
            return self.cloud.extract_trial_data(paper, methods_snippet)
        logger.error("HybridProvider: No LLM available for trial data extraction.")
        return None

    def evaluate_escalation(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        # Gate 2 -> Escalation -> Cloud (GPT-4o)
        if self.cloud.is_available():
            logger.info("⚡️ HybridProvider: Using Cloud (OpenAI) for Escalation Evaluation.")
            return self.cloud.evaluate_escalation(paper)
        
        logger.warning("HybridProvider: Cloud unavailable for escalation, falling back to local.")
        if self.local.is_available():
            return self.local.evaluate_escalation(paper)
        
        logger.error("HybridProvider: No LLM available for escalation evaluation.")
        return {"approved": False, "reason": "No LLM available for escalation."}
    
    def generate_deep_read(self, paper: Dict[str, Any]) -> Optional[str]:
        # Local-first by design. Cloud is fallback when local is unavailable.
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for deep read generation.")
            return self.local.generate_deep_read(paper)
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for deep read, falling back to cloud.")
            return self.cloud.generate_deep_read(paper)
        logger.error("HybridProvider: No LLM available for deep read generation.")
        return None

    def analyze_relevance(self, paper: Dict[str, Any], rq: str) -> Optional[Dict[str, str]]:
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for relevance analysis.")
            return self.local.analyze_relevance(paper, rq)
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for relevance analysis, falling back to cloud.")
            return self.cloud.analyze_relevance(paper, rq)
        logger.error("HybridProvider: No LLM available for relevance analysis.")
        return None


def get_llm_provider(config: LLMConfig, entity_aliases: Dict[str, str] = None) -> Optional[LLMProvider]:
    """설정에 맞는 LLM 공급자 인스턴스를 반환"""
    if config.mode == "hybrid":
        logger.info("Initializing Hybrid LLM Provider.")
        return HybridProvider(config, entity_aliases)
    elif config.mode == "local":
        if config.local and config.local.provider == "ollama":
            logger.info("Initializing Local Ollama LLM Provider.")
            return OllamaProvider(config, entity_aliases)
        else:
            logger.error(f"Local mode specified, but no valid local provider configured: {config.local.provider if config.local else 'None'}")
            return None
    elif config.mode == "cloud":
        if config.cloud and config.cloud.provider == "openai":
            logger.info("Initializing Cloud OpenAI LLM Provider.")
            return OpenAIProvider(config, entity_aliases)
        else:
            logger.error(f"Cloud mode specified, but no valid cloud provider configured: {config.cloud.provider if config.cloud else 'None'}")
            return None
    
    logger.error(f"Invalid LLM mode specified: {config.mode}. No LLM provider initialized.")
    return None
