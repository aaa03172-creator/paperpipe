from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


class PatchOp(BaseModel):
    op: Literal["add", "remove", "replace", "toggle"]
    path: str = Field(...)
    value: Optional[Union[str, int, bool, List[str]]] = None
    rationale: str


class PatchRequest(BaseModel):
    target_profile_id: str
    ops: List[PatchOp] = Field(default_factory=list)
    meta: Optional[dict] = None
