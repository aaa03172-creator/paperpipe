import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _is_truthy_assertion_value(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return False


def check_retraction(doi: str, email: str = None) -> Dict[str, Any]:
    """
    Check if a paper is retracted using Crossref API.
    
    Args:
        doi: The DOI of the paper.
        email: Email for Crossref Polite Pool (recommended).

    Returns:
        Dict with keys:
        - is_retracted (bool): True if retracted.
        - retraction_details (str): Details identifying the update type (e.g. "Retracted", "Correction").
    """
    if not doi:
        return {"is_retracted": False, "retraction_details": None}

    # Clean DOI just in case
    doi_clean = doi.replace("https://doi.org/", "").strip()
    url = f"https://api.crossref.org/works/{doi_clean}"
    
    headers = {}
    if email:
        headers["User-Agent"] = f"PaperPipe/1.0 (mailto:{email})"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 404:
            logger.warning(f"DOI not found in Crossref: {doi}")
            return {"is_retracted": False, "retraction_details": None}
            
        response.raise_for_status()
        data = response.json()
        item = data.get("message", {})
        
        # 1. Check 'update-to' field (Primary method for updates/retractions)
        # This list contains updates *to* this work, or if this work is an update *to* another.
        # Actually, for a retracted paper, we look if there are updates *pointing to it* saying it is retracted?
        # WAIT. Crossref 'update-to' is roughly:
        # If I am the retraction notice, I have an 'update-to' field pointing to the original paper.
        # If I am the original paper, I might have 'is-retracted' : true assertion?
        # Crossref strategy:
        # "Crossref Retraction Watch data is integrated."
        # We should check assertions?
        
        # Simplified Check Strategy based on Crossref metadata:
        # 1. Check 'is-retracted' assertion (if available from Retraction Watch integration)
        # 2. Check 'update-policy' or 'updates'?
        
        # Let's look for "is-retracted" in assertions.
        # Reference: https://www.crossref.org/blog/retraction-watch-retractions-now-in-the-crossref-api/
        # "Filter by is-retracted:true"
        # In the work metadata, it's under `assertions`.
        
        is_retracted = False
        details = []

        # Check Assertions (Retraction Watch integration)
        assertions = item.get("assertions", [])
        for assertion in assertions:
            if assertion.get("name") == "is-retracted" and _is_truthy_assertion_value(assertion.get("value")):
                is_retracted = True
                details.append("Retraction Watch: IS_RETRACTED")
                break
        
        # Also check if it is an "update" type itself? No, we are checking the paper.
        # But if the paper IS the retraction notice, we usually don't want to process it as a paper?
        # Ideally we want to know if the paper *V* has been retracted.
        
        # Also check for "updates" field in the work.
        # "updates" list in the response for the original work.
        if "updates" in item:
            for update in item["updates"]:
                up_type = update.get("type")
                if up_type in ["retraction", "withdrawal", "removal"]:
                    is_retracted = True
                    details.append(f"Crossref Update: {up_type}")
                elif up_type == "correction":
                    details.append(f"Crossref Update: {up_type}")

        if is_retracted:
            return {
                "is_retracted": True, 
                "retraction_details": "; ".join(details) if details else "Retracted (Unspecified)"
            }
        
        if details:
             # Not retracted but has updates (e.g. correction)
             return {
                 "is_retracted": False,
                 "retraction_details": "; ".join(details)
             }

        return {"is_retracted": False, "retraction_details": None}

    except Exception as e:
        logger.warning(f"Crossref check failed for {doi}: {e}")
        # Fail safe -> Assume not retracted rather than blocking
        return {"is_retracted": False, "retraction_details": "Check Failed"}
