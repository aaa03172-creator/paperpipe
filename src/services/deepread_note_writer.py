import re

from src.schemas.core import BiomedicalClinicalExtraction
from src.schemas.agent_artifacts import ClaimSet, StatsReport
from src.schemas.claimset_coverage import ClaimsetCoverageSidecar


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
        if check.notes:
            stats_md += f"- **Notes**: {check.notes}\n"
        stats_md += f"- **Code Execution**:\n```python\n{check.code}\n```\n"
        stats_md += f"- **Output**:\n```text\n{check.outputs}\n```\n"
    return stats_md


def build_clinical_extraction_markdown(extraction: BiomedicalClinicalExtraction) -> str:
    population_parts = []
    if extraction.population.condition:
        population_parts.append(extraction.population.condition)
    if extraction.population.cohort_description:
        population_parts.append(extraction.population.cohort_description)
    if extraction.population.n_total > 0:
        population_parts.append(f"n={extraction.population.n_total}")
    population_line = ", ".join(population_parts) or "Not detailed"

    intervention_parts = []
    if extraction.intervention.name:
        intervention_parts.append(extraction.intervention.name)
    if extraction.intervention.category != "unknown":
        intervention_parts.append(extraction.intervention.category.replace("_", " ").title())
    if extraction.intervention.dose:
        intervention_parts.append(extraction.intervention.dose)
    elif extraction.intervention.schedule:
        intervention_parts.append(extraction.intervention.schedule)
    if extraction.intervention.duration_weeks > 0:
        intervention_parts.append(f"{extraction.intervention.duration_weeks} weeks")
    intervention_line = ", ".join(intervention_parts) or "Not detailed"

    primary_outcomes = ", ".join(
        endpoint.name for endpoint in extraction.outcomes.primary[:3] if endpoint.name
    ) or "Not detailed"

    safety_line = "Not detailed"
    if extraction.safety_adherence.adverse_events_reported:
        safety_line = extraction.safety_adherence.adverse_events_summary or "Adverse events reported"
    elif extraction.outcomes.safety:
        safety_line = ", ".join(endpoint.name for endpoint in extraction.outcomes.safety[:3] if endpoint.name) or "Reported"

    followup_tag = extraction.eligibility_flags.followup_tag.replace("_", " ").title()

    return (
        "### 🏥 Clinical Extraction\n"
        f"- **Condition / Population**: {population_line}\n"
        f"- **Intervention**: {intervention_line}\n"
        f"- **Primary Outcomes**: {primary_outcomes}\n"
        f"- **Safety**: {safety_line}\n"
        f"- **Follow-Up Tag**: {followup_tag}\n\n"
    )


def _format_evidence_text_for_display(text: str) -> str:
    formatted = str(text or "")
    formatted = re.sub(r"([A-Za-z0-9])-\s*\n\s*([A-Za-z0-9])", r"\1\2", formatted)
    formatted = re.sub(r"\s*\n\s*", " ", formatted)
    formatted = re.sub(
        r"^[A-Za-z]?\d+(?:\s+[A-Za-z])*(?:\s+and\s+[A-Za-z])?\),\s*(?=(indicating that|these results showed that|suggesting that|suggested that))",
        "",
        formatted,
        flags=re.IGNORECASE,
    )
    formatted = re.sub(r"\s+", " ", formatted).strip()
    return formatted


def build_deepread_markdown(
    model_name: str,
    claims_set: ClaimSet,
    stats_md: str = "",
    clinical_md: str = "",
    coverage: ClaimsetCoverageSidecar | None = None,
) -> str:
    md_output = f"{DEEPREAD_HEADER}\n"
    md_output += f"**Analyzed via {model_name}**\n\n"
    coverage_md = build_coverage_review_markdown(coverage)
    if coverage_md:
        md_output += coverage_md

    if clinical_md:
        md_output += clinical_md

    for i, claim in enumerate(claims_set.claims, 1):
        icon = "✅" if claim.confidence > 0.8 else "⚠️"
        md_output += f"### {i}. {claim.statement} {icon}\n"
        md_output += f"- **Type**: {claim.type}\n"
        md_output += f"- **Confidence**: {claim.confidence}\n"
        if claim.evidence_spans:
            span = claim.evidence_spans[0]
            evidence_text = span.quote if span.quote else span.raw_text
            evidence_text = _format_evidence_text_for_display(evidence_text)
            section_name = span.section if span.section else "Page " + str(span.page)
            md_output += f"- **Evidence**: \"{evidence_text}\" (Section: {section_name})\n"
        if claim.limitations:
            md_output += f"- **Limitations**: {', '.join(claim.limitations)}\n"
        md_output += "\n"

    if stats_md:
        md_output += stats_md
    return md_output


def build_coverage_review_markdown(coverage: ClaimsetCoverageSidecar | None) -> str:
    if coverage is None or coverage.coverage_status == "pass":
        return ""
    missing_topics = [
        signal.label
        for signal in coverage.topic_signals
        if signal.present_in_document and not signal.covered_by_claimset
    ]
    parts = [
        "### Coverage Review",
        f"- **Status**: {coverage.coverage_status.upper()}",
        "- **Gate**: Advisory only",
        (
            f"- **Covered Pages**: {', '.join(str(page) for page in coverage.page_summary.covered_pages) or 'None'} "
            f"of {coverage.metrics.document_page_count or 'unknown'}"
        ),
    ]
    if coverage.page_summary.missing_page_ranges:
        parts.append(f"- **Undercovered Page Ranges**: {', '.join(coverage.page_summary.missing_page_ranges)}")
    if missing_topics:
        parts.append(f"- **Missing Topic Signals**: {', '.join(missing_topics[:4])}")
    if coverage.duplicate_warnings:
        parts.append(f"- **Near-Duplicate Claim Warnings**: {len(coverage.duplicate_warnings)}")
    parts.append(f"- **Evidence Grounding**: {coverage.evidence_summary.grounded_ratio:.0%} grounded")
    parts.append(f"- **Recommended Next Action**: {coverage.recommended_next_action.replace('_', ' ')}")
    return "\n".join(parts) + "\n\n"


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
