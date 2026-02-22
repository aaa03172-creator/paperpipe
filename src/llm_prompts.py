from __future__ import annotations

from typing import Any, Dict, Optional


def build_trial_extraction_prompt(
    paper: Dict[str, Any],
    methods_snippet: str,
    schema_json: str,
) -> str:
    return f"""
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


def build_deep_read_prompt(paper: Dict[str, Any]) -> str:
    slot = str(paper.get("slot", "")).lower()
    if slot == "methods":
        return f"""
            Analyze this METHODOLOGY paper for a neuroscientist.
            Title: {paper.get('title', 'N/A')}
            Abstract: {paper.get('summary', 'N/A')}
            
            Provide a structured report in Korean (Markdown):
            0. **[독창성 요약] (Triage 4-Step)**
               - **배경 (Context)**: 이 연구 분야의 일반적 배경.
               - **기존 한계 (Gap)**: 기존 연구들이 해결하지 못한 결정적 질문.
               - **이 연구의 접근 (This Paper)**: 이 논문이 그 질문을 어떻게 다루는가.
            
            1. **기술의 핵심 (Core Technique)**: What is the main method/protocol?
            2. **주요 프로토콜 및 팁 (Key Protocol & Tips)**: Critical steps, reagents, or troubleshooting advice mentioned.
            3. **장점 및 혁신성 (Advantages & Innovation)**: Why is it better than existing methods?
            4. **한계 및 주의점 (Limitations & Caveats)**: What are the constraints or potential pitfalls?
            5. **적용 분야 (Applications)**: How can this be applied in neuroscience?
            """
    if slot == "mechanism":
        return f"""
            Analyze this MECHANISTIC paper for a neuroscientist.
            Title: {paper.get('title', 'N/A')}
            Abstract: {paper.get('summary', 'N/A')}
            
            Provide a structured report in Korean (Markdown):
            0. **[독창성 요약] (Triage 4-Step)**
               - **배경 (Context)**: 이 연구 분야의 일반적 배경.
               - **기존 한계 (Gap)**: 기존 연구들이 해결하지 못한 결정적 질문.
               - **이 연구의 접근 (This Paper)**: 이 논문이 그 질문을 어떻게 다루는가.
               
            1. **핵심 가설 (Hypothesis)**: What are they testing?
            2. **주요 메커니즘 (Key Mechanism)**: Detailed pathway/molecule interactions (e.g., A -> B -> C).
            3. **실험 결과 (Key Results)**: Main findings supporting the mechanism.
            4. **의의 (Implications)**: Impact on the field.
            """
    return f"""
            Analyze this paper for a neuroscientist.
            Title: {paper.get('title', 'N/A')}
            Abstract: {paper.get('summary', 'N/A')}
            
            Provide a structured report in Korean (Markdown):
            0. **[독창성 요약]** (Context -> Gap -> Paper)
               - **배경 (Context)**: 이 연구 분야의 일반적 배경.
               - **기존 한계 (Gap)**: 기존 연구들이 해결하지 못한 결정적 질문.
               - **이 연구의 접근 (This Paper)**: 이 논문이 그 질문을 어떻게 다루는가.
            1. **핵심 발견 (Key Findings)**
            2. **방법론적 특징 (Methodology)**
            3. **의의 및 한계 (Implications & Limitations)**
            """


def build_one_liner_prompt(paper: Dict[str, Any]) -> str:
    return f"""
        Summarize the core contribution of this paper in ONE SINGLE Korean sentence, like a TL;DR.
        Title: {paper.get('title', 'N/A')}
        Abstract: {paper.get('summary', 'N/A')}
        """


def build_slot_classification_prompt(paper: Dict[str, Any], current_slot: str) -> str:
    return f"""
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


def build_tagging_prompts(
    paper: Dict[str, Any],
    entity_aliases: Optional[Dict[str, str]] = None,
) -> tuple[str, str]:
    alias_prompt_section = ""
    if entity_aliases:
        alias_list = "\n".join(
            [f"- '{alias}' -> '{standard}'" for alias, standard in entity_aliases.items()]
        )
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
    full_text = paper.get("full_text")
    if full_text:
        snippet = full_text[:20000]
        user_prompt += f"\n- Full Text Content (First 20k chars):\n{snippet}\n"

    return system_prompt, user_prompt


def build_escalation_prompt(paper: Dict[str, Any]) -> str:
    return f"""
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


def build_relevance_analysis_prompt(paper: Dict[str, Any], rq: str) -> str:
    return f"""
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
