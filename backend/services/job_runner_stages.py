"""Compatibility bridge for stage modules.

This module keeps the existing import path stable while the stage
implementations live in split modules under backend.services.job_stages.
"""

from backend.services.job_stages import (
    run_ingest_stage,
    run_index_stage,
    run_read_stage,
    run_verify_stage,
)

__all__ = [
    "run_ingest_stage",
    "run_index_stage",
    "run_read_stage",
    "run_verify_stage",
]
