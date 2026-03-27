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
    "synapse", "hippocampus",
    "tumor", "cancer", "carcinoma", "oncology", "metastasis",
    "immune", "immunology", "t cell", "tcell", "b cell", "bcell", "macrophage", "cytokine", "inflammation",
    "cell", "organoid", "fibroblast", "hepatocyte", "epithelium", "biomarker", "patient", "clinical",
    "biomaterial", "scaffold", "hydrogel", "drug delivery", "nanoparticle", "implant", "tissue engineering",
}

def validate_profile(profile: Profile, anchor_terms: set[str] | None = None) -> List[str]:
    """
    Checks profile against risk rules.
    Returns a list of error strings. Empty list means VALID.
    """
    errors = []
    effective_anchor_terms = set(ANCHOR_TERMS)
    if anchor_terms:
        effective_anchor_terms.update(term.lower() for term in anchor_terms if term)
    
    # Rule 1: Anchor Requirement
    # If query.must contains a BROAD term, it MUST also contain an ANCHOR term
    # UNLESS there is a specific exclusion in must_not
    
    has_broad = any(t.lower() in BROAD_TERMS for t in profile.query.must)
    has_anchor = any(t.lower() in effective_anchor_terms for t in profile.query.must)
    has_exclusion = len(profile.query.must_not) > 0 # Simple check for now
    
    if has_broad and not has_anchor and not has_exclusion:
        errors.append(
            "RISK: Broad terms detected without biomedical anchors. "
            "Add a domain anchor (for example tumor, immune, microglia, organoid, biomaterial) "
            "or specific exclusions."
        )

    return errors
