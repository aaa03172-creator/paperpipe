from __future__ import annotations

from src.services.cli_system_health_workflows import (
    clear_logs_workflow,
    doctor_workflow,
    reset_workflow,
    test_unpaywall_workflow,
)
from src.services.cli_system_watch_library_workflows import (
    organize_workflow,
    stats_workflow,
    watch_downloads_workflow,
    watch_workflow,
)

__all__ = [
    "doctor_workflow",
    "clear_logs_workflow",
    "reset_workflow",
    "test_unpaywall_workflow",
    "watch_workflow",
    "watch_downloads_workflow",
    "organize_workflow",
    "stats_workflow",
]
