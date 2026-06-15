from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


EvalPayloadClass = Literal["local_only", "lab_allowed", "external_allowed"]


def generated_at_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class EvalRunMetadata(BaseModel):
    schema_version: Literal["eval_run_metadata.v1"] = "eval_run_metadata.v1"
    harness: str
    run_id: str
    mode: str
    generated_at_utc: datetime = Field(default_factory=generated_at_utc)
    payload_class: EvalPayloadClass = "local_only"
    provider: str = "deterministic"
    model: str | None = None
    eval_id: str | None = None
    case_ids: list[str] = Field(default_factory=list)
    subset: str | None = None


def build_eval_run_metadata(
    *,
    harness: str,
    run_id: str,
    mode: str,
    payload_class: EvalPayloadClass = "local_only",
    provider: str = "deterministic",
    model: str | None = None,
    eval_id: str | None = None,
    case_ids: list[str] | None = None,
    subset: str | None = None,
) -> EvalRunMetadata:
    return EvalRunMetadata(
        harness=harness,
        run_id=run_id,
        mode=mode,
        payload_class=payload_class,
        provider=provider,
        model=model,
        eval_id=eval_id,
        case_ids=list(case_ids or []),
        subset=subset,
    )
