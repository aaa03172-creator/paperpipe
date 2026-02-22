import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from src.cli_commands import register_commands
from src.config import load_config
from src.db_utils import (
    DB_PATH as DB_UTILS_PATH,
    init_db as init_jobs_db,
    init_run_stats_table,
)
from src.logger import setup_logging
from src.services.cli_system_workflows import organize_workflow
from src.services.cli_workflows import run_deepread_workflow
from src.services.rag_cli_workflows import ask_question_workflow

load_dotenv()

if os.getenv("OPENAI_API_KEY"):
    clean_key = os.getenv("OPENAI_API_KEY").strip().replace("\n", "").replace("\r", "")
    os.environ["OPENAI_API_KEY"] = clean_key

app = typer.Typer(no_args_is_help=True)
console = Console()

try:
    config_initial = load_config()
    log_level = config_initial.system.log_level
except Exception:
    log_level = "INFO"

logger = setup_logging(log_level=log_level)


def bootstrap_database() -> Path:
    """Initialize canonical runtime schema (papers/review_queue/jobs/run_stats)."""
    from scripts.init_db import init_db as init_core_db

    init_core_db()
    init_jobs_db()
    init_run_stats_table()
    return DB_UTILS_PATH


@app.callback()
def main():
    """PaperPipe Automation Tool"""
    pass


def organize(target_dir: str = "."):
    """Compatibility wrapper for tests/scripts importing src.cli.organize."""
    organize_workflow(target_dir, console)


def deepread(identifier: str, verify: bool = False):
    """Compatibility wrapper for tests/scripts importing src.cli.deepread."""
    run_deepread_workflow(identifier, verify, console)


def ask(question: str):
    """Compatibility wrapper for tests/scripts importing src.cli.ask."""
    ask_question_workflow(question, console)


register_commands(
    app,
    console=console,
    logger=logger,
    bootstrap_database=bootstrap_database,
    db_utils_path=DB_UTILS_PATH,
)


if __name__ == "__main__":
    app()
