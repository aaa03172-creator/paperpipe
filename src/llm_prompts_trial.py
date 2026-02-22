from __future__ import annotations

from typing import Any, Dict


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
