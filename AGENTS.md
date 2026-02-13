# PaperPipe Agentic Guidelines

## 1. Architectural Rules
- **API-First:** Core logic must be exposed via FastAPI. No hardcoded CLI-only paths.
- **Pydantic Contracts:** All agent inputs/outputs must strictly follow the Pydantic schemas in `src/schemas/`.
- **Idempotency:** Obsidian markdown generation must replace sections safely, not blindly append.

## 2. MCP & Cost Control Guardrails (CRITICAL)
If you are equipped with the Google Developer Knowledge MCP (or any external search tool):
- **Limit `search_documents`:** Maximum 2 calls per session.
- **Limit `get_document`:** Maximum 1 call per session (only fetch the single most relevant doc).
- **BANNED `batch_get_documents`:** Do NOT use this tool. It causes massive token bloat. If absolutely necessary, you must ask the user for explicit permission first.
- **Save Context:** Summarize findings internally; do not repeatedly fetch the same external docs.
