import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI, APITimeoutError, RateLimitError, APIStatusError
import json
import re
import time
import warnings
import numpy as np
import ollama

from src.config import (
    LLMConfig,
    resolve_clinical_extraction_feature,
    resolve_specialty_trial_extraction_feature,
)
from src.schemas import BiomedicalClinicalExtraction, SpecialtyTrialExtraction, PaperTagging
from src.json_repair import repair_and_parse_json

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _cloud_provider_name(config: LLMConfig) -> str:
    cloud_config = getattr(config, "cloud", None)
    provider = getattr(cloud_config, "provider", "openai")
    return str(provider or "openai").strip().lower() or "openai"


def _cloud_provider_label(config: LLMConfig) -> str:
    provider = _cloud_provider_name(config)
    if provider == "anthropic":
        return "Anthropic"
    return "OpenAI"


def _anthropic_client(api_key: str, *, timeout_seconds: int):
    try:
        from anthropic import Anthropic
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The `anthropic` package is not available in this Python environment. "
            "Use the repo venv or install the project dependencies first."
        ) from exc

    return Anthropic(api_key=api_key, timeout=timeout_seconds)


def _extract_anthropic_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        return str(content or "").strip()

    text_blocks: List[str] = []
    for block in content:
        if isinstance(block, dict):
            if str(block.get("type") or "").strip() != "text":
                continue
            text = str(block.get("text") or "").strip()
            if text:
                text_blocks.append(text)
            continue
        if str(getattr(block, "type", "") or "").strip() != "text":
            continue
        text = str(getattr(block, "text", "") or "").strip()
        if text:
            text_blocks.append(text)
    return "\n\n".join(text_blocks).strip()

# Canonical research text should remain English/original by default.
# Localized display layers can derive from these outputs later.
CANONICAL_SUMMARY_LANGUAGE = "English"
SPECIALTY_TRIAL_EXTRACTION_TASK = "specialty_trial_extraction"
LEGACY_SPECIALTY_TRIAL_EXTRACTION_TASK = "trial_extraction"
SLOT_ADJUDICATION_TASK = "slot_adjudication"
TAGGING_ADJUDICATION_TASK = "tagging_adjudication"
_HARD_TAG_SAMPLE_PATTERNS = (
    re.compile(r"\bn\s*[=:]\s*(\d{1,5})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,5})\s+(patients?|participants?|subjects?|volunteers?|cases?|mice|rats|animals?)\b", re.IGNORECASE),
)
_HARD_TAG_MODEL_PATTERN = re.compile(
    r"\b(5xFAD|APP/PS1|3xTg-AD|Tg2576|P301S|C57BL/6J?|BALB/c|HeLa|HEK293T?|SH-SY5Y|U87(?:MG)?|U251|MCF-7|A549|RAW ?264\.7|BV2|Jurkat|THP-1)\b"
)
_HARD_TAG_SPECIES_RULES = (
    (re.compile(r"\b(human|patients?|participants?|subjects?|volunteers?|cohort)\b", re.IGNORECASE), "human"),
    (re.compile(r"\b(mouse|mice|murine)\b", re.IGNORECASE), "mouse"),
    (re.compile(r"\b(rat|rats)\b", re.IGNORECASE), "rat"),
    (re.compile(r"\b(zebrafish)\b", re.IGNORECASE), "zebrafish"),
    (re.compile(r"\b(drosophila|fruit fly)\b", re.IGNORECASE), "drosophila"),
    (re.compile(r"\b(c\.?\s*elegans)\b", re.IGNORECASE), "c_elegans"),
    (re.compile(r"\b(monkey|macaque|primate)\b", re.IGNORECASE), "primate"),
    (re.compile(r"\b(dog|canine)\b", re.IGNORECASE), "dog"),
    (re.compile(r"\b(pig|porcine)\b", re.IGNORECASE), "pig"),
)
_DESIGN_OBSERVATIONAL_KEYWORDS = (
    "observational study",
    "cohort study",
    "retrospective cohort",
    "prospective cohort",
    "case control",
    "cross sectional",
    "registry study",
    "registry based",
)
_DESIGN_NONRANDOMIZED_KEYWORDS = (
    "single arm",
    "single group",
    "open label",
    "non randomized",
    "nonrandomized",
    "quasi experimental",
    "before after",
    "pre post",
)
_STUDY_TYPE_GUIDANCE_KEYWORDS = (
    "guideline",
    "guidelines",
    "consensus",
    "recommendation",
    "recommendations",
    "position statement",
)
_STUDY_TYPE_METHODS_KEYWORDS = (
    "protocol",
    "assay",
    "workflow",
    "validation study",
    "method validation",
    "methods paper",
    "sample preparation",
    "head to head",
    "benchmark",
    "benchmarking",
    "platform comparison",
    "assay comparison",
    "analytical performance",
)
_STUDY_TYPE_REVIEW_KEYWORDS = (
    "review",
    "narrative review",
    "critical review",
    "scoping review",
    "perspective",
    "hypothesis",
)
_PRECLINICAL_STUDY_KEYWORDS = (
    "in vitro",
    "cell culture",
    "organoid",
    "xenograft",
    "mouse model",
    "rat model",
    "animal model",
    "murine",
)
_SLOT_CLINICAL_CUE_TERMS = (
    "patient",
    "patients",
    "cohort",
    "randomized",
    "randomised",
    "placebo",
    "double blind",
    "clinical trial",
    "controlled trial",
    "intervention",
    "biomarker",
)
_SLOT_CLINICAL_UTILITY_CUE_TERMS = (
    "screening",
    "screen",
    "risk prediction",
    "predict dementia risk",
    "prognostic",
    "prognosis",
    "real world",
    "memory clinic",
    "triage",
    "decision support",
    "patient management",
    "clinical utility",
    "conversion",
)
_SLOT_METHODS_CUE_TERMS = (
    "protocol",
    "workflow",
    "assay",
    "validation",
    "sample preparation",
    "optimization",
    "optimisation",
    "methods paper",
    "method validation",
    "head to head",
    "benchmark",
    "benchmarking",
    "platform",
    "comparison",
    "linearity",
    "precision",
    "cutoff",
    "cutoffs",
)
_SLOT_MECHANISM_CUE_TERMS = (
    "pathway",
    "mechanism",
    "signaling",
    "signalling",
    "protein",
    "gene",
    "receptor",
    "phosphorylation",
    "knockout",
    "autophagy",
    "microglia",
)
_DEEP_READ_SECTION_HEADING_RE = re.compile(
    r"(?im)^\s*(abstract|introduction|background|methods?|materials\s+and\s+methods|results?|discussion|conclusions?)\s*:?\s*$"
)
_DEEP_READ_SECTION_PRIORITY = (
    "methods",
    "materials and methods",
    "results",
    "discussion",
    "conclusion",
    "conclusions",
    "introduction",
    "background",
    "abstract",
)

ESCALATION_BIOMEDICAL_SCOPE_TERMS = (
    "biomedical",
    "disease",
    "diseases",
    "patient",
    "patients",
    "cohort",
    "clinical",
    "trial",
    "randomized",
    "translational",
    "diagnosis",
    "diagnostic",
    "biomarker",
    "blood biomarker",
    "plasma biomarker",
    "csf biomarker",
    "oncology",
    "cancer",
    "tumor",
    "tumour",
    "immunology",
    "immune",
    "autoimmune",
    "inflammation",
    "cell",
    "cellular",
    "gene",
    "genetic",
    "molecular",
    "therapeutic",
    "treatment",
    "bioengineering",
    "biomaterial",
    "device",
    "implant",
    "hydrogel",
    "scaffold",
    "regenerative",
    "cartilage",
    "wound healing",
    "wound",
    "osteoarthritis",
    "brain",
    "neuroscience",
    "alzheimer",
    "alzheimers",
    "mci",
    "dementia",
    "microglia",
    "neuroinflammation",
)

ESCALATION_CONDITION_TERMS = (
    "mci",
    "mild cognitive impairment",
    "disease",
    "diseases",
    "cancer",
    "tumor",
    "tumour",
    "lymphoma",
    "leukemia",
    "melanoma",
    "colitis",
    "arthritis",
    "infection",
    "sepsis",
    "fibrosis",
    "diabetes",
    "obesity",
    "osteoarthritis",
    "cartilage",
    "wound",
    "dementia",
    "alzheimer",
    "alzheimers",
)

ESCALATION_OUT_OF_SCOPE_TERMS = (
    "sports performance",
    "collegiate cyclists",
    "endurance performance",
    "athletes",
    "football",
    "soccer",
    "basketball",
    "macroeconomic",
    "stock market",
    "consumer behavior",
    "supply chain",
    "semiconductor",
    "materials engineering",
    "synthetic polymer",
    "polymer films",
    "sustainable materials",
    "astrophysics",
    "particle physics",
    "quantum computing",
)

ESCALATION_REVIEW_STYLE_TERMS = (
    "advances in",
    "review",
    "narrative review",
    "critical review",
    "perspective",
    "personal view",
    "hypothesis",
    "what we know",
    "remains to be explored",
)

ESCALATION_METHOD_TERMS = (
    "assay",
    "cre-loxp",
    "cre loxp",
    "cre-er",
    "tamoxifen",
    "recombination",
    "recombination efficiency",
    "protocol",
    "protocol guidance",
    "workflow",
    "sample preparation",
    "validation",
    "optimized",
    "optimization",
)

ESCALATION_GUIDANCE_TERMS = (
    "recommendation",
    "recommendations",
    "guideline",
    "guidelines",
    "consensus",
    "working group",
    "clinical practice",
)

ESCALATION_CLINICAL_DATA_TERMS = (
    "randomized",
    "trial",
    "placebo",
    "patients",
    "cohort",
    "clinical study",
    "pilot",
    "prospective",
    "follow-up",
    "followup",
    "safety",
    "functional outcome",
    "response",
    "monitoring",
)

ESCALATION_ORIGINAL_EVIDENCE_TERMS = (
    "study",
    "studied",
    "results",
    "data",
    "identified",
    "reveal",
    "revealed",
    "showed",
    "demonstrated",
    "predict",
    "analysis",
    "improves",
    "improved",
    "modulate",
    "promote",
    "measured",
    "mouse",
    "mice",
    "model",
    "models",
    "cohort",
    "trial",
    "randomized",
    "prospective",
    "in vitro",
)

ESCALATION_MECHANISTIC_EVIDENCE_TERMS = (
    "mechanism",
    "pathway",
    "regulator",
    "regulators",
    "modulate",
    "promote",
    "inhibit",
    "activation",
    "signaling",
    "microglia",
    "amyloid",
    "tau",
    "macrophage",
    "t cell",
    "crispr",
    "organoid",
    "mouse model",
    "mice",
    "in vitro",
    "fibrosis",
    "tumor microenvironment",
)

ESCALATION_RESULT_IN_TITLE_TERMS = (
    "improves",
    "improved",
    "predict",
    "predicts",
    "modulate",
    "modulates",
    "promote",
    "promotes",
    "drives",
    "reveals",
    "revealed",
    "identifies",
    "identified",
    "targets",
    "concord",
    "associated with",
)

ESCALATION_ROUTE_APPROVE = "FAST_LANE_APPROVE"
ESCALATION_ROUTE_REVIEW = "QUEUE_HUMAN_REVIEW"
ESCALATION_REASON_CODE_ALIASES = {
    "OUT_OF_SCOPE": "OUT_OF_BIOMEDICAL_SCOPE",
    "NON_BIOMEDICAL": "OUT_OF_BIOMEDICAL_SCOPE",
    "NOT_BIOMEDICAL": "OUT_OF_BIOMEDICAL_SCOPE",
    "BROAD_REVIEW": "REVIEW_STYLE_LOW_CLARITY",
    "REVIEW": "REVIEW_STYLE_LOW_CLARITY",
    "NARRATIVE_REVIEW": "REVIEW_STYLE_LOW_CLARITY",
    "GUIDELINE": "FASTLANE_GUIDANCE",
    "CLINICAL_GUIDANCE": "FASTLANE_GUIDANCE",
    "METHOD": "FASTLANE_METHOD",
    "METHODS": "FASTLANE_METHOD",
    "CLINICAL": "FASTLANE_CLINICAL",
    "TRANSLATIONAL": "FASTLANE_CLINICAL",
    "MECHANISTIC": "FASTLANE_MECHANISTIC",
    "NO_AUTHORITY": "MODEL_REVIEW_REQUIRED",
    "UNCERTAIN": "MODEL_REVIEW_REQUIRED",
}
ESCALATION_REASON_CODE_ALLOWLIST = {
    "OUT_OF_BIOMEDICAL_SCOPE",
    "REVIEW_STYLE_LOW_CLARITY",
    "FASTLANE_METHOD",
    "FASTLANE_GUIDANCE",
    "FASTLANE_CLINICAL",
    "FASTLANE_MECHANISTIC",
    "MODEL_FAST_LANE_APPROVE",
    "MODEL_REVIEW_REQUIRED",
    "JUDGE_ERROR",
}

class LLMProvider:
    """LLM 공급자 인터페이스"""
    def __init__(self, config: LLMConfig, entity_aliases: Dict[str, str] = None):
        self.config = config
        self.entity_aliases = entity_aliases or {}
        self.client = None
        self._legacy_deep_read_helper_warned = False
        self.last_specialty_trial_extraction_diagnostic: Dict[str, Any] = {
            "status": "not_run",
            "error": None,
        }
        self.last_specialty_trial_extraction_raw_response: Optional[str] = None
        self.last_slot_classification_metrics: Dict[str, Any] = {
            "status": "not_run",
            "adjudication_triggered": False,
            "adjudication_reason": None,
            "final_source": None,
            "final_slot": None,
            "first_pass_predicted_slot": None,
            "first_pass_confidence": None,
            "error": None,
        }
        self.last_tagging_metrics: Dict[str, Any] = {
            "status": "not_run",
            "adjudication_triggered": False,
            "adjudication_reason": None,
            "final_source": None,
            "first_pass_confidence": None,
            "final_confidence": None,
            "first_pass_soft_tag_count": 0,
            "final_soft_tag_count": 0,
            "evidence_span_present": False,
            "validation_error": None,
            "error": None,
        }
        
        # Base implementation init
        self._initialize()

    def _initialize(self):
        """Provider specific initialization"""
        pass

    def is_available(self) -> bool:
        """API 키가 설정되어 있고 클라이언트가 준비되었는지 확인"""
        return self.client is not None

    def _temperature_for_task(self, task: str) -> float:
        """Use deterministic decoding for gate decisions to reduce approval drift."""
        if task in {"escalation", SLOT_ADJUDICATION_TASK, TAGGING_ADJUDICATION_TASK}:
            return 0.0
        return 0.3

    def _set_specialty_trial_extraction_diagnostic(self, *, status: str, error: str | None = None) -> None:
        self.last_specialty_trial_extraction_diagnostic = {
            "status": str(status or "").strip() or "unknown",
            "error": str(error).strip() if error else None,
        }

    def get_specialty_trial_extraction_diagnostic(self) -> Dict[str, Any]:
        return dict(self.last_specialty_trial_extraction_diagnostic)

    def _set_specialty_trial_extraction_raw_response(self, response: str | None) -> None:
        text = str(response).strip() if response is not None else ""
        self.last_specialty_trial_extraction_raw_response = text or None

    def get_specialty_trial_extraction_raw_response(self) -> Optional[str]:
        return self.last_specialty_trial_extraction_raw_response

    def _set_slot_classification_metrics(self, **kwargs: Any) -> None:
        metrics = {
            "status": "unknown",
            "adjudication_triggered": False,
            "adjudication_reason": None,
            "final_source": None,
            "final_slot": None,
            "first_pass_predicted_slot": None,
            "first_pass_confidence": None,
            "error": None,
        }
        metrics.update(kwargs)
        self.last_slot_classification_metrics = metrics

    def get_slot_classification_metrics(self) -> Dict[str, Any]:
        return dict(self.last_slot_classification_metrics)

    def _set_tagging_metrics(self, **kwargs: Any) -> None:
        metrics = {
            "status": "unknown",
            "adjudication_triggered": False,
            "adjudication_reason": None,
            "final_source": None,
            "first_pass_confidence": None,
            "final_confidence": None,
            "first_pass_soft_tag_count": 0,
            "final_soft_tag_count": 0,
            "evidence_span_present": False,
            "validation_error": None,
            "error": None,
        }
        metrics.update(kwargs)
        self.last_tagging_metrics = metrics

    def get_tagging_metrics(self) -> Dict[str, Any]:
        return dict(self.last_tagging_metrics)

    def _warn_legacy_deep_read_helper_used(self) -> None:
        if self._legacy_deep_read_helper_warned:
            return
        message = (
            "LLMProvider.generate_deep_read() is a legacy compatibility helper for metadata/full-text callers; "
            "the live deep-read runtime uses ReaderAgent over DocumentArtifact chunks."
        )
        logger.warning(message)
        warnings.warn(
            message,
            FutureWarning,
            stacklevel=2,
        )
        self._legacy_deep_read_helper_warned = True

    @staticmethod
    def _normalize_task_name(task: str) -> str:
        if task == LEGACY_SPECIALTY_TRIAL_EXTRACTION_TASK:
            return SPECIALTY_TRIAL_EXTRACTION_TASK
        if task == SLOT_ADJUDICATION_TASK:
            return "slot_classification"
        if task == TAGGING_ADJUDICATION_TASK:
            return "tagging"
        return task

    @staticmethod
    def _paper_text_blob(paper: Dict[str, Any]) -> str:
        tags = paper.get("tags", [])
        if isinstance(tags, list):
            tags_text = " ".join(str(tag) for tag in tags if tag)
        else:
            tags_text = str(tags or "")
        return " ".join(
            [
                str(paper.get("title") or ""),
                str(paper.get("summary") or ""),
                tags_text,
            ]
        ).lower()

    def _clinical_review_fallback_slot(self, paper: Dict[str, Any], predicted_slot: str) -> Optional[str]:
        if predicted_slot != "Mechanism":
            return None

        text = self._paper_text_blob(paper)
        is_review = any(term in text for term in ("systematic review", "meta-analysis", "meta analysis"))
        if not is_review:
            return None

        has_clinical_focus = any(
            term in text
            for term in (
                "clinical benefit",
                "clinical benefits",
                "adults with disease",
                "adults with medical conditions",
                "patients",
                "intervention",
                "treatment",
                "prognosis",
                "diagnosis",
                "randomized",
                "trial",
                "clinical evidence",
            )
        )
        has_methods_focus = any(
            term in text
            for term in (
                "assay",
                "validation",
                "platform",
                "benchmark",
                "workflow",
                "protocol",
                "analytical",
            )
        )
        has_explicit_mechanism_focus = any(
            term in text
            for term in (
                "mechanistic review",
                "pathway synthesis",
                "molecular mechanism",
                "causal biology",
                "preclinical mechanism",
            )
        )
        if has_clinical_focus and not has_methods_focus and not has_explicit_mechanism_focus:
            return "Clinical"
        return None

    def _escalation_fast_reject_reason(self, paper: Dict[str, Any]) -> Optional[str]:
        reason, _ = self._escalation_fast_reject(paper)
        return reason

    def _escalation_fast_reject(self, paper: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        text = self._paper_text_blob(paper)
        has_method_lane = any(term in text for term in ESCALATION_METHOD_TERMS)
        has_guidance_lane = any(term in text for term in ESCALATION_GUIDANCE_TERMS)
        has_clinical_data = any(term in text for term in ESCALATION_CLINICAL_DATA_TERMS)
        has_original_evidence = any(term in text for term in ESCALATION_ORIGINAL_EVIDENCE_TERMS)
        is_review_style = any(term in text for term in ESCALATION_REVIEW_STYLE_TERMS)

        if has_method_lane:
            return None, None
        if any(term in text for term in ESCALATION_OUT_OF_SCOPE_TERMS):
            return (
                "Out of PaperPipe's biomedical research workspace scope; keep pending review unless a human explicitly overrides."
            ), "OUT_OF_BIOMEDICAL_SCOPE"
        if is_review_style and not has_guidance_lane and not has_clinical_data and not has_original_evidence:
            return (
                "Broad review-style biomedical paper without authoritative guidance or direct clinical/translational evidence; keep pending review."
            ), "REVIEW_STYLE_LOW_CLARITY"
        if not any(term in text for term in ESCALATION_BIOMEDICAL_SCOPE_TERMS):
            return (
                "Out of PaperPipe's biomedical research workspace scope; keep pending review unless a human explicitly overrides."
            ), "OUT_OF_BIOMEDICAL_SCOPE"
        return None, None

    def _escalation_fast_approve_reason(self, paper: Dict[str, Any]) -> Optional[str]:
        reason, _ = self._escalation_fast_approve(paper)
        return reason

    def _escalation_fast_approve(self, paper: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        text = self._paper_text_blob(paper)
        title = str(paper.get("title") or "").lower()
        negative_scope_signals = (
            "not about",
            "did not involve",
            "does not involve",
            "not involve",
            "not relevant",
            "relevance is indirect",
            "indirect relevance",
            "not central",
        )
        if any(signal in text for signal in negative_scope_signals):
            return None, None
        has_biomedical_scope = any(term in text for term in ESCALATION_BIOMEDICAL_SCOPE_TERMS)
        has_condition_context = any(term in text for term in ESCALATION_CONDITION_TERMS)
        has_method_lane = any(term in text for term in ESCALATION_METHOD_TERMS)
        has_guidance_lane = any(term in text for term in ESCALATION_GUIDANCE_TERMS)
        has_clinical_data = any(term in text for term in ESCALATION_CLINICAL_DATA_TERMS)
        has_original_evidence = any(term in text for term in ESCALATION_ORIGINAL_EVIDENCE_TERMS)
        has_mechanistic_evidence = any(term in text for term in ESCALATION_MECHANISTIC_EVIDENCE_TERMS)
        has_title_result_signal = any(term in title for term in ESCALATION_RESULT_IN_TITLE_TERMS)
        is_review_style = any(term in text for term in ESCALATION_REVIEW_STYLE_TERMS)

        if has_method_lane and has_biomedical_scope:
            return "Concrete biomedical methods/protocol optimization is explicit; safe to auto-approve.", "FASTLANE_METHOD"

        if has_guidance_lane and has_biomedical_scope and (
            "diagnosis" in text
            or "diagnostic" in text
            or "biomarker" in text
            or "treatment" in text
            or "monitoring" in text
            or "clinical" in text
        ):
            return "Authoritative biomedical guidance is explicit; safe to auto-approve.", "FASTLANE_GUIDANCE"

        if (
            has_biomedical_scope
            and has_condition_context
            and has_clinical_data
            and has_original_evidence
            and not is_review_style
        ):
            return "Direct biomedical clinical/translational evidence is explicit; safe to auto-approve.", "FASTLANE_CLINICAL"

        if (
            has_biomedical_scope
            and has_condition_context
            and has_mechanistic_evidence
            and has_original_evidence
            and has_title_result_signal
            and not is_review_style
        ):
            return "Direct biomedical mechanistic evidence is explicit; safe to auto-approve.", "FASTLANE_MECHANISTIC"

        return None, None

    def _escalation_in_biomedical_scope(self, paper: Dict[str, Any]) -> bool:
        text = self._paper_text_blob(paper)
        if any(term in text for term in ESCALATION_OUT_OF_SCOPE_TERMS):
            return False
        return any(term in text for term in ESCALATION_BIOMEDICAL_SCOPE_TERMS)

    @staticmethod
    def _normalize_escalation_reason_codes(raw_codes: Any, *, approved: bool) -> List[str]:
        if not isinstance(raw_codes, list):
            return []
        normalized: List[str] = []
        for code in raw_codes:
            text = str(code or "").strip()
            if not text:
                continue
            upper = text.upper()
            canonical = ESCALATION_REASON_CODE_ALIASES.get(upper, upper)
            if canonical in ESCALATION_REASON_CODE_ALLOWLIST:
                normalized.append(canonical)
            elif approved:
                normalized.append("MODEL_FAST_LANE_APPROVE")
            else:
                normalized.append("MODEL_REVIEW_REQUIRED")
        deduped: List[str] = []
        for code in normalized:
            if code not in deduped:
                deduped.append(code)
        return deduped

    def _build_escalation_result(
        self,
        *,
        paper: Dict[str, Any],
        approved: bool,
        new_confidence: float,
        reason: str,
        reason_codes: Optional[List[str]] = None,
        final_route: Optional[str] = None,
    ) -> Dict[str, Any]:
        route = final_route or (ESCALATION_ROUTE_APPROVE if approved else ESCALATION_ROUTE_REVIEW)
        if route not in {ESCALATION_ROUTE_APPROVE, ESCALATION_ROUTE_REVIEW}:
            route = ESCALATION_ROUTE_APPROVE if approved else ESCALATION_ROUTE_REVIEW

        codes = [code for code in (reason_codes or []) if code]
        if not codes:
            if str(reason or "").lower().startswith("judge error"):
                codes = ["JUDGE_ERROR"]
            elif approved:
                codes = ["MODEL_FAST_LANE_APPROVE"]
            else:
                codes = ["MODEL_REVIEW_REQUIRED"]

        return {
            "approved": bool(approved),
            "new_confidence": float(new_confidence or 0.0),
            "reason": str(reason or "No reason provided"),
            "in_biomedical_scope": self._escalation_in_biomedical_scope(paper),
            "final_route": route,
            "reason_codes": codes,
        }

    def _build_escalation_prompt(self, paper: Dict[str, Any]) -> str:
        return f"""
        You are the final escalation gate for PaperPipe.
        The paper is already in "Pending Review". Your default answer is NO.

        Approve only when the title/abstract/tags make it obvious that a human does not need to inspect it.
        If there is any uncertainty, breadth, or indirect relevance, return approved=false.

        Paper:
        - Title: {paper.get('title', 'N/A')}
        - Abstract: {paper.get('summary', 'N/A')}
        - Current Tags: {paper.get('tags', [])}

        Auto-approve ONLY if all of the following are true:
        1. Direct fit to PaperPipe's biomedical workspace scope:
           - human clinical or translational biomedical studies across neuroscience, oncology, immunology, cell biology, translational medicine, or biomaterials-adjacent biomedical work
           - concrete biomedical methods, assay validation, protocol optimization, or workflow guidance
        2. The abstract suggests one of:
           - original clinical or translational data with a specific, strong finding in a defined disease, population, intervention, or biomarker context
           - an authoritative recommendation / consensus / diagnosis / biomarker / treatment / trial-design guidance that is clearly central to biomedical practice
        3. The relevance is immediate, not a remote transfer from a non-biomedical field.

        Reject and keep pending review when any of these apply:
        - broad review, critical review, narrative review, perspective, or hypothesis piece without a clearly authoritative biomedical guidance signal
        - general materials engineering, sports/performance, macroeconomics, or other non-biomedical work without biological, clinical, or translational context
        - interesting but not clearly must-keep, must-read, or decision-changing from metadata alone

        Return JSON STRICTLY:
        {{
            "approved": boolean,
            "new_confidence": float,
            "reason": "One sentence, concrete and conservative.",
            "reason_codes": ["OPTIONAL_REASON_CODE"],
            "final_route": "FAST_LANE_APPROVE" | "QUEUE_HUMAN_REVIEW"
        }}
        """

    def _get_model(self, task: str) -> str:
        """작업에 적합한 모델을 반환 (override 우선)"""
        task = self._normalize_task_name(task)
        # Default behavior: rely on feature config overrides if enabled, else provider default
        # This will be overridden by subclasses to map to specific model dicts (e.g. Ollama)
        if self.config.features: # Check if features config exists
            clinical_feature = resolve_clinical_extraction_feature(self.config.features)
            if task == "clinical_extraction" and clinical_feature:
                return clinical_feature.model
            trial_feature = resolve_specialty_trial_extraction_feature(self.config.features)
            if task == SPECIALTY_TRIAL_EXTRACTION_TASK and trial_feature:
                return trial_feature.model
            elif task == "one_liner" and self.config.features.one_liner:
                return self.config.features.one_liner.model
            elif task == "slot_classification" and self.config.features.slot_classification:
                return self.config.features.slot_classification.model
        
        # Fallback to default_model if features not configured or task not found
        if self.config.default_model:
            return self.config.default_model
        
        return "gpt-4o-mini" # Ultimate fallback

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        raise NotImplementedError

    def get_embedding(self, text: str) -> Optional[List[float]]:
        raise NotImplementedError

    def _extract_json(self, response_content: str) -> Optional[Dict[str, Any]]:
        """
        Robustly extract/repair JSON from LLM response.
        """
        if not response_content:
            return None

        try:
            parsed = repair_and_parse_json(response_content)
            
            # [Smart Unwrap Logic]
            # If the LLM wrapped the response in "data", "response", "content", etc., unwrap it.
            # For tagging, we expect hard_tags and soft_tags to be present together.
            
            def find_keys(obj, keys):
                if isinstance(obj, dict):
                    # Check if this object has the keys we want
                    if all(k in obj for k in keys):
                        return obj
                    # If not, check values (recursive descent)
                    for v in obj.values():
                        found = find_keys(v, keys)
                        if found:
                            return found
                return None

            # Try to find the schema if not at root
            # Only do this if we are looking for a specific schema structure (inferred by context or generous check)
            # For tagging, we expect hard_tags and soft_tags.
            unwrapped = find_keys(parsed, ["hard_tags", "soft_tags"])
            if unwrapped:
                return unwrapped
            
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to extract JSON from content: {response_content[:100]}... ({e})")
        return None

    @staticmethod
    def _tagging_source_text(paper: Dict[str, Any]) -> str:
        return "\n".join(
            [
                str(paper.get("title") or ""),
                str(paper.get("summary") or ""),
                str(paper.get("full_text") or ""),
            ]
        )

    @staticmethod
    def _normalize_hard_tag_text(text: str) -> str:
        lowered = str(text or "").lower()
        lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
        return " ".join(lowered.split())

    @staticmethod
    def _extract_sample_size_hard_tag(text: str) -> int | None:
        candidates: list[int] = []
        for pattern in _HARD_TAG_SAMPLE_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    candidates.append(int(match.group(1)))
                except (TypeError, ValueError):
                    continue
        return max(candidates) if candidates else None

    @staticmethod
    def _extract_species_hard_tag(text: str) -> str | None:
        matches: list[str] = []
        for pattern, normalized in _HARD_TAG_SPECIES_RULES:
            if pattern.search(text):
                matches.append(normalized)
        unique_matches = list(dict.fromkeys(matches))
        return unique_matches[0] if len(unique_matches) == 1 else None

    @staticmethod
    def _extract_model_hard_tag(text: str) -> str | None:
        matches = [match.group(1) for match in _HARD_TAG_MODEL_PATTERN.finditer(text)]
        unique_matches = list(dict.fromkeys(matches))
        return unique_matches[0] if len(unique_matches) == 1 else None

    @classmethod
    def _extract_design_hard_tag(cls, text: str) -> str | None:
        normalized = cls._normalize_hard_tag_text(text)
        if not normalized:
            return None

        has_randomized = "randomized" in normalized or "randomised" in normalized
        has_trial = "trial" in normalized or "clinical trial" in normalized or "controlled trial" in normalized
        has_crossover = "crossover" in normalized or "cross over" in normalized

        if "meta analysis" in normalized:
            return "meta_analysis"
        if "systematic review" in normalized:
            return "systematic_review"
        if has_crossover and (has_randomized or has_trial):
            return "crossover_rct"
        if (has_randomized or "double blind" in normalized or "placebo controlled" in normalized) and has_trial:
            return "parallel_rct"
        if any(keyword in normalized for keyword in _DESIGN_NONRANDOMIZED_KEYWORDS):
            return "nonrandomized"
        if any(keyword in normalized for keyword in _DESIGN_OBSERVATIONAL_KEYWORDS):
            return "observational"
        return None

    @classmethod
    def _extract_study_type_hard_tag(cls, text: str) -> str | None:
        normalized = cls._normalize_hard_tag_text(text)
        if not normalized:
            return None

        design = cls._extract_design_hard_tag(text)
        if design == "meta_analysis":
            return "Meta-analysis"
        if design == "systematic_review":
            return "Systematic Review"
        if any(keyword in normalized for keyword in _STUDY_TYPE_GUIDANCE_KEYWORDS):
            return "Guideline"
        if design in {"parallel_rct", "crossover_rct", "nonrandomized"}:
            return "Clinical Trial"
        if design == "observational":
            return "Observational Study"
        if any(keyword in normalized for keyword in _STUDY_TYPE_METHODS_KEYWORDS):
            return "Methods Paper"
        if any(keyword in normalized for keyword in _STUDY_TYPE_REVIEW_KEYWORDS):
            return "Review"
        if any(keyword in normalized for keyword in _PRECLINICAL_STUDY_KEYWORDS):
            return "Preclinical Study"

        species = cls._extract_species_hard_tag(text)
        model = cls._extract_model_hard_tag(text)
        if species and species != "human":
            return "Preclinical Study"
        if model:
            return "Preclinical Study"
        return None

    @staticmethod
    def _is_missing_hard_tag_value(value: Any) -> bool:
        return value in (None, "", [], {})

    def _deterministic_hard_tags(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        text = self._tagging_source_text(paper)
        if not text.strip():
            return {}
        return {
            "species": self._extract_species_hard_tag(text),
            "sample_size": self._extract_sample_size_hard_tag(text),
            "model": self._extract_model_hard_tag(text),
            "design": self._extract_design_hard_tag(text),
            "study_type": self._extract_study_type_hard_tag(text),
        }

    def _augment_tagging_hard_tags(self, payload: Dict[str, Any], paper: Dict[str, Any]) -> Dict[str, Any]:
        augmented = dict(payload)
        hard_tags = augmented.get("hard_tags")
        hard_tags_dict = dict(hard_tags) if isinstance(hard_tags, dict) else {}
        for key, value in self._deterministic_hard_tags(paper).items():
            if key not in hard_tags_dict or self._is_missing_hard_tag_value(hard_tags_dict.get(key)):
                if value not in (None, ""):
                    hard_tags_dict[key] = value
        augmented["hard_tags"] = hard_tags_dict
        return augmented

    @staticmethod
    def _normalized_section_name(name: str) -> str:
        lowered = " ".join(str(name or "").strip().lower().split())
        if lowered in {"method", "methods"}:
            return "Methods"
        if lowered == "materials and methods":
            return "Materials and Methods"
        if lowered in {"result", "results"}:
            return "Results"
        if lowered == "discussion":
            return "Discussion"
        if lowered in {"conclusion", "conclusions"}:
            return "Conclusion"
        if lowered == "introduction":
            return "Introduction"
        if lowered == "background":
            return "Background"
        if lowered == "abstract":
            return "Abstract"
        return str(name or "").strip().title() or "Section"

    def _section_aware_full_text_blocks(
        self,
        full_text: str,
        *,
        max_chars: int,
        per_section_chars: int,
    ) -> List[str]:
        matches = list(_DEEP_READ_SECTION_HEADING_RE.finditer(full_text))
        if not matches:
            return []

        sections: list[tuple[str, str]] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(full_text)
            body = full_text[start:end].strip()
            if not body:
                continue
            sections.append((self._normalized_section_name(match.group(1)), body))

        if not sections:
            return []

        order = {name: idx for idx, name in enumerate(self._normalized_section_name(s) for s in _DEEP_READ_SECTION_PRIORITY)}
        sections.sort(key=lambda item: (order.get(item[0], len(order)),))

        remaining = max_chars
        chunk_blocks: list[str] = []
        for section_name, body in sections:
            if remaining <= 0:
                break
            excerpt_budget = max(300, min(remaining, per_section_chars))
            excerpt = body[:excerpt_budget].strip()
            if not excerpt:
                continue
            block = f"[{section_name}]\n{excerpt}"
            if len(block) > remaining and chunk_blocks:
                break
            chunk_blocks.append(block[:remaining])
            remaining -= len(block[:remaining]) + 2

        return chunk_blocks

    @staticmethod
    def _cue_presence_label(text: str, cue_terms: tuple[str, ...]) -> str:
        return "yes" if any(term in text for term in cue_terms) else "no"

    def _deterministic_signal_summary(self, paper: Dict[str, Any], *, current_slot: str | None = None) -> str:
        text = self._normalize_hard_tag_text(self._tagging_source_text(paper))
        hard_tags = self._deterministic_hard_tags(paper)
        lines = ["Deterministic Signal Summary:"]
        if current_slot is not None:
            lines.append(f"- Current Rule-based Guess: {current_slot}")
        lines.append(f"- Species Hint: {hard_tags.get('species') or 'unknown'}")
        lines.append(f"- Study Type Hint: {hard_tags.get('study_type') or 'unknown'}")
        lines.append(f"- Design Hint: {hard_tags.get('design') or 'unknown'}")
        lines.append(f"- Clinical Cue Terms Present: {self._cue_presence_label(text, _SLOT_CLINICAL_CUE_TERMS)}")
        lines.append(
            f"- Clinical Utility Cue Terms Present: {self._cue_presence_label(text, _SLOT_CLINICAL_UTILITY_CUE_TERMS)}"
        )
        lines.append(f"- Methods Cue Terms Present: {self._cue_presence_label(text, _SLOT_METHODS_CUE_TERMS)}")
        lines.append(
            "- Assay Comparison Cue Terms Present: "
            f"{self._cue_presence_label(text, ('head to head', 'benchmark', 'benchmarking', 'platform comparison', 'assay comparison'))}"
        )
        lines.append(f"- Mechanism Cue Terms Present: {self._cue_presence_label(text, _SLOT_MECHANISM_CUE_TERMS)}")
        return "\n".join(lines)

    def _paper_evidence_bundle(
        self,
        paper: Dict[str, Any],
        *,
        current_slot: str | None = None,
        max_chars: int = 6000,
        per_section_chars: int = 1200,
    ) -> str:
        parts = [
            f"Title: {paper.get('title', 'N/A')}",
            f"Abstract: {paper.get('summary', 'N/A')}",
            self._deterministic_signal_summary(paper, current_slot=current_slot),
        ]

        full_text = str(paper.get("full_text") or "").strip()
        if not full_text:
            return "\n".join(parts)

        chunk_blocks = self._section_aware_full_text_blocks(
            full_text,
            max_chars=max_chars,
            per_section_chars=per_section_chars,
        )
        if chunk_blocks:
            parts.append("Section-Aware Full Text Chunks:")
            parts.extend(chunk_blocks)
        else:
            snippet = full_text[:max_chars].strip()
            if snippet:
                parts.append("Full Text Excerpt:")
                parts.append(snippet)

        return "\n".join(parts)

    @staticmethod
    def _normalize_slot_prediction(value: Any) -> Optional[str]:
        normalized = str(value or "").strip().lower()
        if normalized == "clinical":
            return "Clinical"
        if normalized == "methods":
            return "Methods"
        if normalized == "mechanism":
            return "Mechanism"
        return None

    @staticmethod
    def _coerce_optional_bool(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1"}:
                return True
            if normalized in {"false", "no", "0"}:
                return False
        return None

    def _slot_analysis_requires_adjudication(self, analysis: Dict[str, Any], current_slot: str) -> tuple[bool, Optional[str]]:
        explicit = self._coerce_optional_bool(analysis.get("needs_adjudication"))
        if explicit is not None:
            return explicit, "explicit_flag" if explicit else None

        predicted = self._normalize_slot_prediction(analysis.get("predicted_slot")) or current_slot

        confidence: Optional[float] = None
        raw_confidence = analysis.get("confidence")
        if raw_confidence is not None:
            try:
                confidence = float(raw_confidence)
            except (TypeError, ValueError):
                confidence = None

        signal_flags = [
            self._coerce_optional_bool(analysis.get("clinical_signal")),
            self._coerce_optional_bool(analysis.get("methods_signal")),
            self._coerce_optional_bool(analysis.get("mechanism_signal")),
        ]
        known_flags = [flag for flag in signal_flags if flag is not None]
        if known_flags:
            positive_flags = sum(1 for flag in known_flags if flag is True)
            if positive_flags != 1:
                return True, "signal_conflict"

        if confidence is not None and confidence < 0.75:
            return True, "low_confidence"
        if confidence is not None and predicted != current_slot and confidence < 0.9:
            return True, "slot_change_low_confidence"
        return False, None

    def _build_slot_adjudication_prompt(
        self,
        *,
        evidence_bundle: str,
        current_slot: str,
        first_pass_analysis: Dict[str, Any],
    ) -> str:
        analysis_json = json.dumps(first_pass_analysis, ensure_ascii=False, indent=2, sort_keys=True)
        return f"""
        You are the final adjudicator for biomedical slot classification.
        Resolve ambiguous or conflicting first-pass slot analyses conservatively.

        Allowed Slots:
        - Mechanism
        - Clinical
        - Methods

        Selection Priorities:
        1. Choose Clinical only when the central contribution is human-subject, patient, biomarker, intervention, or translational evidence with screening, prognosis, risk prediction, triage, or real-world clinical utility as the main novelty.
        2. Choose Methods when the primary contribution is a protocol, assay, workflow, validation, technique paper, or assay/platform benchmarking/comparison paper.
        3. Choose Mechanism when the central contribution is biological pathway or cellular/animal mechanism work.
        4. If signals are mixed, prefer the slot that best matches the PRIMARY contribution, not secondary context.
        5. Prefer Clinical over Methods when biomarker technology is mainly a tool for a patient-management, screening, prognostic, or risk-prediction claim.
        6. Prefer Methods over Clinical when patient cohorts are used mainly to validate or compare measurement platforms rather than answer a patient-management question.
        7. Human cohorts do not automatically make a paper Clinical if the main novelty is validating or benchmarking a measurement platform.
        8. If evidence remains mixed after review, keep the current rule-based guess.

        Current Rule-based Guess:
        {current_slot}

        First-Pass Hierarchical Analysis:
        {analysis_json}

        Paper Evidence Bundle:
        {evidence_bundle}

        Return JSON STRICTLY:
        {{
            "reasoning": "Short adjudication rationale.",
            "predicted_slot": "Mechanism" | "Clinical" | "Methods"
        }}
        """

    def _entity_alias_prompt_section(self) -> str:
        if not self.entity_aliases:
            return ""
        alias_list = "\n".join([f"- '{alias}' -> '{standard}'" for alias, standard in self.entity_aliases.items()])
        return f"""
        5. **Entity Normalization (CRITICAL)**:
           You MUST normalize the following terms to their standard names if encountered:
           {alias_list}
           - Example: If text says "TNBC patients", soft tag MUST be "#TripleNegativeBreastCancer", NOT "#TNBC".
        """

    @staticmethod
    def _coerce_optional_float(value: Any) -> Optional[float]:
        try:
            if value in (None, ""):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalized_soft_tags(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        normalized: List[str] = []
        for item in value:
            tag = str(item or "").strip()
            if tag:
                normalized.append(tag)
        return normalized

    def _tagging_requires_adjudication(self, payload: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        explicit = self._coerce_optional_bool(payload.get("needs_adjudication"))
        if explicit is not None:
            return explicit, "explicit_flag" if explicit else None

        soft_tags = self._normalized_soft_tags(payload.get("soft_tags"))
        if not soft_tags:
            return True, "missing_soft_tags"
        if any(not tag.startswith("#") for tag in soft_tags):
            return True, "invalid_soft_tag_format"

        evidence_span = str(payload.get("evidence_span") or "").strip()
        if not evidence_span:
            return True, "missing_evidence_span"

        confidence = self._coerce_optional_float(payload.get("confidence"))
        if confidence is not None and confidence < 0.7:
            return True, "low_confidence"
        return False, None

    def _build_tagging_adjudication_prompt(
        self,
        *,
        evidence_bundle: str,
        first_pass_analysis: Dict[str, Any],
    ) -> str:
        first_pass_json = json.dumps(first_pass_analysis, ensure_ascii=False, indent=2, sort_keys=True)
        return f"""
        You are the final adjudicator for biomedical hybrid tagging.
        Repair a weak or malformed first-pass tagging result conservatively using the paper evidence bundle.

        Requirements:
        1. Preserve supported hard tags when the evidence bundle clearly supports them.
        2. Ensure every soft tag starts with `#` and uses Obsidian-style formatting.
        3. Keep the evidence span concrete and non-empty.
        4. If confidence should remain low, keep it low rather than inventing certainty.

        First-Pass Tagging Analysis:
        {first_pass_json}

        Paper Evidence Bundle:
        {evidence_bundle}

        Return JSON ONLY in the following structure:
        {{
            "hard_tags": {{
                "species": "extracted species or null",
                "sample_size": integer or null,
                "model": "extracted model or null",
                "design": "parallel_rct | crossover_rct | nonrandomized | observational | systematic_review | meta_analysis | null",
                "study_type": "Clinical Trial | Observational Study | Systematic Review | Meta-analysis | Methods Paper | Review | Guideline | Preclinical Study | null"
            }},
            "soft_tags": ["#Category/Subcategory", "#AnotherTag"],
            "evidence_span": "Quote from text...",
            "confidence": 0.8,
            "reasoning": "Short repair rationale..."
        }}
        """

    def _validate_tagging_payload(self, payload: Dict[str, Any], paper: Dict[str, Any]) -> PaperTagging:
        augmented = self._augment_tagging_hard_tags(payload, paper)
        return PaperTagging(**augmented)

    def _deep_read_section_context(self, paper: Dict[str, Any], max_chars: int = 8000) -> str:
        parts = [
            f"Title: {paper.get('title', 'N/A')}",
            f"Abstract: {paper.get('summary', 'N/A')}",
        ]

        full_text = str(paper.get("full_text") or "").strip()
        if not full_text:
            return "\n".join(parts)

        chunk_blocks = self._section_aware_full_text_blocks(
            full_text,
            max_chars=max_chars,
            per_section_chars=1600,
        )
        if chunk_blocks:
            parts.append("Section-Aware Full Text Chunks:")
            parts.extend(chunk_blocks)
        else:
            snippet = full_text[:max_chars].strip()
            if snippet:
                parts.append("Full Text Excerpt:")
                parts.append(snippet)

        return "\n".join(parts)

    @staticmethod
    def _fallback_citation_from_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": paper.get("title", ""),
            "authors_first": str(paper.get("authors", "")).split(",")[0] if paper.get("authors") else "Unknown",
            "year": int(paper.get("published", "0")[:4]) if paper.get("published") and paper.get("published")[:4].isdigit() else 0,
            "journal_or_server": paper.get("source", "Unknown"),
            "doi": paper.get("doi"),
            "url": paper.get("link"),
        }

    def extract_biomedical_clinical_data(
        self,
        paper: Dict[str, Any],
        methods_snippet: str = "",
    ) -> Optional[BiomedicalClinicalExtraction]:
        """Domain-neutral biomedical clinical extraction for the default workspace lane."""

        try:
            schema_json = json.dumps(BiomedicalClinicalExtraction.model_json_schema(), indent=2)
        except Exception:
            schema_json = "Schema definition unavailable."

        prompt = f"""
You are an information extraction engine for the default biomedical clinical lane in PaperPipe.
IMPORTANT SCOPE: {BiomedicalClinicalExtraction.default_scope_note()}
Extract structured data STRICTLY as valid JSON following the provided schema below. Do not output any Markdown, comments, or extra keys.

Schema:
{schema_json}

Rules:
- Keep the extraction domain-neutral across biomedical clinical and translational studies, including neuroscience, oncology, immunology, cell therapy, and biomaterials-adjacent biomedical work when they are actually human or translational studies.
- Capture the studied condition/population, intervention, comparator, primary outcomes, secondary outcomes, biomarkers, and safety/adherence when reported.
- If the paper is not a human clinical or translational biomedical study, set eligibility_flags.is_human_clinical_study=false or eligibility_flags.fits_biomedical_scope=false and explain why.
- If a field is not stated, use null/0/unknown appropriately and list it in extraction_quality.missing_fields.
- Prefer generic biomedical wording over disease-specific assumptions. Do not assume Alzheimer disease, MCI, ketones, or neuroscience-specific endpoints unless the paper text explicitly supports them.

Now extract from the following text:
<<<
Title: {paper.get('title', 'N/A')}
Abstract: {paper.get('summary', 'N/A')}
Methods Snippet: {methods_snippet if methods_snippet else "Not available"}
>>>
"""

        for i in range(2):
            response_content = self._make_request(
                "clinical_extraction",
                prompt,
                is_json=True,
                schema=BiomedicalClinicalExtraction.model_json_schema(),
            )

            if not response_content or "AI Error" in response_content:
                logger.error(f"Failed to get valid content from LLM: {response_content}")
                return None

            try:
                data = self._extract_json(response_content)
                if not data:
                    logger.warning(f"Attempt {i+1}: Failed to extract JSON from response.")
                    continue

                if not data.get("paper_id"):
                    data["paper_id"] = paper.get("doi") or paper.get("link") or paper.get("title") or "unknown_id"

                if not data.get("citation"):
                    data["citation"] = self._fallback_citation_from_paper(paper)

                validated_data = BiomedicalClinicalExtraction(**data)
                logger.info("Successfully parsed and validated biomedical clinical extraction data.")
                return validated_data
            except Exception as e:
                logger.error(f"Schema validation failed for LLM response: {e}")
                return None

        logger.error("Failed to get a valid and parseable biomedical clinical extraction JSON response after retries.")
        return None

    def extract_specialty_trial_data(
        self,
        paper: Dict[str, Any],
        methods_snippet: str = "",
    ) -> Optional[SpecialtyTrialExtraction]:
        """Specialty clinical extraction for the legacy MCI/MCT/ketone lane."""
        self._set_specialty_trial_extraction_diagnostic(status="started")
        self._set_specialty_trial_extraction_raw_response(None)
        
        # [Fix] Pydantic 모델에서 JSON 스키마 추출하여 프롬프트에 주입
        try:
            schema_json = json.dumps(SpecialtyTrialExtraction.model_json_schema(), indent=2)
        except Exception:
            schema_json = "Schema definition unavailable."

        prompt = f"""
You are an information extraction engine for a specialty clinical evidence lane in PaperPipe.
IMPORTANT SCOPE: {SpecialtyTrialExtraction.specialty_scope_note()}
This prompt intentionally targets MCT/ketone supplementation in Mild Cognitive Impairment (MCI). Do not reinterpret it as the generic biomedical clinical extraction contract.
Extract structured data STRICTLY as valid JSON following the provided schema below. Do not output any Markdown, comments, or extra keys.

Schema:
{schema_json}

Rules:
- The target population is MCI-only. If the study includes AD or mixed populations and MCI-specific results are not separable, mark include_for_mci_mct_review=false and explain why.
- Primary outcomes must cover cognition AND also capture ADL/function and safety/adherence when reported.
- Ketone ester/salt interventions must be included but tagged for separate analysis (separate_analysis_tag="ketone_ester_or_salt").
- If a field is not stated, use null/0/unknown appropriately and list it in extraction_quality.missing_fields.
- **IMPORTANT**: If specific dose/product is missing in abstract, INFER 'category' and 'product_name' from Title or Context. Do not leave Intervention empty if possible.
- If the paper is a Systematic Review or Meta-analysis:
    - Set 'category' to the INTERVENTION TOPIC (e.g., 'ketogenic_diet', 'mct', 'ketone_ester').
    - Set 'product_name' to "Systematic Review".
    - Summarize the overall conclusion in 'outcomes.cognition[0].notes'.
- Always try to classify 'separate_analysis_tag' (e.g., 'primary_mct', 'ketogenic_diet') even if details are sparse.
- For 'Population', if 'mci_only' is false, provide details in 'comorbidity_notes' (e.g., "Includes AD and Healthy Controls").

Now extract from the following text:
<<<
Title: {paper.get('title', 'N/A')}
Abstract: {paper.get('summary', 'N/A')}
Methods Snippet: {methods_snippet if methods_snippet else "Not available"}
>>>
"""
        
        for i in range(2): # 최대 2번 시도 (최초 1회 + 재시도 1회)
            response_content = self._make_request(
                SPECIALTY_TRIAL_EXTRACTION_TASK,
                prompt,
                is_json=True,
                schema=SpecialtyTrialExtraction.model_json_schema(),
            )
            self._set_specialty_trial_extraction_raw_response(response_content)
            
            if not response_content or "AI Error" in response_content:
                logger.error(f"Failed to get valid content from LLM: {response_content}")
                self._set_specialty_trial_extraction_diagnostic(
                    status="request_failed",
                    error=str(response_content or "empty_response"),
                )
                return None

            try:
                # [Modified] Parse using robust extractor
                data = self._extract_json(response_content)
                if not data:
                    logger.warning(f"Attempt {i+1}: Failed to extract JSON from response.")
                    continue
                
                # Ensure metadata (Robustness)
                if not data.get('paper_id'):
                    data['paper_id'] = paper.get('doi') or paper.get('link') or paper.get('title') or "unknown_id"
                
                # Citation 정보가 부실하면 원본 메타데이터로 보완
                if not data.get('citation'):
                    data['citation'] = self._fallback_citation_from_paper(paper)

                validated_data = SpecialtyTrialExtraction(**data)
                logger.info("Successfully parsed and validated trial extraction data.")
                self._set_specialty_trial_extraction_diagnostic(status="ok")
                return validated_data
            except Exception as e:
                logger.error(f"Schema validation failed for LLM response: {e}")
                self._set_specialty_trial_extraction_diagnostic(
                    status="schema_invalid",
                    error=f"{type(e).__name__}: {e}",
                )
                # 유효성 검사 실패 시 재시도 없이 종료 (프롬프트 자체의 문제일 수 있음)
                return None
        
        logger.error("Failed to get a valid and parseable JSON response after retries.")
        self._set_specialty_trial_extraction_diagnostic(status="json_parse_failed")
        return None

    def extract_trial_data(self, paper: Dict[str, Any], methods_snippet: str = "") -> Optional[SpecialtyTrialExtraction]:
        """Backward-compatible wrapper for the specialty clinical extraction lane."""
        return self.extract_specialty_trial_data(paper, methods_snippet)

    def _generate_legacy_deep_read_summary(self, paper: Dict[str, Any]) -> Optional[str]:
        slot = paper.get('slot', '').lower()
        context_block = self._deep_read_section_context(paper)

        if slot == 'methods':
            prompt = f"""
            Analyze this METHODOLOGY paper for a biomedical researcher.
            Paper Context:
            {context_block}
            
            Provide a structured report in {CANONICAL_SUMMARY_LANGUAGE} (Markdown):
            0. **Originality Summary (Triage 4-Step)**
               - **Context**: What is the broader background of this line of research?
               - **Gap**: What decisive question did prior work leave unresolved?
               - **This Paper**: How does this paper address that question?
            
            1. **Core Technique**: What is the main method or protocol?
            2. **Key Protocol And Tips**: What critical steps, reagents, or troubleshooting advice are highlighted?
            3. **Advantages And Innovation**: Why is it better than existing methods?
            4. **Limitations And Caveats**: What are the constraints or potential pitfalls?
            5. **Applications**: How can this be applied in biomedical research or translational work?
            """
        elif slot == 'mechanism':
            prompt = f"""
            Analyze this MECHANISTIC paper for a biomedical researcher.
            Paper Context:
            {context_block}
            
            Provide a structured report in {CANONICAL_SUMMARY_LANGUAGE} (Markdown):
            0. **Originality Summary (Triage 4-Step)**
               - **Context**: What is the broader background of this line of research?
               - **Gap**: What decisive question did prior work leave unresolved?
               - **This Paper**: How does this paper address that question?
               
            1. **Hypothesis**: What are they testing?
            2. **Key Mechanism**: What pathway or molecule interactions are proposed (for example, A -> B -> C)?
            3. **Key Results**: What findings support the mechanism?
            4. **Implications**: What is the impact on the field?
            """
        else:
            prompt = f"""
            Analyze this paper for a biomedical researcher.
            Paper Context:
            {context_block}
            
            Provide a structured report in {CANONICAL_SUMMARY_LANGUAGE} (Markdown):
            0. **Originality Summary** (Context -> Gap -> Paper)
               - **Context**: What is the broader background of this line of research?
               - **Gap**: What decisive question did prior work leave unresolved?
               - **This Paper**: How does this paper address that question?
            1. **Key Findings**
            2. **Methodology**
            3. **Implications And Limitations**
            """
        return self._make_request("deep_read", prompt)

    def generate_deep_read(self, paper: Dict[str, Any]) -> Optional[str]:
        """Compatibility deep-read helper for legacy/non-agent callers.

        The live CLI/runtime deep-read lane uses ``ReaderAgent`` over
        ``DocumentArtifact`` chunks. Keep this helper for bounded callers that
        only have metadata/full-text dict payloads available.
        """
        self._warn_legacy_deep_read_helper_used()
        return self._generate_legacy_deep_read_summary(paper)

    def generate_one_liner(self, paper: Dict[str, Any]) -> Optional[str]:
        """논문의 핵심 내용을 한 문장으로 요약"""
        prompt = f"""
        Summarize the core contribution of this paper in ONE SINGLE {CANONICAL_SUMMARY_LANGUAGE} sentence, like a TL;DR.
        Title: {paper.get('title', 'N/A')}
        Abstract: {paper.get('summary', 'N/A')}
        """
        return self._make_request("one_liner", prompt)

    def review_claimset_bundle(self, *, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Teacher-quality review over a prepared claimset bundle."""
        return self._make_request("teacher_review", prompt, is_json=True, system_prompt=system_prompt)

    def classify_slot(self, paper: Dict[str, Any], current_slot: str) -> str:
        """논문의 슬롯을 계층적(Hierarchical)으로 분류"""
        self._set_slot_classification_metrics(status="started", final_slot=current_slot)
        evidence_bundle = self._paper_evidence_bundle(
            paper,
            current_slot=current_slot,
            max_chars=4500,
            per_section_chars=900,
        )
        prompt = f"""
        You are a research paper classifier.
        Classify the paper into exactly one slot by identifying the paper's center of gravity.

        Target Schema (Slots):
        1. Mechanism: Primary contribution is basic science, cellular pathways, molecular interactions, animal/cell experiments, causal biology, or mechanistic synthesis.
        2. Clinical: Primary contribution is human clinical evidence, patient-facing screening, diagnosis, prognosis, risk prediction, triage, treatment effect, clinical utility, or disease-focused systematic review/meta-analysis of clinical evidence.
        3. Methods: Primary contribution is a protocol, technique, assay, workflow, analytical validation, cutoff calibration, platform benchmark, head-to-head assay comparison, method/resource benchmark, quality-control panel, reporting checklist, or measurement-performance characterization.

        Paper Evidence Bundle:
        {evidence_bundle}

        Reasoning Steps:
        1. Domain Check: Is this biomedical research, and what biomedical area is central?
        2. Clinical Evidence Review Hard Stop: If the paper is a systematic review or meta-analysis whose main question is clinical benefits, patient outcomes, intervention/exposure effects, treatment effects, prognosis, diagnosis, adverse events, evidence quality, or clinical utility in humans, patients, adults with disease, or adults with medical conditions, choose Clinical. This rule applies even when the intervention or exposure has metabolic, molecular, biomarker, omics, pathway, or mechanistic rationale. Do not choose Mechanism for this pattern unless the review primarily synthesizes causal pathway biology rather than patient-facing evidence. Do not choose Methods unless the review primarily evaluates assay/sample/workflow/calibration/quality-control methodology.
        3. Center-of-Gravity Check: What would be lost if the paper's central contribution were removed? Use this answer before counting cue words.
        4. Review Fallback: Disease-focused clinical evidence reviews remain Clinical unless the main contribution is explicit pathway biology or method/workflow evaluation. Clinical-benefit reviews of interventions or exposures in adults with disease remain Clinical. A title pattern such as "Clinical Benefits of [intervention/exposure] in Adults with Disease: A Systematic Review" is Clinical under the current three-slot taxonomy.
        5. Methods Boundary Check: If the primary novelty is a measurement platform, assay workflow, analytical validation, cutoff calibration, precision/linearity, platform benchmark, head-to-head assay comparison, reference dataset, reporting checklist, reproducibility benchmark, quality-control panel, or measurement-performance characterization, choose Methods even when diagnostic/prognostic endpoints are reported or disease cohorts are included.
        6. Methods Review Boundary Check: If a systematic review, scoping review, guideline-like methods paper, or resource paper primarily synthesizes sample handling, pre-analytical variables, calibration, harmonization, quality control, analytical reproducibility, assay workflow, staining/image-analysis workflow, sequencing preprocessing, benchmark datasets, reporting standards, or mass-spectrometry/metabolomics sample-preparation protocols, choose Methods. Keep this Methods even when the paper mentions biomarkers, omics, neurodegeneration, cancer, inflammatory disease, or clinical sample labels. Do not choose Mechanism unless the review/resource primarily synthesizes causal pathway biology or disease-state mechanisms. Do not choose Methods for clinical-benefit reviews unless the methods/workflow itself is the object of synthesis.
        7. Clinical Utility Boundary Check: If biomarkers or assays are tools inside a patient-facing screening, prognosis, risk prediction, triage, memory-clinic, population-screening, or patient-management question, choose Clinical unless the assay/platform itself is the object of development or benchmarking.
        8. Mechanism Check: Choose Mechanism for original or synthesized causal biology, pathway, molecular, animal, or cell-mechanism work. Do not choose Mechanism merely because a clinical intervention, exposure, biomarker, omics workflow, disease sample, or clinical-benefit review has a plausible biological mechanism.
        9. Hard-Case Anchor Check:
           - Clinical-benefit systematic reviews in adults with disease should remain Clinical unless pathway synthesis is the main contribution.
           - Disease-focused clinical evidence reviews should not become Mechanism solely from biological rationale.
           - Head-to-head assay benchmarking with clinical endpoints should remain Methods.
           - Methods-focused systematic reviews of assay handling, calibration, quality control, preprocessing, image analysis, or sample preparation should remain Methods even when disease and biomarker terms are prominent.
           - Clinic-based dementia-risk prediction should remain Clinical.
           - Population screening/classification utility should remain Clinical.
        10. Confidence and Adjudication: Set needs_adjudication=true if the center of gravity is mixed, if a review/resource taxonomy gap is driving uncertainty, or if Methods and Clinical signals are both strong.

        Return JSON STRICTLY:
        {{
            "reasoning": "Step-by-step reasoning focused on center of gravity and boundary rules.",
            "domain_in_scope": true,
            "clinical_signal": false,
            "methods_signal": false,
            "mechanism_signal": false,
            "predicted_slot": "Mechanism" | "Clinical" | "Methods",
            "confidence": 0.0,
            "needs_adjudication": false
        }}
        """
        response_content = self._make_request("slot_classification", prompt, is_json=True)
        
        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                    predicted = self._normalize_slot_prediction(data.get("predicted_slot"))
                    if predicted:
                        first_pass_confidence = self._coerce_optional_float(data.get("confidence"))
                        deterministic_slot = self._clinical_review_fallback_slot(paper, predicted)
                        if deterministic_slot:
                            self._set_slot_classification_metrics(
                                status="ok",
                                adjudication_triggered=False,
                                adjudication_reason=None,
                                final_source="deterministic_review_fallback",
                                final_slot=deterministic_slot,
                                first_pass_predicted_slot=predicted,
                                first_pass_confidence=first_pass_confidence,
                                error=None,
                            )
                            logger.info(f"   🤖 Slot Review Fallback: {current_slot} -> {deterministic_slot}")
                            return deterministic_slot

                        needs_adjudication, adjudication_reason = self._slot_analysis_requires_adjudication(data, current_slot)
                        if not needs_adjudication:
                            self._set_slot_classification_metrics(
                                status="ok",
                                adjudication_triggered=False,
                                adjudication_reason=None,
                                final_source="first_pass",
                                final_slot=predicted,
                                first_pass_predicted_slot=predicted,
                                first_pass_confidence=first_pass_confidence,
                                error=None,
                            )
                            logger.info(f"   🤖 Slot Verified: {current_slot} -> {predicted}")
                            return predicted

                        adjudication_prompt = self._build_slot_adjudication_prompt(
                            evidence_bundle=evidence_bundle,
                            current_slot=current_slot,
                            first_pass_analysis=data,
                        )
                        adjudication_response = self._make_request(
                            SLOT_ADJUDICATION_TASK,
                            adjudication_prompt,
                            is_json=True,
                        )
                        if adjudication_response:
                            adjudication_data = self._extract_json(adjudication_response)
                            adjudicated_slot = self._normalize_slot_prediction(
                                adjudication_data.get("predicted_slot") if adjudication_data else None
                            )
                            if adjudicated_slot:
                                self._set_slot_classification_metrics(
                                    status="ok",
                                    adjudication_triggered=True,
                                    adjudication_reason=adjudication_reason,
                                    final_source="adjudicated",
                                    final_slot=adjudicated_slot,
                                    first_pass_predicted_slot=predicted,
                                    first_pass_confidence=first_pass_confidence,
                                    error=None,
                                )
                                logger.info(f"   🤖 Slot Adjudicated: {current_slot} -> {adjudicated_slot}")
                                return adjudicated_slot

                        self._set_slot_classification_metrics(
                            status="ok",
                            adjudication_triggered=True,
                            adjudication_reason=adjudication_reason,
                            final_source="first_pass_fallback",
                            final_slot=predicted,
                            first_pass_predicted_slot=predicted,
                            first_pass_confidence=first_pass_confidence,
                            error=None,
                        )
                        logger.info(f"   🤖 Slot Verified (first pass fallback): {current_slot} -> {predicted}")
                        return predicted
            except Exception:
                pass
        
        self._set_slot_classification_metrics(
            status="failed",
            adjudication_triggered=False,
            adjudication_reason=None,
            final_source="original_slot",
            final_slot=current_slot,
            first_pass_predicted_slot=None,
            first_pass_confidence=None,
            error="classification_verification_failed",
        )
        logger.warning("   ⚠️ Classification verification failed. Keeping original slot.")
        return current_slot

    def tag_paper(self, paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Hybrid Tagging: Extraction (Hard) + Generation (Soft)"""
        # from src.schemas import PaperTagging # Delayed import to avoid circular dependency if any - already imported
        self._set_tagging_metrics(status="started")

        # [NEW] Alias Injection
        alias_prompt_section = self._entity_alias_prompt_section()

        system_prompt = f"""
        Perform Hybrid Tagging for this research paper.
        
        1. **Analysis**: Understand the main topic, species used, and key findings.
        2. **Soft Tagging (Generation)**: Generate **at least 3 keywords** (Soft Tags).
           - **Format**: `#Category/Subcategory` or `#Concept` (Obsidian style).
           - **STRICT FORMATTING**: 
             - Use **Forward Slash (/)** for hierarchy (e.DO NOT** use `>`.
             - **NO SPACES**: Use `CamelCase` or `snake_case` (e.g., `#ClinicalTrial`, `#TripleNegativeBreastCancer`).
             - **NO Special Characters**: Remove `&`, `:`.
           - **Authority**: Use standard MeSH terms adapted to this format.
           - **Hierarchy**: Include at least one broad category tag (e.g., `#Medicine/Oncology` or `#Medicine/Immunology`).
           - **No Repeats**: **DO NOT** use words that already appear in the **TITLE**. Add NEW context.
           - **FAIL-SAFE**: Even if hard extraction fails, YOU MUST GENERATE SOFT TAGS.
        {alias_prompt_section}
           
        3. **Hard Tagging (Extraction)**: Extract exact values if present. If not found, use null.
           - 'species': 'mouse', 'human', etc.
           - 'sample_size': n number (integer)
           - 'model': e.g., '5xFAD', 'HeLa'
           - 'design': one of 'parallel_rct', 'crossover_rct', 'nonrandomized', 'observational', 'systematic_review', 'meta_analysis'
           - 'study_type': e.g., 'Clinical Trial', 'Observational Study', 'Systematic Review', 'Meta-analysis', 'Methods Paper'

        4. **Evidence & Confidence (Mandatory)**:
           - **evidence_span**: Quote the EXACT sentence or phrase from the abstract/title that justifies your tags.
           - **confidence**: A score between 0.0 and 1.0 indicating how sure you are about the tags and classification.
        
        Return JSON ONLY in the following structure:
        {{
            "hard_tags": {{
                "species": "extracted species or null",
                "sample_size": integer or null, 
                "model": "extracted model or null",
                "design": "extracted design or null",
                "study_type": "extracted study type or null"
            }}, 
            "soft_tags": ["#Category/Subcategory", "#AnotherTag"],
            "evidence_span": "Quote from text...",
            "confidence": 0.8,
            "reasoning": "Reasoning..."
        }}
        
        Example Output (Structure Reference):
        {{
            "hard_tags": {{"species": "human", "sample_size": 120, "model": null, "design": "observational", "study_type": "Observational Study"}},
            "soft_tags": ["#Medicine/Oncology", "#LiquidBiopsy", "#Biomarker"],
            "evidence_span": "We analyzed plasma circulating tumor DNA in 120 patients with metastatic breast cancer...",
            "confidence": 0.95,
            "reasoning": "Paper reports a human oncology biomarker study with clear clinical context."
        }}
        
        Rules:
        - If 'hard_tags' are not found, return dictionary with null values.
        - **'soft_tags' MUST NOT be empty and MUST START WITH #.**
        - **NEVER return an empty list for 'soft_tags'.**
        - Set `needs_adjudication` to true only if the result is weak, malformed, or needs a repair pass; otherwise false.
        - **DO NOT WRAP the response in 'content' or 'response' keys. return the schema keys at the ROOT.**
        """
        evidence_bundle = self._paper_evidence_bundle(paper, max_chars=6500, per_section_chars=1200)
        user_prompt = f"""
        Paper Evidence Bundle:
        {evidence_bundle}
        """
        
        # Use System Prompt + User Prompt. Enable JSON mode for stability.
        response_content = self._make_request("tagging", user_prompt, is_json=True, schema=None, system_prompt=system_prompt)
        
        if response_content:
            data: Optional[Dict[str, Any]] = None
            first_pass_validated_payload: Optional[Dict[str, Any]] = None
            adjudication_reason: Optional[str] = None
            try:
                data = self._extract_json(response_content)
                if not data:
                    self._set_tagging_metrics(
                        status="json_parse_failed",
                        adjudication_triggered=False,
                        adjudication_reason=None,
                        final_source=None,
                        first_pass_confidence=None,
                        final_confidence=None,
                        first_pass_soft_tag_count=0,
                        final_soft_tag_count=0,
                        evidence_span_present=False,
                        validation_error=None,
                        error="empty_or_unparseable_json",
                    )
                    logger.warning("Extracted JSON was None/Empty")
                    return None

                first_pass_confidence = self._coerce_optional_float(data.get("confidence"))
                first_pass_soft_tag_count = len(self._normalized_soft_tags(data.get("soft_tags")))

                try:
                    tagging_result = self._validate_tagging_payload(data, paper)
                    first_pass_validated_payload = tagging_result.model_dump()
                    first_pass_decision_payload = dict(first_pass_validated_payload)
                    if "needs_adjudication" in data:
                        first_pass_decision_payload["needs_adjudication"] = data.get("needs_adjudication")
                    needs_adjudication, adjudication_reason = self._tagging_requires_adjudication(first_pass_decision_payload)
                    if not needs_adjudication:
                        self._set_tagging_metrics(
                            status="ok",
                            adjudication_triggered=False,
                            adjudication_reason=None,
                            final_source="first_pass",
                            first_pass_confidence=first_pass_confidence,
                            final_confidence=self._coerce_optional_float(first_pass_validated_payload.get("confidence")),
                            first_pass_soft_tag_count=first_pass_soft_tag_count,
                            final_soft_tag_count=len(self._normalized_soft_tags(first_pass_validated_payload.get("soft_tags"))),
                            evidence_span_present=bool(str(first_pass_validated_payload.get("evidence_span") or "").strip()),
                            validation_error=None,
                            error=None,
                        )
                        return first_pass_validated_payload
                except Exception as validation_error:
                    adjudication_reason = "schema_invalid"
                    self._set_tagging_metrics(
                        status="adjudicating",
                        adjudication_triggered=True,
                        adjudication_reason=adjudication_reason,
                        final_source=None,
                        first_pass_confidence=first_pass_confidence,
                        final_confidence=None,
                        first_pass_soft_tag_count=first_pass_soft_tag_count,
                        final_soft_tag_count=0,
                        evidence_span_present=bool(str(data.get("evidence_span") or "").strip()),
                        validation_error=str(validation_error),
                        error=None,
                    )
                    logger.warning(f"Initial tagging validation failed; attempting adjudication repair: {validation_error}")
                else:
                    self._set_tagging_metrics(
                        status="adjudicating",
                        adjudication_triggered=True,
                        adjudication_reason=adjudication_reason,
                        final_source=None,
                        first_pass_confidence=first_pass_confidence,
                        final_confidence=None,
                        first_pass_soft_tag_count=first_pass_soft_tag_count,
                        final_soft_tag_count=0,
                        evidence_span_present=bool(str(first_pass_validated_payload.get("evidence_span") or "").strip()),
                        validation_error=None,
                        error=None,
                    )

                adjudication_prompt = self._build_tagging_adjudication_prompt(
                    evidence_bundle=evidence_bundle,
                    first_pass_analysis=data,
                )
                adjudication_response = self._make_request(
                    TAGGING_ADJUDICATION_TASK,
                    adjudication_prompt,
                    is_json=True,
                )
                if adjudication_response:
                    adjudication_data = self._extract_json(adjudication_response)
                    if adjudication_data:
                        repaired_result = self._validate_tagging_payload(adjudication_data, paper)
                        repaired_payload = repaired_result.model_dump()
                        self._set_tagging_metrics(
                            status="ok",
                            adjudication_triggered=True,
                            adjudication_reason=adjudication_reason,
                            final_source="adjudicated",
                            first_pass_confidence=first_pass_confidence,
                            final_confidence=self._coerce_optional_float(repaired_payload.get("confidence")),
                            first_pass_soft_tag_count=first_pass_soft_tag_count,
                            final_soft_tag_count=len(self._normalized_soft_tags(repaired_payload.get("soft_tags"))),
                            evidence_span_present=bool(str(repaired_payload.get("evidence_span") or "").strip()),
                            validation_error=self.last_tagging_metrics.get("validation_error"),
                            error=None,
                        )
                        return repaired_payload

                if first_pass_validated_payload is not None:
                    self._set_tagging_metrics(
                        status="ok",
                        adjudication_triggered=True,
                        adjudication_reason=adjudication_reason,
                        final_source="first_pass_fallback",
                        first_pass_confidence=first_pass_confidence,
                        final_confidence=self._coerce_optional_float(first_pass_validated_payload.get("confidence")),
                        first_pass_soft_tag_count=first_pass_soft_tag_count,
                        final_soft_tag_count=len(self._normalized_soft_tags(first_pass_validated_payload.get("soft_tags"))),
                        evidence_span_present=bool(str(first_pass_validated_payload.get("evidence_span") or "").strip()),
                        validation_error=self.last_tagging_metrics.get("validation_error"),
                        error=None,
                    )
                    return first_pass_validated_payload

                tagging_result = self._validate_tagging_payload(data, paper)
                final_payload = tagging_result.model_dump()
                self._set_tagging_metrics(
                    status="ok",
                    adjudication_triggered=False,
                    adjudication_reason=None,
                    final_source="first_pass",
                    first_pass_confidence=first_pass_confidence,
                    final_confidence=self._coerce_optional_float(final_payload.get("confidence")),
                    first_pass_soft_tag_count=first_pass_soft_tag_count,
                    final_soft_tag_count=len(self._normalized_soft_tags(final_payload.get("soft_tags"))),
                    evidence_span_present=bool(str(final_payload.get("evidence_span") or "").strip()),
                    validation_error=None,
                    error=None,
                )
                return final_payload
            except Exception as e:
                self._set_tagging_metrics(
                    status="failed",
                    adjudication_triggered=bool(adjudication_reason),
                    adjudication_reason=adjudication_reason,
                    final_source=None,
                    first_pass_confidence=self._coerce_optional_float(data.get("confidence")) if isinstance(data, dict) else None,
                    final_confidence=None,
                    first_pass_soft_tag_count=len(self._normalized_soft_tags(data.get("soft_tags"))) if isinstance(data, dict) else 0,
                    final_soft_tag_count=0,
                    evidence_span_present=bool(str(data.get("evidence_span") or "").strip()) if isinstance(data, dict) else False,
                    validation_error=self.last_tagging_metrics.get("validation_error"),
                    error=str(e),
                )
                logger.error(f"Error parsing tagging result: {e}. Content: {response_content[:100]}...")
                return None
        
        self._set_tagging_metrics(
            status="provider_empty",
            adjudication_triggered=False,
            adjudication_reason=None,
            final_source=None,
            first_pass_confidence=None,
            final_confidence=None,
            first_pass_soft_tag_count=0,
            final_soft_tag_count=0,
            evidence_span_present=False,
            validation_error=None,
            error="provider_returned_no_content",
        )
        return None

    def evaluate_escalation(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """Escalation Gate: Re-evaluate 'Pending Review' papers with a stricter Judge logic."""
        fast_reject_reason, fast_reject_code = self._escalation_fast_reject(paper)
        if fast_reject_reason:
            return self._build_escalation_result(
                paper=paper,
                approved=False,
                new_confidence=0.0,
                reason=fast_reject_reason,
                reason_codes=[fast_reject_code] if fast_reject_code else None,
                final_route=ESCALATION_ROUTE_REVIEW,
            )

        fast_approve_reason, fast_approve_code = self._escalation_fast_approve(paper)
        if fast_approve_reason:
            return self._build_escalation_result(
                paper=paper,
                approved=True,
                new_confidence=0.96,
                reason=fast_approve_reason,
                reason_codes=[fast_approve_code] if fast_approve_code else None,
                final_route=ESCALATION_ROUTE_APPROVE,
            )

        prompt = self._build_escalation_prompt(paper)
        
        response_content = self._make_request("escalation", prompt, is_json=True)
        
        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                    approved = bool(data.get("approved", False))
                    return self._build_escalation_result(
                        paper=paper,
                        approved=approved,
                        new_confidence=float(data.get("new_confidence", 0.0) or 0.0),
                        reason=str(data.get("reason", "No reason provided")),
                        reason_codes=self._normalize_escalation_reason_codes(
                            data.get("reason_codes"),
                            approved=approved,
                        ),
                        final_route=str(data.get("final_route") or "").strip() or None,
                    )
            except Exception:
                logger.warning("Failed to parse Escalation Judge response.")
        
        return self._build_escalation_result(
            paper=paper,
            approved=False,
            new_confidence=0.0,
            reason="Judge Error",
            reason_codes=["JUDGE_ERROR"],
            final_route=ESCALATION_ROUTE_REVIEW,
        )

    def analyze_relevance(self, paper: Dict[str, Any], rq: str) -> Optional[Dict[str, str]]:
        """[NEW] Ticket 7: Context-Aware Summarization Logic"""
        prompt = f"""
        You are a research assistant helping to answer a specific Research Question (RQ).
        
        MY RESEARCH QUESTION: "{rq}"
        
        Analyze the following paper to extract insights relevant to my RQ.
        
        Paper:
        - Title: {paper.get('title', 'N/A')}
        - Abstract: {paper.get('summary', 'N/A')}
        
        Identify:
        1. **Gap**: What specific gap or problem does this paper address that is relevant to my RQ?
        2. **Insight**: What key finding or method in this paper directly helps answer my RQ?
        3. **Limitation**: What are the limitations of this paper in the context of my RQ?
        
        Return JSON STRICTLY:
        {{
            "gap": "1-2 sentences...",
            "insight": "1-2 sentences...",
            "limitation": "1-2 sentences..."
        }}
        """
        
        response_content = self._make_request("relevance_analysis", prompt, is_json=True)
        
        if response_content:
            try:
                data = self._extract_json(response_content)
                if data:
                    return {
                        "gap": data.get("gap", "N/A"),
                        "insight": data.get("insight", "N/A"),
                        "limitation": data.get("limitation", "N/A")
                    }
            except Exception:
                logger.warning("Failed to parse Relevance Analysis response.")
        
        return None

    def find_related_papers(self, target_paper_id: str, all_papers_vectors: Dict[str, List[float]], top_k: int = 3) -> List[Any]:
        """
        Smart Linking: Finds related papers based on embedding similarity.
        Requires pre-computed embeddings for all papers.
        """
        if target_paper_id not in all_papers_vectors:
            logger.warning(f"Target paper ID '{target_paper_id}' not found in provided vectors.")
            return []
        
        target_vec = np.array(all_papers_vectors[target_paper_id])
        
        # Handle zero vector case
        if np.linalg.norm(target_vec) == 0:
            logger.warning(f"Target paper '{target_paper_id}' has a zero embedding vector. Cannot compute similarity.")
            return []

        results = []
        
        for pid, vec in all_papers_vectors.items():
            if pid == target_paper_id:
                continue
            
            current_vec = np.array(vec)
            
            # Handle zero vector case for current paper
            norm_current_vec = np.linalg.norm(current_vec)
            if norm_current_vec == 0:
                logger.debug(f"Skipping paper '{pid}' due to zero embedding vector.")
                continue

            # Cosine similarity
            similarity = np.dot(target_vec, current_vec) / (np.linalg.norm(target_vec) * norm_current_vec)
            results.append((pid, similarity))
        
        # Sort desc
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


class OpenAIProvider(LLMProvider):
    """OpenAI API를 사용하는 LLM 공급자"""
    def _initialize(self):
        # Resolve API Key based on mode or fallback
        api_key = None
        if self.config.cloud and self.config.cloud.api_key:
            api_key = self.config.cloud.api_key
        
        if not api_key:
            logger.warning("OpenAI API key is not configured. OpenAI features will be disabled.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)

    def _get_model(self, task: str) -> str:
        # If cloud config has specific model per task, use it
        if self.config.cloud and self.config.cloud.model:
            return self.config.cloud.model
        # Otherwise, fall back to the generic LLMProvider logic
        return super()._get_model(task)

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """중앙화된 API 요청 핸들러 (재시도, 타임아웃, 에러 처리)"""
        if not self.is_available():
            return None

        model = self._get_model(task)
        logger.info(f"Making LLM request to model '{model}' for task '{task}'.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": self._temperature_for_task(task),
            "timeout": self.config.timeout_seconds,
        }
        if is_json or schema: # OpenAI uses response_format for JSON, schema is not directly passed
            request_params["response_format"] = {"type": "json_object"}

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**request_params)
                return response.choices[0].message.content
            except RateLimitError:
                wait_time = 2 ** (attempt + 1) # 2초, 4초, 8초 대기
                logger.warning(f"LLM RateLimit hit on attempt {attempt + 1}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                if attempt >= self.config.max_retries:
                    logger.error("LLM RateLimit exceeded. Please check OpenAI credit balance.")
                    return "❌ AI Error: Rate Limit (Check Billing)"
            except APITimeoutError:
                logger.warning(f"LLM Timeout on attempt {attempt + 1}. Retrying...")
                if attempt >= self.config.max_retries:
                    logger.error("LLM Timeout exceeded.")
                    return "❌ AI Error: Timeout"
            except APIStatusError as e:
                logger.error(f"LLM API Error: {e.status_code} - {e.message}")
                return f"❌ AI Error: {e.message}"
            except Exception as e:
                logger.exception(f"An unexpected error occurred during LLM request: {e}")
                return "❌ AI Error: An unexpected error occurred."
        return None
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        if not self.is_available():
            return None
        try:
            # Use the embedding model specified in config, or a default
            embedding_model = self.config.cloud.embedding_model if self.config.cloud and self.config.cloud.embedding_model else "text-embedding-3-small"
            resp = self.client.embeddings.create(input=text, model=embedding_model)
            return resp.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            return None


class AnthropicProvider(LLMProvider):
    """Anthropic API를 사용하는 LLM 공급자"""

    def _initialize(self):
        api_key = None
        if self.config.cloud and self.config.cloud.api_key:
            api_key = self.config.cloud.api_key

        if not api_key:
            logger.warning("Anthropic API key is not configured. Anthropic features will be disabled.")
            self.client = None
            return

        try:
            self.client = _anthropic_client(api_key, timeout_seconds=self.config.timeout_seconds)
        except Exception as exc:
            logger.warning(f"Anthropic client initialization failed: {exc}. Anthropic features will be disabled.")
            self.client = None

    def _get_model(self, task: str) -> str:
        if self.config.cloud and self.config.cloud.model:
            return self.config.cloud.model
        return super()._get_model(task)

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        if not self.is_available():
            return None

        model = self._get_model(task)
        logger.info(f"Making Anthropic request to model '{model}' for task '{task}'.")

        system_parts: List[str] = []
        if system_prompt:
            system_parts.append(system_prompt)
        if is_json or schema:
            json_instruction = (
                "Return only a valid JSON object at the root. "
                "Do not use Markdown fences, commentary, or wrapper keys unless the schema requires them."
            )
            if schema:
                try:
                    json_instruction = f"{json_instruction}\n\nSchema:\n{json.dumps(schema, ensure_ascii=False)}"
                except Exception:
                    pass
            system_parts.append(json_instruction)

        request_params: Dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "temperature": self._temperature_for_task(task),
            "messages": [{"role": "user", "content": prompt}],
        }
        system_text = "\n\n".join(part.strip() for part in system_parts if str(part).strip())
        if system_text:
            request_params["system"] = system_text

        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.messages.create(**request_params)
                return _extract_anthropic_text(response)
            except Exception as exc:
                if attempt >= self.config.max_retries:
                    logger.exception(f"Anthropic request failed for model '{model}': {exc}")
                    return f"❌ AI Error: {exc}"
                wait_time = 2 ** (attempt + 1)
                logger.warning(
                    f"Anthropic request failed on attempt {attempt + 1} for task '{task}'. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
        return None

    def get_embedding(self, text: str) -> Optional[List[float]]:
        logger.warning("Anthropic provider does not currently support embeddings in PaperPipe.")
        return None


def _build_cloud_provider(config: LLMConfig, entity_aliases: Dict[str, str] = None) -> LLMProvider:
    provider = _cloud_provider_name(config)
    if provider == "anthropic":
        return AnthropicProvider(config, entity_aliases)
    return OpenAIProvider(config, entity_aliases)

class OllamaProvider(LLMProvider):
    """Ollama API를 사용하는 LLM 공급자"""
    def _initialize(self):
        # Ollama client is implicit via library but we can configure base_url
        self.host = self.config.local.base_url if self.config.local else "http://localhost:11434"
        self.models = self.config.local.models if self.config.local else {}
        
        try:
            # Test connection by creating a client instance
            self.ollama_client = ollama.Client(
                host=self.host,
                timeout=self.config.timeout_seconds,
            )
            # Attempt to list models to confirm connectivity
            self.ollama_client.list()
            self.client = True # Mark as available
            logger.info(f"Ollama connected successfully at {self.host}")
        except Exception as e:
            logger.warning(f"Ollama connection failed at {self.host}: {e}. Ollama features will be disabled.")
            self.client = None
            self.ollama_client = None

    def _get_model(self, task: str) -> str:
        task = self._normalize_task_name(task)
        # Map task to local models defined in config, with fallbacks
        if self.models:
            if task in {SPECIALTY_TRIAL_EXTRACTION_TASK, "clinical_extraction"}:
                return self.models.get("extractor", "llama3:8b")
            if task == "slot_classification":
                return self.models.get("classifier", "llama3:8b")
            if task == "tagging":
                return self.models.get("tagger", "biomistral:7b")
            if task == "escalation":
                return self.models.get("judge", "llama3:latest")
            if task == "teacher_review":
                return self.models.get("teacher_review", self.models.get("chat", "phi3"))
            if task == "one_liner":
                return self.models.get("one_liner", "phi3")
            if task == "deep_read":
                return self.models.get("deep_read", "llama3:8b")
            if task == "relevance_analysis":
                return self.models.get("relevance_analyzer", "llama3:8b")
        
        # Fallback to a general chat model if specific task model not found
        return self.models.get("chat", "phi3")

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        if not self.is_available():
            return None

        model = self._get_model(task)
        logger.info(f"Making LLM request to Ollama model '{model}' for task '{task}'.")

        options = {
            "temperature": self._temperature_for_task(task),
            "num_predict": 4096, # Max tokens to generate
        }
        
        # Ollama handles JSON output via the 'format' parameter
        format_param = None
        if schema:
            format_param = "json" 
        elif is_json:
            format_param = "json"

        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        try:
            response = self.ollama_client.chat(
                model=model,
                messages=messages,
                format=format_param,
                options=options
            )
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama Request Failed for model '{model}': {e}")
            return f"❌ AI Error: Ollama request failed ({model}). Check server logs."

    def get_embedding(self, text: str) -> Optional[List[float]]:
        if not self.is_available():
            return None
        try:
            embedding_model = self.models.get("embedder", "nomic-embed-text")
            response = self.ollama_client.embeddings(model=embedding_model, prompt=text)
            return response['embedding']
        except Exception as e:
            logger.error(f"Ollama embedding failed for model '{embedding_model}': {e}")
            return None

class HybridProvider(LLMProvider):
    """로컬(Ollama)과 클라우드 LLM을 조합하여 사용하는 공급자"""
    def _initialize(self):
        self.local = OllamaProvider(self.config, self.entity_aliases)
        self.cloud = _build_cloud_provider(self.config, self.entity_aliases)
        # Hybrid provider is logically available if at least one sub-provider is available
        self.client = self.local.is_available() or self.cloud.is_available()
        if not self.client:
            logger.error("Neither local nor cloud LLM providers are available in Hybrid mode.")

    def is_available(self) -> bool:
        return self.local.is_available() or self.cloud.is_available()

    def _make_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema: Optional[Dict] = None,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        # This method should not be called directly in HybridProvider,
        # as specific tasks are routed to specific sub-providers.
        # However, if a task is not explicitly routed, we can define a fallback.
        logger.warning(f"HybridProvider: Unrouted task '{task}'. Falling back to cloud if available, else local.")
        if self.cloud.is_available():
            return self.cloud._make_request(task, prompt, is_json, schema, system_prompt=system_prompt)
        elif self.local.is_available():
            return self.local._make_request(task, prompt, is_json, schema, system_prompt=system_prompt)
        else:
            logger.error(f"HybridProvider: No LLM available for task '{task}'.")
            return "❌ AI Error: No LLM available."

    def get_embedding(self, text: str) -> Optional[List[float]]:
        # Prefer local embedding for cost/speed
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for embedding.")
            return self.local.get_embedding(text)
        elif self.cloud.is_available():
            logger.debug("HybridProvider: Using cloud for embedding.")
            return self.cloud.get_embedding(text)
        logger.error("HybridProvider: No LLM available for embedding.")
        return None

    # Routing Logic for specific tasks
    def classify_slot(self, paper: Dict[str, Any], current_slot: str) -> str:
        # L1/L2 -> Local (Fast)
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for slot classification.")
            result = self.local.classify_slot(paper, current_slot)
            self.last_slot_classification_metrics = self.local.get_slot_classification_metrics()
            return result
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for slot classification, falling back to cloud.")
            result = self.cloud.classify_slot(paper, current_slot)
            self.last_slot_classification_metrics = self.cloud.get_slot_classification_metrics()
            return result
        logger.error("HybridProvider: No LLM available for slot classification.")
        self._set_slot_classification_metrics(
            status="provider_unavailable",
            adjudication_triggered=False,
            adjudication_reason=None,
            final_source="original_slot",
            final_slot=current_slot,
            first_pass_predicted_slot=None,
            first_pass_confidence=None,
            error="No LLM available for slot classification.",
        )
        return current_slot # Fallback to original if no LLM

    def tag_paper(self, paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # High volume -> Local (BioMistral)
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for tagging.")
            result = self.local.tag_paper(paper)
            self.last_tagging_metrics = self.local.get_tagging_metrics()
            return result
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for tagging, falling back to cloud.")
            result = self.cloud.tag_paper(paper)
            self.last_tagging_metrics = self.cloud.get_tagging_metrics()
            return result
        logger.error("HybridProvider: No LLM available for tagging.")
        self._set_tagging_metrics(
            status="provider_unavailable",
            adjudication_triggered=False,
            adjudication_reason=None,
            final_source=None,
            first_pass_confidence=None,
            final_confidence=None,
            first_pass_soft_tag_count=0,
            final_soft_tag_count=0,
            evidence_span_present=False,
            validation_error=None,
            error="No LLM available for tagging.",
        )
        return None

    def generate_one_liner(self, paper: Dict[str, Any]) -> Optional[str]:
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for one-liner generation.")
            return self.local.generate_one_liner(paper)
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for one-liner, falling back to cloud.")
            return self.cloud.generate_one_liner(paper)
        logger.error("HybridProvider: No LLM available for one-liner.")
        return None
    
    def extract_specialty_trial_data(
        self,
        paper: Dict[str, Any],
        methods_snippet: str = "",
    ) -> Optional[SpecialtyTrialExtraction]:
        # Trials are critical -> Prefer Cloud for accuracy, OR Local if specified
        # Spec says: "Tagging & Linking (Ollama)", "Escalation (Cloud)".
        # Trial extraction is closer to Tagging (Extraction).
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for trial data extraction.")
            result = self.local.extract_specialty_trial_data(paper, methods_snippet)
            self.last_specialty_trial_extraction_diagnostic = self.local.get_specialty_trial_extraction_diagnostic()
            self.last_specialty_trial_extraction_raw_response = self.local.get_specialty_trial_extraction_raw_response()
            return result
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for trial extraction, falling back to cloud.")
            result = self.cloud.extract_specialty_trial_data(paper, methods_snippet)
            self.last_specialty_trial_extraction_diagnostic = self.cloud.get_specialty_trial_extraction_diagnostic()
            self.last_specialty_trial_extraction_raw_response = self.cloud.get_specialty_trial_extraction_raw_response()
            return result
        logger.error("HybridProvider: No LLM available for trial data extraction.")
        self._set_specialty_trial_extraction_diagnostic(
            status="provider_unavailable",
            error="No LLM available for trial data extraction.",
        )
        self._set_specialty_trial_extraction_raw_response(None)
        return None

    def extract_trial_data(self, paper: Dict[str, Any], methods_snippet: str = "") -> Optional[SpecialtyTrialExtraction]:
        return self.extract_specialty_trial_data(paper, methods_snippet)

    def extract_biomedical_clinical_data(
        self,
        paper: Dict[str, Any],
        methods_snippet: str = "",
    ) -> Optional[BiomedicalClinicalExtraction]:
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for biomedical clinical extraction.")
            return self.local.extract_biomedical_clinical_data(paper, methods_snippet)
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for biomedical clinical extraction, falling back to cloud.")
            return self.cloud.extract_biomedical_clinical_data(paper, methods_snippet)
        logger.error("HybridProvider: No LLM available for biomedical clinical extraction.")
        return None

    def evaluate_escalation(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        # Gate 2 -> Escalation -> Cloud
        if self.cloud.is_available():
            logger.info(f"⚡️ HybridProvider: Using Cloud ({_cloud_provider_label(self.config)}) for Escalation Evaluation.")
            return self.cloud.evaluate_escalation(paper)
        
        logger.warning("HybridProvider: Cloud unavailable for escalation, falling back to local.")
        if self.local.is_available():
            return self.local.evaluate_escalation(paper)
        
        logger.error("HybridProvider: No LLM available for escalation evaluation.")
        return {"approved": False, "reason": "No LLM available for escalation."}
    
    def generate_deep_read(self, paper: Dict[str, Any]) -> Optional[str]:
        """Compatibility wrapper for legacy metadata-based deep-read helpers."""
        self._warn_legacy_deep_read_helper_used()
        # Local-first by design. Cloud is fallback when local is unavailable.
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for deep read generation.")
            return self.local._generate_legacy_deep_read_summary(paper)
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for deep read, falling back to cloud.")
            return self.cloud._generate_legacy_deep_read_summary(paper)
        logger.error("HybridProvider: No LLM available for deep read generation.")
        return None

    def analyze_relevance(self, paper: Dict[str, Any], rq: str) -> Optional[Dict[str, str]]:
        if self.local.is_available():
            logger.debug("HybridProvider: Using local for relevance analysis.")
            return self.local.analyze_relevance(paper, rq)
        elif self.cloud.is_available():
            logger.warning("HybridProvider: Local unavailable for relevance analysis, falling back to cloud.")
            return self.cloud.analyze_relevance(paper, rq)
        logger.error("HybridProvider: No LLM available for relevance analysis.")
        return None


def get_llm_provider(config: LLMConfig, entity_aliases: Dict[str, str] = None) -> Optional[LLMProvider]:
    """설정에 맞는 LLM 공급자 인스턴스를 반환"""
    if config.mode == "hybrid":
        logger.info("Initializing Hybrid LLM Provider.")
        return HybridProvider(config, entity_aliases)
    elif config.mode == "local":
        if config.local and config.local.provider == "ollama":
            logger.info("Initializing Local Ollama LLM Provider.")
            return OllamaProvider(config, entity_aliases)
        else:
            logger.error(f"Local mode specified, but no valid local provider configured: {config.local.provider if config.local else 'None'}")
            return None
    elif config.mode == "cloud":
        if config.cloud and _cloud_provider_name(config) in {"openai", "anthropic"}:
            logger.info(f"Initializing Cloud {_cloud_provider_label(config)} LLM Provider.")
            return _build_cloud_provider(config, entity_aliases)
        else:
            logger.error(f"Cloud mode specified, but no valid cloud provider configured: {config.cloud.provider if config.cloud else 'None'}")
            return None
    
    logger.error(f"Invalid LLM mode specified: {config.mode}. No LLM provider initialized.")
    return None
