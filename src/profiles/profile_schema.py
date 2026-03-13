from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class QuerySpec(BaseModel):
    must: List[str] = Field(default_factory=list)
    should: List[str] = Field(default_factory=list)
    must_not: List[str] = Field(default_factory=list)


class Limits(BaseModel):
    max_results_per_run: int = Field(default=30, ge=1, le=100)
    date_window_days: int = Field(default=365, ge=1)


class Profile(BaseModel):
    id: str
    revision: int = Field(default=0, ge=0)
    title: str
    enabled: bool = True
    schedule: Literal["daily", "weekly", "manual"] = "daily"
    limits: Limits = Field(default_factory=Limits)
    query: QuerySpec = Field(default_factory=QuerySpec)
    notes: Optional[str] = None


class ProfileConfig(BaseModel):
    profiles: List[Profile] = Field(default_factory=list)
    defaults: Dict[str, Any] = Field(default_factory=dict)
