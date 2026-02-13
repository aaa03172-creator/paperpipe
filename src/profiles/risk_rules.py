from typing import List
from src.profiles.profile_schema import Profile

# Terms that are too broad on their own
BROAD_TERMS = {
    "tamoxifen", "genotyping", "cre-er", "cre-loxp", "mouse", "rat", "model",
    "protein", "gene", "expression", "therapy", "drug"
}

# Anchor terms that must be present if a broad term is used
ANCHOR_TERMS = {
    "brain", "cns", "neuron", "glia", "microglia", "astrocyte", 
    "neuroinflammation", "alzheimer", "parkinson", "neurodegeneration",
    "synapse", "cognitive", "memory", "hippocampus"
}

def validate_profile(profile: Profile) -> List[str]:
    """
    Checks profile against risk rules.
    Returns a list of error strings. Empty list means VALID.
    """
    errors = []
    
    # Rule 1: Anchor Requirement
    # If query.must contains a BROAD term, it MUST also contain an ANCHOR term
    # UNLESS there is a specific exclusion in must_not
    
    has_broad = any(t.lower() in BROAD_TERMS for t in profile.query.must)
    has_anchor = any(t.lower() in ANCHOR_TERMS for t in profile.query.must)
    has_exclusion = len(profile.query.must_not) > 0 # Simple check for now
    
    if has_broad and not has_anchor and not has_exclusion:
        errors.append(
            "RISK: Broad terms detected without Neuroscience Anchors. "
            f"Add one of {list(ANCHOR_TERMS)[:3]}... or specific exclusions."
        )

    return errors
