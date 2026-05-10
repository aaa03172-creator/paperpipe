import logging
from typing import List, Any
from copy import deepcopy
from src.profiles.profile_schema import Profile, QuerySpec
from src.profiles.patch_schema import PatchRequest, PatchOp

logger = logging.getLogger(__name__)

ALLOWED_PATHS = {
    "query.must", "query.should", "query.must_not",
    "limits.max_results_per_run", "limits.date_window_days",
    "enabled", "schedule", "notes"
}

def _get_target(obj: Any, path: str):
    """"Helper: Traverse dot-notation path to get (parent, field_name)."""
    parts = path.split('.')
    current = obj
    for part in parts[:-1]:
        if hasattr(current, part):
            current = getattr(current, part)
        elif isinstance(current, dict):
            current = current[part]
        else:
            return None, None
    return current, parts[-1]

def apply_patch(original_profile: Profile, request: PatchRequest) -> Profile:
    """
    Applies a list of operations to a profile deterministically.
    Returns a NEW Profile object (does not mutate original in-place).
    """
    if original_profile.id != request.target_profile_id:
        raise ValueError(f"Patch ID mismatch: {request.target_profile_id} vs {original_profile.id}")

    # Work on a copy
    profile = original_profile.model_copy(deep=True)

    for op in request.ops:
        if op.path not in ALLOWED_PATHS:
            logger.warning(f"Skipping disallowed path: {op.path}")
            continue

        parent, field = _get_target(profile, op.path)
        if parent is None:
            logger.warning(f"Path not found: {op.path}")
            continue

        current_val = getattr(parent, field)

        if op.op == "add":
            # List append
            if isinstance(current_val, list):
                if op.value not in current_val:
                    current_val.append(op.value)
            else:
                 logger.warning(f"Cannot 'add' to non-list field: {op.path}")

        elif op.op == "remove":
            # List remove
            if isinstance(current_val, list):
                if op.value in current_val:
                    current_val.remove(op.value)
            else:
                 logger.warning(f"Cannot 'remove' from non-list field: {op.path}")

        elif op.op == "replace":
            # Scalar replacement
            # Basic type checking could be added here
            setattr(parent, field, op.value)

        elif op.op == "toggle":
            # Boolean toggle
             if isinstance(current_val, bool):
                 setattr(parent, field, not current_val)
             else:
                 logger.warning(f"Cannot 'toggle' non-bool field: {op.path}")

    return profile
