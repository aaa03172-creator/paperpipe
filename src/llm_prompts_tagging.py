from __future__ import annotations

from typing import Any, Dict, Optional


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
