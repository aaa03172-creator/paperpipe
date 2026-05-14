import logging
from typing import Dict, Any, Optional
from openai import OpenAI, APITimeoutError, RateLimitError, APIStatusError
import json
import time
import re

from pydantic import ValidationError

from src.config import LLMConfig
from src.schemas import TrialExtraction

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMProvider:
    """LLM 공급자 인터페이스"""
    def __init__(self, config: LLMConfig):
        self.config = config
        self.api_key = None
        
        # [강력한 방어 코드] Config 객체와 별개로 로컬 변수에 정제된 키 저장
        if self.config.api_key:
            self.api_key = re.sub(r'\s+', '', self.config.api_key)

        if not self.api_key:
            logger.warning("LLM Provider: API key is not configured. All LLM features will be disabled.")
            self.client = None
        else:
            self.client = self._create_client()

    def _create_client(self):
        raise NotImplementedError

    def is_available(self) -> bool:
        """API 키가 설정되어 있고 클라이언트가 준비되었는지 확인"""
        return self.client is not None and self.api_key is not None

    def extract_trial_data(self, paper: Dict[str, Any]) -> Optional[TrialExtraction]:
        raise NotImplementedError

    def generate_one_liner(self, paper: Dict[str, Any]) -> Optional[str]:
        raise NotImplementedError
    
    def generate_deep_read(self, paper: Dict[str, Any]) -> Optional[str]:
        """논문을 심도 있게 분석하는 'Deep Read' 요약 생성"""
        raise NotImplementedError

    def classify_slot(self, paper: Dict[str, Any], current_slot: str) -> str:
        """논문의 슬롯(Mechanism, Clinical, Methods)을 재분류"""
        raise NotImplementedError

    def _get_model(self, task: str) -> str:
        """작업에 적합한 모델을 반환 (override 우선)"""
        if task == "trial_extraction":
            return self.config.features.trial_extraction.model
        elif task == "one_liner":
            return self.config.features.one_liner.model
        elif task == "slot_classification":
            return self.config.features.slot_classification.model
        return self.config.default_model

class OpenAIProvider(LLMProvider):
    """OpenAI API를 사용하는 LLM 공급자"""
    def _create_client(self):
        # 이미 __init__에서 정제된 self.api_key 사용
        return OpenAI(api_key=self.api_key)

    def _make_request(self, task: str, prompt: str, is_json: bool = False):
        """중앙화된 API 요청 핸들러 (재시도, 타임아웃, 에러 처리)"""
        if not self.is_available():
            return None

        model = self._get_model(task)
        logger.info(f"Making LLM request to model '{model}' for task '{task}'.")
        
        messages = [{"role": "user", "content": prompt}]
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "timeout": self.config.timeout_seconds,
        }
        if is_json:
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
                return f"❌ AI Error: An unexpected error occurred."
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
            response_content = self._make_request("trial_extraction", prompt, is_json=True)
            
            if not response_content or "AI Error" in response_content:
                logger.error(f"Failed to get valid content from LLM: {response_content}")
                return None

            try:
                # [Modified] Parse JSON first, inject metadata, then validate
                data = json.loads(response_content)
                
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
            except json.JSONDecodeError:
                logger.warning(f"Attempt {i+1}: Failed to parse JSON. Retrying with a corrective prompt.")
                prompt = "The previous response was not valid JSON. Please output ONLY the JSON object, with no additional text or formatting."
            except ValidationError as e:
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
            
            Provide a structured report in Korean (Markdown):
            1. **기술의 핵심 (Core Technique)**: What is the main method/protocol?
            2. **주요 프로토콜 및 팁 (Key Protocol & Tips)**: Critical steps, reagents, or troubleshooting advice mentioned.
            3. **장점 및 혁신성 (Advantages & Innovation)**: Why is it better than existing methods?
            4. **한계 및 주의점 (Limitations & Caveats)**: What are the constraints or potential pitfalls?
            5. **적용 분야 (Applications)**: How can this be applied in neuroscience (e.g., specific circuits, cell types)?
            """
        elif slot == 'mechanism':
            prompt = f"""
            Analyze this MECHANISTIC paper for a neuroscientist.
            Title: {paper.get('title', 'N/A')}
            Abstract: {paper.get('summary', 'N/A')}
            
            Provide a structured report in Korean (Markdown):
            1. **핵심 가설 (Hypothesis)**: What are they testing?
            2. **주요 메커니즘 (Key Mechanism)**: Detailed pathway/molecule interactions (e.g., A -> B -> C).
            3. **실험 결과 (Key Results)**: Main findings supporting the mechanism.
            4. **의의 (Implications)**: Impact on the field (e.g., new drug target, understanding disease).
            """
        else:
            prompt = f"""
            Analyze this paper for a neuroscientist.
            Title: {paper.get('title', 'N/A')}
            Abstract: {paper.get('summary', 'N/A')}
            
            Provide a structured report in Korean (Markdown):
            1. **핵심 발견 (Key Findings)**
            2. **방법론적 특징 (Methodology)**
            3. **의의 및 한계 (Implications & Limitations)**
            """
        return self._make_request("deep_read", prompt)

    def generate_one_liner(self, paper: Dict[str, Any]) -> Optional[str]:
        """논문의 핵심 내용을 한 문장으로 요약"""
        prompt = f"""
        Summarize the core contribution of this paper in ONE SINGLE Korean sentence, like a TL;DR.
        Title: {paper.get('title', 'N/A')}
        Abstract: {paper.get('summary', 'N/A')}
        """
        return self._make_request("one_liner", prompt)

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
                data = json.loads(response_content)
                predicted = data.get("predicted_slot")
                if predicted in ["Mechanism", "Clinical", "Methods"]:
                    logger.info(f"   🤖 Slot Verified: {current_slot} -> {predicted}")
                    return predicted
            except json.JSONDecodeError:
                pass
        
        logger.warning("   ⚠️ Classification verification failed. Keeping original slot.")
        return current_slot

    def tag_paper(self, paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Hybrid Tagging: Extraction (Hard) + Generation (Soft)"""
        from src.schemas import PaperTagging # Delayed import to avoid circular dependency if any

        prompt = f"""
        Perform Hybrid Tagging for this research paper.
        
        1. **Analysis**: Understand the main topic, species used, and key findings.
        2. **Soft Tagging (Generation)**: Generate **at least 3 keywords** (Soft Tags).
           - **Format**: `#Category/Subcategory` or `#Concept` (Obsidian style).
           - **STRICT FORMATTING**: 
             - Use **Forward Slash (/)** for hierarchy (e.g., `#Medicine/Neurology`). **DO NOT** use `>`.
             - **NO SPACES**: Use `CamelCase` or `snake_case` (e.g., `#ClinicalTrial`, `#Alzheimers_Disease`).
             - **NO Special Characters**: Remove `&`, `:`.
           - **Authority**: Use standard MeSH terms adapted to this format.
           - **Hierarchy**: Include at least one broad category tag (e.g., `#Medicine/Neurology`).
           - **No Repeats**: **DO NOT** use words that already appear in the **TITLE**. Add NEW context.
           - **FAIL-SAFE**: Even if hard extraction fails, YOU MUST GENERATE SOFT TAGS.
           
        3. **Hard Tagging (Extraction)**: Extract exact values if present. If not found, use null.
           - 'species': 'mouse', 'human', etc.
           - 'sample_size': n number (integer)
           - 'model': e.g., '5xFAD', 'HeLa'

        4. **Evidence & Confidence (Mandatory)**:
           - **evidence_span**: Quote the EXACT sentence or phrase from the abstract/title that justifies your tags.
           - **confidence**: A score between 0.0 and 1.0 indicating how sure you are about the tags and classification.
        
        Return JSON ONLY in the following format:
        {{
            "hard_tags": {{
                "species": "mouse",
                "sample_size": 20,
                "model": "5xFAD" 
            }}, 
            "soft_tags": ["#Medicine/Neurology", "#DietaryFats", "#CognitiveDysfunction"],
            "evidence_span": "We observed that 5xFAD mice showed improved...",
            "confidence": 0.95,
            "reasoning": "Brief reasoning..."
        }}
        
        Rules:
        - If 'hard_tags' are not found, return dictionary with null values.
        - **'soft_tags' MUST NOT be empty and MUST START WITH #.**
        - **NEVER return an empty list for 'soft_tags'.**
        
        Paper:
        - Title: {paper.get('title', 'N/A')}
        - Abstract: {paper.get('summary', 'N/A')}
        """
        
        response_content = self._make_request("tagging", prompt, is_json=True)
        
        if response_content:
            try:
                data = json.loads(response_content)
                # Validation
                tagging_result = PaperTagging(**data)
                return tagging_result.model_dump()
            except Exception as e:
                logger.error(f"Error parsing tagging result: {e}")
        
        return None

    def evaluate_escalation(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """Escalation Gate: Re-evaluate 'Pending Review' papers with a stricter Judge logic."""
        prompt = f"""
        You are a Senior Editor for a prestigious Neuroscience journal.
        Your subordinate has flagged this paper as "Pending Review" (Medium Confidence).
        
        Your Task: Determine if this paper is CLEARLY relevant and high-quality enough to be **Auto-Approved** immediately, bypassing further human review.
        
        Paper:
        - Title: {paper.get('title', 'N/A')}
        - Abstract: {paper.get('summary', 'N/A')}
        - Current Tags: {paper.get('tags', [])}
        
        Criteria for Auto-Approval (Escalation):
        1. **Clear Relevance**: The paper explicitly addresses the core topics (e.g., Ketosis, MCI, Alzheimer's, or specific methods).
        2. **High Quality/Significance**: The findings appear robust and significant based on the abstract.
        3. **No Red Flags**: No ambiguity about species, methods, or critical flaws.
        
        Return JSON STRICTLY:
        {{
            "approved": boolean, // True if upgraded to Auto-Approved
            "new_confidence": float, // Re-scored confidence (e.g., 0.95 if approved)
            "reason": "String explaining the decision (max 1 sentence)"
        }}
        """
        
        response_content = self._make_request("escalation", prompt, is_json=True)
        
        if response_content:
            try:
                data = json.loads(response_content)
                return {
                    "approved": data.get("approved", False),
                    "new_confidence": data.get("new_confidence", 0.0),
                    "reason": data.get("reason", "No reason provided")
                }
            except json.JSONDecodeError:
                logger.warning("Failed to parse Escalation Judge response.")
        
        return {"approved": False, "reason": "Judge Error"}

def get_llm_provider(config: LLMConfig) -> Optional[LLMProvider]:
    """설정에 맞는 LLM 공급자 인스턴스를 반환"""
    if config.provider == "openai":
        return OpenAIProvider(config)
    # 다른 프로바이더 (e.g., "anthropic")가 추가될 경우 여기에 로직을 구현
    return None
