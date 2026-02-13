from typing import List, Optional, Any, Literal, Union
from pydantic import BaseModel, Field

class PatchOp(BaseModel):
    op: Literal["add", "remove", "replace", "toggle"]
    path: str = Field(..., description="Dot-notation path, e.g., 'query.must'")
    value: Optional[Union[str, int, bool, List[str]]] = None
    rationale: str = Field(..., description="Why is this change being made?")

class PatchRequest(BaseModel):
    target_profile_id: str
    ops: List[PatchOp] = Field(default_factory=list)
    meta: Optional[dict] = None
