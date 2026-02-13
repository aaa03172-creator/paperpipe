---
description: 
---

# Ticket Execution Workflow

When you are assigned a task (Ticket), follow these steps strictly:

## Step 1: Understand (Analysis)
- Read the **Master Spec** (`PaperPipe_Master_Spec.md`) related to the ticket.
- Identify which Python modules are affected.
- State the goal of this ticket in one sentence.

## Step 2: Plan (Pseudo-code)
- **Do NOT write code immediately.**
- Outline the logic in pseudo-code or comments.
- Ask yourself: "Does this plan violate any Master Rules (e.g., Zotero DB write)?"
- Plan how to handle errors (try/except blocks).

## Step 3: Implement (Coding)
- Write the code.
- Ensure all configurations are loaded from `config.yaml`.
- Apply Type Hints.

## Step 4: Verify & Log
- Did you add logging statements?
- Did you update the `schema/` if data structures changed?

## Step 5: Finalize
- Report "Task Complete" and summarize what files were created or modified.