"""LLM helper for profile patch suggestions.

This module is separate from the Deep Read reasoning persona system in
`src.persona_modes.py`. It edits boolean search profiles and proposes audit
patches only.
"""

import logging
import json
from src.agents.adapter import OllamaModelAdapter
from src.profiles.profile_schema import Profile
from src.profiles.patch_schema import PatchRequest
from src.config import load_config

logger = logging.getLogger(__name__)

PROFILE_PATCH_ASSISTANT_PROMPT = """You are a profile patch assistant for a biomedical research database.
This helper is separate from the Deep Read reasoning persona system and should only produce search-profile edits.
Your job is to translate the user's natural language requests into precise JSON Patches to update Boolean search profiles (`must`, `must_not`, `should`, and limits).

Operating Rules:
1. **Extreme Caution (Prevent Explosions):** Never allow broad, ambiguous terms (e.g., 'tamoxifen', 'genotyping', 'mouse') without a specific biological anchor (e.g., 'microglia', 'CNS', 'brain'). If the user asks for a broad term, proactively add anchors to the `must` list or specific exclusions to the `must_not` list.
2. **Ontology Expansion (Domain Expert):** If the user suggests a basic biological/medical term, AUTOMATICALLY expand it to a robust Boolean OR group using MeSH terms and synonyms (e.g., if user says 'sleep', you add `(sleep OR insomnia OR circadian rhythm OR "sleep deprivation")`). Add this entire expanded string as the `value` in the patch.
3. **Pessimistic Limits:** If a query broadens significantly, prefer lowering `max_results_per_run` to prevent API exhaustion.
4. **Format Strictness:** You only speak in valid JSON representing the `PatchRequest` schema. No conversational filler. If the user's request is too ambiguous, use the `meta.risk_flags` array to state ["needs_user_choice"] and leave the `ops` list empty.

CURRENT PROFILE (JSON):
{profile_json}

USER REQUEST:
{user_request}

OUTPUT SCHEMA (JSON):
{{
    "target_profile_id": "{profile_id}",
    "ops": [
        {{ "op": "add|remove|replace|toggle", "path": "dot.path", "value": "value", "rationale": "reason" }}
    ],
    "meta": {{ "risk_flags": [] }}
}}
"""

PROFILE_AUDIT_PROMPT = """You are a profile audit assistant for a biomedical research database.
This helper is separate from the Deep Read reasoning persona system and should only produce search-profile fixes.
A search profile is consistently hitting its API limit (max_results_per_run), causing potential data loss (truncation).

Your Goal: Propose a PatchRequest to reduce result volume while maintaining relevance.
Strategies:
1. Narrow the query (add specific exclusions to `must_not` or stricter `must` terms).
2. Reduce the `date_window_days` limit (e.g. 365 -> 90).
3. Do NOT just increase `max_results_per_run` unless you are sure it's safe (default is unsafe).

CURRENT PROFILE:
{profile_json}

AUDIT DATA:
- Limit Hit Frequency: {hit_ratio:.1%} of runs in last {days} days.
- Current Limit: {current_limit}

OUTPUT SCHEMA (JSON):
Same as PatchRequest.
"""

class ProfileChatAgent:
    """Generate `PatchRequest` suggestions for profile editing flows only."""

    def __init__(self, model_name: str = None):
        self.config = load_config()
        # Default to llama3 if not specified
        self.model_name = model_name or (self.config.agents.main_model if self.config.agents else "llama3:latest")
        self.adapter = OllamaModelAdapter(model_name=self.model_name)

    def generate_patch(self, profile: Profile, user_request: str) -> PatchRequest:
        """
        Generates a PatchRequest based on the user's chat input.
        """
        prompt = PROFILE_PATCH_ASSISTANT_PROMPT.format(
            profile_json=profile.model_dump_json(),
            user_request=user_request,
            profile_id=profile.id
        )

        logger.info(f"🤖 Profile patch assistant thinking for profile '{profile.id}'...")
        
        try:
            # Force JSON mode
            response = self.adapter.generate(prompt, format="json", temperature=0.2)
            
            # Parse & Validate
            data = json.loads(response.text)
            patch = PatchRequest(**data)
            
            # Double check target ID
            if patch.target_profile_id != profile.id:
                logger.warning(f"Agent hallucinated profile ID: {patch.target_profile_id}. Correcting to {profile.id}")
                patch.target_profile_id = profile.id
                
            return patch
            
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON from agent")
            raise ValueError("Agent failed to produce valid JSON.")
        except Exception as e:
            logger.error(f"Agent error: {e}")
            raise

    def suggest_audit_fix(self, profile: Profile, hit_ratio: float, days: int) -> PatchRequest:
        """
        Generates a patch to fix a profile that is hitting limits effectively.
        """
        prompt = PROFILE_AUDIT_PROMPT.format(
            profile_json=profile.model_dump_json(),
            hit_ratio=hit_ratio,
            days=days,
            current_limit=profile.limits.max_results_per_run,
            profile_id=profile.id
        )

        logger.info(f"🤖 Profile audit assistant thinking for profile '{profile.id}'...")
        
        try:
            # Re-use adapter
            response = self.adapter.generate(prompt, format="json", temperature=0.2)
            data = json.loads(response.text)
            patch = PatchRequest(**data)
            
            # Ensure ID match
            if patch.target_profile_id != profile.id:
                patch.target_profile_id = profile.id
                
            return patch
        except Exception as e:
            logger.error(f"Audit Agent error: {e}")
            raise
