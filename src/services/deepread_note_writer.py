import re

from src.schemas.agent_artifacts import ClaimSet, StatsReport


DEEPREAD_HEADER = "## 🤖 Agent Deep Read"
STATS_HEADER = "### 🧪 Stats Verification"
DEEPREAD_SECTION_RE = re.compile(
    r"^## 🤖 Agent Deep Read\s*\n.*?(?=^## (?!🧪 Stats Verification).+|\Z)",
    re.MULTILINE | re.DOTALL,
)


def build_stats_markdown(stats_report: StatsReport) -> str:
    stats_md = f"\n{STATS_HEADER}\n"
    for check in stats_report.checks:
        icon = "✅" if check.verdict == "verified" else "🚨" if check.verdict == "inconsistent" else "⚠️"
        stats_md += f"#### Check: {check.test_type} {icon}\n"
        stats_md += f"- **Hypothesis**: {check.hypothesis or 'N/A'}\n"
        if check.decision_error:
            stats_md += (
                f"- **CRITICAL**: Decision Error Detected! (Computed p={check.computed_p} "
                f"vs Reported p={check.reported_p})\n"
            )
        else:
            stats_md += f"- **Verdict**: {check.verdict}\n"
            stats_md += f"- **Reported**: p={check.reported_p}\n"
            stats_md += f"- **Computed**: p={check.computed_p}\n"
        stats_md += f"- **Code Execution**:\n```python\n{check.code}\n```\n"
        stats_md += f"- **Output**:\n```text\n{check.outputs}\n```\n"
    return stats_md


def build_deepread_markdown(model_name: str, claims_set: ClaimSet, stats_md: str = "") -> str:
    md_output = f"{DEEPREAD_HEADER}\n"
    md_output += f"**Analyzed via {model_name}**\n\n"

    for i, claim in enumerate(claims_set.claims, 1):
        icon = "✅" if claim.confidence > 0.8 else "⚠️"
        md_output += f"### {i}. {claim.statement} {icon}\n"
        md_output += f"- **Type**: {claim.type}\n"
        md_output += f"- **Confidence**: {claim.confidence}\n"
        if claim.evidence_spans:
            span = claim.evidence_spans[0]
            evidence_text = span.quote if span.quote else span.raw_text
            badge = span.confidence_band or "hold"
            page = _display_page_number(span.page)
            if page is not None:
                md_output += f"- **Evidence**: \"{evidence_text}\" [p.{page}] ({badge})\n"
            else:
                md_output += (
                    f"- **Evidence**: \"{evidence_text}\" (p.? | {badge} | next: search quote in source)\n"
                )
        if claim.limitations:
            md_output += f"- **Limitations**: {', '.join(claim.limitations)}\n"
        md_output += "\n"

    if stats_md:
        md_output += stats_md
    return md_output


def upsert_deepread_section(content: str, new_section: str) -> str:
    """Replace all Deep Read sections with the latest section while preserving non-target content."""
    section = new_section.strip() + "\n"
    matches = list(DEEPREAD_SECTION_RE.finditer(content))
    if not matches:
        base = content.rstrip()
        if not base:
            return section
        return f"{base}\n\n{section}"

    first = matches[0]
    out = [content[: first.start()], section]
    cursor = first.end()
    for m in matches[1:]:
        out.append(content[cursor : m.start()])
        cursor = m.end()
    out.append(content[cursor:])
    return "".join(out)


def _display_page_number(page: int | None) -> int | None:
    if page is None:
        return None
    if page <= 0:
        return 1
    return page
