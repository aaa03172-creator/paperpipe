from typing import List, Optional, Dict, Literal, Any
from pydantic import BaseModel, Field

class QuerySpec(BaseModel):
    """Structured boolean query definition."""
    must: List[str] = Field(default_factory=list, description="AND terms (All required)")
    should: List[str] = Field(default_factory=list, description="OR terms (At least one required if list not empty)")
    must_not: List[str] = Field(default_factory=list, description="NOT terms (None allowed)")

    def to_boolean_string(self) -> str:
        """Converts robust structure to legacy boolean string."""
        parts = []
        if self.must:
            # (A AND B AND C)
            must_group = " AND ".join([f'"{t}"' if " " in t else t for t in self.must])
            parts.append(f"({must_group})")
        
        if self.should:
             # (X OR Y OR Z)
             should_group = " OR ".join([f'"{t}"' if " " in t else t for t in self.should])
             parts.append(f"({should_group})")
             
        if self.must_not:
            # NOT (P OR Q)
            not_group = " OR ".join([f'"{t}"' if " " in t else t for t in self.must_not])
            parts.append(f"NOT ({not_group})")
            
        return " AND ".join(parts)

class Limits(BaseModel):
    max_results_per_run: int = Field(default=30, ge=1, le=100)
    date_window_days: int = Field(default=365, ge=1)

class Profile(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    title: str
    enabled: bool = True
    schedule: Literal["daily", "weekly", "manual"] = "daily"
    limits: Limits = Field(default_factory=Limits)
    query: QuerySpec = Field(default_factory=QuerySpec)
    notes: Optional[str] = None
    
class ProfileConfig(BaseModel):
    profiles: List[Profile] = Field(default_factory=list)
    defaults: Dict[str, Any] = Field(default_factory=dict)
