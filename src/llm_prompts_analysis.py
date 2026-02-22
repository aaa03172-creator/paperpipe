from __future__ import annotations

from typing import Any, Dict


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
