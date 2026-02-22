from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.schemas.trial_models import TrialExtraction


def _population_summary(extraction: "TrialExtraction") -> str:
    pop_parts = []
    population = extraction.population
    if population.mci_only:
        pop_parts.append("MCI-only")
    else:
        desc = "Mixed/Other"
        details = []
        if population.subtype != "unknown":
            details.append(population.subtype)
        if population.comorbidity_notes:
            details.append(population.comorbidity_notes)
        if details:
            desc += f" ({', '.join(details)})"
        pop_parts.append(desc)

    if population.n_total > 0:
        pop_parts.append(f"n={population.n_total}")
    if population.age_mean > 0:
        pop_parts.append(f"age\u2248{population.age_mean:.1f}")
    if population.apoe4_reported and population.apoe4_percent > 0:
        pop_parts.append(f"APOE4+ {population.apoe4_percent:.0f}%")
    return ", ".join(pop_parts)


def _intervention_summary(extraction: "TrialExtraction") -> str:
    intervention = extraction.intervention
    int_parts = []
    if intervention.category != "unknown":
        cat_display = intervention.category.replace("_", " ").title()
        if intervention.product_name:
            cat_display += f" ({intervention.product_name})"
        int_parts.append(cat_display)
    elif intervention.product_name:
        int_parts.append(intervention.product_name)

    if intervention.dose_value > 0:
        unit = intervention.dose_unit.replace("_per_day", "/d") if intervention.dose_unit != "unknown" else ""
        int_parts.append(f"{intervention.dose_value:.1f}{unit}")
    elif intervention.dose_schedule:
        int_parts.append(intervention.dose_schedule)

    if intervention.duration_weeks > 0:
        int_parts.append(f"{intervention.duration_weeks} weeks")
    intervention_str = ", ".join(int_parts)

    if not intervention_str:
        if extraction.study_design.design in ["systematic_review", "meta_analysis"]:
            return "Systematic Review / Meta-analysis"
        if extraction.eligibility_flags.separate_analysis_tag != "unknown":
            tag_clean = extraction.eligibility_flags.separate_analysis_tag.replace("_", " ").title()
            return f"{tag_clean} (Unspecified details)"
        return "Not detailed"

    return intervention_str


def _cognition_summary(extraction: "TrialExtraction") -> str:
    cognition_outcomes = []
    for cognition in extraction.outcomes.cognition:
        text = cognition.name
        if cognition.effect_direction != "unknown":
            text += f" ({cognition.effect_direction})"
        if cognition.notes:
            text += f": {cognition.notes}"
        cognition_outcomes.append(text)
    return "; ".join(cognition_outcomes) if cognition_outcomes else "Not reported"


def _adl_summary(extraction: "TrialExtraction") -> str:
    return "Reported" if extraction.outcomes.adl_function else "Not reported"


def _safety_summary(extraction: "TrialExtraction") -> str:
    if not extraction.safety_adherence.adverse_events_reported:
        return "Not reported"
    return extraction.safety_adherence.adverse_events_summary or "Reported, no details"


def _ketone_summary(extraction: "TrialExtraction") -> str:
    if not extraction.ketone_confirmation.measured:
        return "No"
    metric = (
        f" ({extraction.ketone_confirmation.metric})"
        if extraction.ketone_confirmation.metric != "unknown"
        else ""
    )
    return f"Yes{metric}"


def _analysis_tag(extraction: "TrialExtraction") -> str:
    tag = extraction.eligibility_flags.separate_analysis_tag.replace("_", " ").title()
    return "General" if tag.lower() == "unknown" else tag


def build_trial_summary_block(extraction: "TrialExtraction") -> str:
    """Generate the Obsidian callout block for trial extraction summaries."""

    population_str = _population_summary(extraction)
    intervention_str = _intervention_summary(extraction)
    cognition_str = _cognition_summary(extraction)
    adl_str = _adl_summary(extraction)
    ae_summary = _safety_summary(extraction)
    ketone_str = _ketone_summary(extraction)
    tag = _analysis_tag(extraction)

    return f"""
> [!tldr]- Trial Summary
> **Population**: {population_str}
> **Intervention**: {intervention_str}
> **Outcomes**:
> - **Cognition**: {cognition_str}
> - **ADL/Function**: {adl_str}
> - **Safety/Adherence**: {ae_summary}
> **Ketone Confirmed**: {ketone_str}
> **Tag**: #{tag}
"""
