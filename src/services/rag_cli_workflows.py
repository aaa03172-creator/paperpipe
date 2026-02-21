from __future__ import annotations

from rich.console import Console

from src.agents.adapter import OllamaModelAdapter
from src.agents.indexer_agent import IndexerAgent
from src.config import load_config


def ask_question_workflow(question: str, console: Console) -> None:
    config = load_config()
    if not config.agents.enabled:
        console.print("[yellow]⚠️ Agents are disabled in config.[/yellow]")
        return

    console.print(f"[bold cyan]🤔 User: {question}[/bold cyan]")
    try:
        indexer = IndexerAgent(collection_name="paperpipe_rag")
        with console.status("[bold green]🔍 Searching Knowledge Base...[/bold green]"):
            docs = indexer.query(question, n_results=5)

        if not docs:
            console.print("[red]❌ No relevant documents found.[/red]")
            return

        console.print(f"   📄 Found {len(docs)} relevant chunks.")

        context = "\n\n".join(docs)
        prompt = f"""
You are a helpful research assistant for the PaperPipe system.
Answer the user's question based ONLY on the provided context from scientific papers.
If the answer is not in the context, say "I cannot find the answer in the indexed papers."

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""
        adapter = OllamaModelAdapter(model_name=config.agents.main_model)
        with console.status("[bold green]🧠 Thinking...[/bold green]"):
            result = adapter.generate(prompt)

        console.print(f"\n[bold]🤖 Answer:[/bold]\n{result.text}\n")
    except Exception as exc:
        console.print(f"[bold red]❌ Error: {exc}[/bold red]")
        import traceback

        traceback.print_exc()
