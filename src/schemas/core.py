"""
Pydantic 스키마 정의.
LLM에서 추출한 데이터의 유효성을 검사하고 타입을 강제하는 데 사용됩니다.
"""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Any, List, Literal, Optional, Union, Dict
from pathlib import Path
from enum import Enum

# --- Downloader Schemas ---
class DownloadFailure(str, Enum):
    NO_LINK = "no_link"
    RATE_LIMIT = "rate_limit"
    TEMP_FAIL = "temp_fail"
    PERM_FAIL = "perm_fail"
    POLICY_BLOCK = "policy_block"
    BAD_CONTENT = "bad_content"


class DownloadAttempt(BaseModel):
    provider: str
    timestamp: datetime = Field(default_factory=datetime.now)
    status: DownloadFailure
    candidate_url: Optional[str] = None
    message: Optional[str] = None
    retry_no: int = 0
    will_retry: bool = False


class DownloadCandidate(BaseModel):
    url: str
    source_name: str
    is_oa: bool
    confidence: float
    license: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

# --- Data Schemas ---

class PaperStatus(str, Enum):
    """
    Canonical status terms shared across gate decisions and DB status.
    """
    APPROVED = "APPROVED"
    PENDING_REVIEW = "PENDING_REVIEW"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"
    INDEXED = "INDEXED"
    # Backward-compatible alias used in legacy code/tests.
    AUTO_APPROVED = "APPROVED"

class ReadingStatus(str, Enum):
    """
    User-facing reading status for workflow management.
    """
    INBOX = "Inbox"
    READING = "Reading"
    DONE = "Done"

class Paper(BaseModel):
    """논문 정보를 담는 표준 스키마"""
    id: str = Field(description="Unique ID (DOI or timestamp based)")
    title: str
    authors: List[str]
    published: str
    source: str = Field(description="Source of the paper (Pubmed, ArXiv, etc)")
    summary: str
    link: str
    
    # [NEW] Meta-data for Action Gates
    processing_status: PaperStatus = Field(default=PaperStatus.PENDING_REVIEW, description="Current processing status based on confidence.")
    
    # [NEW] Integrity Check (Retraction Watch)
    is_retracted: bool = Field(default=False, description="True if the paper has been retracted")
    retraction_details: Optional[str] = Field(None, description="Details about retraction or correction")

    # [NEW] Escalation Gate
    is_escalated: bool = Field(default=False, description="True if auto-approved via escalation judge")
    escalation_reason: Optional[str] = Field(None, description="Reason for escalation approval")
    escalation_final_route: Optional[str] = Field(None, description="Structured escalation route when present.")
    escalation_in_biomedical_scope: Optional[bool] = Field(
        None,
        description="Whether the escalation judge considered the paper to be in biomedical scope.",
    )
    escalation_reason_codes: List[str] = Field(
        default_factory=list,
        description="Structured escalation reason codes when provided by the escalation judge.",
    )

    # [NEW] Ticket 7: Context-Aware Analysis
    relevance_analysis: Optional[Dict[str, str]] = None # {gap, insight, limitation}
    # [NEW] Bibliometric Data (Ticket 3)
    citation_count: Optional[int] = Field(None, description="Total citations from OpenAlex")
    impact_factor: Optional[float] = Field(None, description="Journal Impact Factor proxy (SJR)")
    journal_tier: Optional[str] = Field(None, description="Q1/Q2/Q3/Q4 or similar ranking")

    # [NEW] Ticket 8: Reading Status Tracking
    reading_status: ReadingStatus = Field(default=ReadingStatus.INBOX, description="User workflow status (Inbox, Reading, Done)")
    manual_rank_score: Optional[float] = Field(None, description="Final calculated rank score")
    download_attempts: List[DownloadAttempt] = Field(default_factory=list, description="PDF download attempts across providers")

    # Optional fields
    doi: Optional[str] = Field(default=None, description="DOI of the paper")
    pdf_link: Optional[str] = Field(default=None, description="Direct PDF URL")
    full_text: Optional[str] = None
    local_pdf_path: Optional[Path] = None

    @field_validator("processing_status", mode="before")
    @classmethod
    def normalize_processing_status(cls, v):
        """Accept legacy labels and normalize to canonical enum values."""
        if isinstance(v, PaperStatus):
            return v
        if isinstance(v, str):
            key = v.strip().upper().replace("-", "_").replace(" ", "_")
            legacy_map = {
                "AUTO_APPROVED": "APPROVED",
                "AUTOAPPROVED": "APPROVED",
                "APPROVED": "APPROVED",
                "PENDING_REVIEW": "PENDING_REVIEW",
                "PENDING": "PENDING_REVIEW",
                "QUARANTINED": "QUARANTINED",
                "FAILED": "FAILED",
                "INDEXED": "INDEXED",
            }
            if key in legacy_map:
                return PaperStatus(legacy_map[key])
        return v

# --- Nested Models ---

class Citation(BaseModel):
    title: str
    authors_first: str
    year: int = 0
    journal_or_server: str
    doi: Optional[str] = None
    url: Optional[str] = None

class StudyDesign(BaseModel):
    design: Literal["parallel_rct", "crossover_rct", "nonrandomized", "observational", "systematic_review", "meta_analysis", "other", "unknown"] = "unknown"
    blinding: Literal["double_blind", "single_blind", "open_label", "unknown"] = "unknown"
    control_type: Literal["placebo", "usual_care", "diet_control", "active_control", "none", "unknown"] = "unknown"
    setting: Literal["single_center", "multi_center", "unknown"] = "unknown"
    duration_weeks: int = 0
    followup_weeks: int = 0
    washout_weeks: int = 0

class Population(BaseModel):
    mci_only: bool = True
    mci_definition: Optional[str] = None
    subtype: Literal["amnestic", "non_amnestic", "mixed", "unknown"] = "unknown"
    n_total: int = 0
    n_intervention: int = 0
    n_control: int = 0
    age_mean: float = 0.0
    age_sd: float = 0.0
    sex_female_percent: float = 0.0
    apoe4_reported: bool = False
    apoe4_percent: float = 0.0
    comorbidity_notes: Optional[str] = None
    baseline_cognition_measure: Optional[str] = None

class Intervention(BaseModel):
    category: Literal["mct", "c8_caprylic", "c10_capric", "mct_mix", "ketone_salt", "ketone_ester", "ketogenic_diet", "other", "unknown"] = "unknown"
    product_name: Optional[str] = None
    dose_value: float = 0.0
    dose_unit: Literal["g_per_day", "ml_per_day", "mg_per_day", "unknown"] = "unknown"
    dose_schedule: Optional[str] = None
    duration_weeks: int = 0
    route: Literal["oral", "other", "unknown"] = "unknown"
    cointerventions: List[str] = []

class Comparator(BaseModel):
    description: Optional[str] = None
    dose_value: float = 0.0
    dose_unit: Literal["g_per_day", "ml_per_day", "mg_per_day", "unknown"] = "unknown"

class KetoneConfirmation(BaseModel):
    measured: bool = False
    metric: Literal["bHB", "acetoacetate", "ketones_unspecified", "unknown"] = "unknown"
    timepoints: List[str] = []
    result_summary: Optional[str] = None

class Outcome(BaseModel):
    name: str
    timepoint_weeks: int = 0
    effect_direction: Literal["improved", "worsened", "no_change", "mixed", "unknown"] = "unknown"
    effect_size_type: Literal["mean_change", "between_group_diff", "percent_change", "p_value_only", "unknown"] = "unknown"
    value: float = 0.0
    sd: float = 0.0
    p_value: Optional[str] = None
    notes: Optional[str] = None

class Outcomes(BaseModel):
    cognition: List[Outcome] = []
    adl_function: List[Outcome] = []
    biomarkers: List[Outcome] = []

class SafetyAdherence(BaseModel):
    adherence_reported: bool = False
    adherence_summary: Optional[str] = None
    adverse_events_reported: bool = False
    adverse_events_summary: Optional[str] = None
    dropout_n_total: int = 0
    dropout_reasons: List[str] = []

class RiskOfBiasHints(BaseModel):
    randomization_clear: bool = False
    allocation_concealment_clear: bool = False
    blinding_clear: bool = False
    attrition_low: bool = False
    selective_reporting_suspected: bool = False
    notes: Optional[str] = None

class EligibilityFlags(BaseModel):
    include_for_mci_mct_review: bool = True
    reason_if_excluded: Optional[str] = None
    separate_analysis_tag: Literal["primary_mct", "ketone_ester_or_salt", "ketogenic_diet", "mixed_population", "unknown"] = "unknown"

class ExtractionQuality(BaseModel):
    confidence: Literal["high", "medium", "low"] = "low"
    missing_fields: List[str] = []

class PaperTagging(BaseModel):
    """General Hybrid Tagging for all papers"""
    hard_tags: Dict[str, Union[str, int, float, None]] = Field(description="Exact values extracted from text (e.g. sample_size, species)")
    soft_tags: List[str] = Field(description="Contextual tags generated by AI (e.g. #autophagy, #prevention)")
    evidence_span: Optional[str] = Field(None, description="The exact sentence or fragment from text that justifies the tags.")
    confidence: float = Field(0.0, description="Model's confidence score (0.0 to 1.0).")
    reasoning: Optional[str] = None

# --- Main Schema ---

class BiomedicalPopulation(BaseModel):
    condition: Optional[str] = None
    cohort_description: Optional[str] = None
    inclusion_criteria: List[str] = Field(default_factory=list)
    exclusion_criteria: List[str] = Field(default_factory=list)
    n_total: int = 0
    n_intervention: int = 0
    n_control: int = 0
    age_mean: float = 0.0
    age_sd: float = 0.0
    sex_female_percent: float = 0.0
    notes: Optional[str] = None


class BiomedicalIntervention(BaseModel):
    category: Literal[
        "small_molecule",
        "biologic",
        "cell_therapy",
        "gene_therapy",
        "device",
        "procedure",
        "diet",
        "behavioral",
        "biomaterial",
        "combination",
        "diagnostic",
        "other",
        "unknown",
    ] = "unknown"
    name: Optional[str] = None
    dose: Optional[str] = None
    route: Optional[str] = None
    schedule: Optional[str] = None
    duration_weeks: int = 0
    cointerventions: List[str] = Field(default_factory=list)


class BiomedicalComparator(BaseModel):
    category: Literal["placebo", "usual_care", "active_control", "historical_control", "none", "other", "unknown"] = "unknown"
    description: Optional[str] = None


class BiomedicalEndpoint(BaseModel):
    name: str
    domain: Literal[
        "primary",
        "secondary",
        "safety",
        "biomarker",
        "quality_of_life",
        "function",
        "survival",
        "pharmacokinetics",
        "feasibility",
        "other",
        "unknown",
    ] = "unknown"
    timepoint_weeks: int = 0
    effect_direction: Literal["improved", "worsened", "no_change", "mixed", "not_applicable", "unknown"] = "unknown"
    result_summary: Optional[str] = None
    effect_size: Optional[str] = None
    p_value: Optional[str] = None
    notes: Optional[str] = None


class BiomedicalOutcomes(BaseModel):
    primary: List[BiomedicalEndpoint] = Field(default_factory=list)
    secondary: List[BiomedicalEndpoint] = Field(default_factory=list)
    biomarkers: List[BiomedicalEndpoint] = Field(default_factory=list)
    safety: List[BiomedicalEndpoint] = Field(default_factory=list)


class BiomedicalSafetyAdherence(BaseModel):
    adherence_reported: bool = False
    adherence_summary: Optional[str] = None
    adverse_events_reported: bool = False
    adverse_events_summary: Optional[str] = None
    serious_adverse_events: Optional[str] = None
    dropout_n_total: int = 0
    dropout_reasons: List[str] = Field(default_factory=list)


class BiomedicalEligibilityFlags(BaseModel):
    is_human_clinical_study: bool = True
    fits_biomedical_scope: bool = True
    reason_if_excluded: Optional[str] = None
    followup_tag: Literal["therapeutic", "diagnostic", "device", "biomarker", "observational", "mixed", "other", "unknown"] = "unknown"


class BiomedicalExtractionQuality(BaseModel):
    confidence: Literal["high", "medium", "low"] = "low"
    missing_fields: List[str] = Field(default_factory=list)


class BiomedicalClinicalExtraction(BaseModel):
    """Generic biomedical clinical extraction schema for the default workspace clinical lane."""

    paper_id: str
    citation: Citation
    study_design: StudyDesign = Field(default_factory=StudyDesign)
    population: BiomedicalPopulation = Field(default_factory=BiomedicalPopulation)
    intervention: BiomedicalIntervention = Field(default_factory=BiomedicalIntervention)
    comparator: BiomedicalComparator = Field(default_factory=BiomedicalComparator)
    outcomes: BiomedicalOutcomes = Field(default_factory=BiomedicalOutcomes)
    safety_adherence: BiomedicalSafetyAdherence = Field(default_factory=BiomedicalSafetyAdherence)
    eligibility_flags: BiomedicalEligibilityFlags = Field(default_factory=BiomedicalEligibilityFlags)
    extraction_quality: BiomedicalExtractionQuality = Field(default_factory=BiomedicalExtractionQuality)

    @staticmethod
    def default_scope_note() -> str:
        return (
            "This is the default biomedical clinical extraction contract for human clinical and "
            "translational studies across biomedical domains. It should stay domain-neutral and "
            "must not assume neuroscience-, Alzheimer-, MCI-, or ketone-specific scope unless a "
            "specialty profile explicitly selects that lane."
        )

class TrialExtraction(BaseModel):
    """Specialized clinical extraction schema for the MCI/MCT/ketone review lane."""
    paper_id: str
    citation: Citation
    study_design: StudyDesign = Field(default_factory=StudyDesign)
    population: Population = Field(default_factory=Population)
    intervention: Intervention = Field(default_factory=Intervention)
    comparator: Comparator = Field(default_factory=Comparator)
    ketone_confirmation: KetoneConfirmation = Field(default_factory=KetoneConfirmation)
    outcomes: Outcomes = Field(default_factory=Outcomes)
    safety_adherence: SafetyAdherence = Field(default_factory=SafetyAdherence)
    risk_of_bias_hints: RiskOfBiasHints = Field(default_factory=RiskOfBiasHints)
    eligibility_flags: EligibilityFlags = Field(default_factory=EligibilityFlags)
    extraction_quality: ExtractionQuality = Field(default_factory=ExtractionQuality)

    @staticmethod
    def specialty_scope_note() -> str:
        return (
            "This contract is a specialty clinical extraction lane for mild cognitive impairment, "
            "ketone, and medium-chain triglyceride studies. It is not the generic biomedical "
            "clinical trial schema for the whole workspace."
        )

    @field_validator('eligibility_flags')
    def check_mci_consistency(cls, v, values):
        """
        mci_only가 False이면 include_for_mci_mct_review도 False여야 함.
        데이터에 접근하기 위해 values.data를 사용합니다.
        """
        # Pydantic v2에서는 values가 FieldValidationInfo 객체이므로 .data로 실제 데이터에 접근
        if 'population' in values.data and not values.data['population'].mci_only:
            v.include_for_mci_mct_review = False
            if not v.reason_if_excluded:
                v.reason_if_excluded = "Population not MCI-only."
        return v

    def to_summary_block(self) -> str:
        """Obsidian 노트에 추가할 자동 요약 블록을 생성합니다."""
        
        # Population
        pop_parts = []
        if self.population.mci_only:
            pop_parts.append("MCI-only")
        else:
            # [Improved] Show details for mixed population
            desc = "Mixed/Other"
            details = []
            if self.population.subtype != "unknown":
                details.append(self.population.subtype)
            if self.population.comorbidity_notes:
                details.append(self.population.comorbidity_notes)
            if details:
                desc += f" ({', '.join(details)})"
            pop_parts.append(desc)
            
        if self.population.n_total > 0:
            pop_parts.append(f"n={self.population.n_total}")
        if self.population.age_mean > 0:
            pop_parts.append(f"age≈{self.population.age_mean:.1f}")
        if self.population.apoe4_reported and self.population.apoe4_percent > 0:
            pop_parts.append(f"APOE4+ {self.population.apoe4_percent:.0f}%")
        population_str = ", ".join(pop_parts)

        # Intervention
        int_parts = []
        if self.intervention.category != "unknown":
            cat_display = self.intervention.category.replace("_", " ").title()
            if self.intervention.product_name:
                cat_display += f" ({self.intervention.product_name})"
            int_parts.append(cat_display)
        elif self.intervention.product_name:
            int_parts.append(self.intervention.product_name)

        if self.intervention.dose_value > 0:
            unit = self.intervention.dose_unit.replace("_per_day", "/d") if self.intervention.dose_unit != "unknown" else ""
            int_parts.append(f"{self.intervention.dose_value:.1f}{unit}")
        elif self.intervention.dose_schedule:
            int_parts.append(self.intervention.dose_schedule)

        if self.intervention.duration_weeks > 0:
            int_parts.append(f"{self.intervention.duration_weeks} weeks")
        intervention_str = ", ".join(int_parts)
        
        if not intervention_str:
            # [개선] Intervention 정보가 없을 때 Study Design이나 Tag 활용
            if self.study_design.design in ["systematic_review", "meta_analysis"]:
                intervention_str = "Systematic Review / Meta-analysis"
            elif self.eligibility_flags.separate_analysis_tag != "unknown":
                tag_clean = self.eligibility_flags.separate_analysis_tag.replace("_", " ").title()
                intervention_str = f"{tag_clean} (Unspecified details)"
            else:
                intervention_str = "Not detailed"
        
        # Outcomes
        cognition_outcomes = []
        if self.outcomes.cognition:
            for co in self.outcomes.cognition:
                text = co.name
                if co.effect_direction != 'unknown':
                    text += f" ({co.effect_direction})"
                if co.notes:
                    text += f": {co.notes}"
                cognition_outcomes.append(text)
        cognition_str = "; ".join(cognition_outcomes) if cognition_outcomes else "Not reported"
        
        adl_str = "Reported" if self.outcomes.adl_function else "Not reported"
        
        ae_summary = "Not reported"
        if self.safety_adherence.adverse_events_reported:
            ae_summary = self.safety_adherence.adverse_events_summary or "Reported, no details"

        # Ketone Confirmation
        ketone_str = "No"
        if self.ketone_confirmation.measured:
            metric = f" ({self.ketone_confirmation.metric})" if self.ketone_confirmation.metric != "unknown" else ""
            ketone_str = f"Yes{metric}"

        # Tag
        tag = self.eligibility_flags.separate_analysis_tag.replace("_", " ").title()
        if tag.lower() == "unknown":
            tag = "General" # Unknown 대신 General로 표시

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


# Canonical specialty-lane name with backward-compatible legacy aliasing.
SpecialtyTrialExtraction = TrialExtraction
