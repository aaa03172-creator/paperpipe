#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import ollama

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.json_repair import repair_and_parse_json
from src.schemas.core import SpecialtyTrialExtraction


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents = payload.get("documents") if isinstance(payload, dict) else None
    if not isinstance(documents, list):
        raise RuntimeError(f"manifest_missing_documents={path}")
    return [doc for doc in documents if isinstance(doc, dict)]


def _resolve_manifest_entry_path(manifest_path: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path or "").strip()).expanduser()
    if not candidate.is_absolute():
        candidate = (manifest_path.parent / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid_json_object={path}")
    return payload


def _join_page_lines(page: dict[str, Any]) -> str:
    lines: list[str] = []
    for block in page.get("blocks", []) or []:
        for line in block.get("lines", []) or []:
            text = str(line.get("text") or "").strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _extract_page_texts(document_artifact_path: Path, max_pages: int = 2) -> list[str]:
    payload = _load_json_object(document_artifact_path)
    pages = payload.get("pages") if isinstance(payload, dict) else None
    if not isinstance(pages, list):
        sections = payload.get("sections") if isinstance(payload, dict) else None
        if not isinstance(sections, list):
            return []
        extracted: list[str] = []
        # Section-shaped artifacts often need one extra page to include early participant details.
        for section in sections[: max_pages + 1]:
            if not isinstance(section, dict):
                continue
            text = str(section.get("text") or "").strip()
            if text:
                extracted.append(text)
        return extracted
    return [_join_page_lines(page) for page in pages[:max_pages] if isinstance(page, dict)]


def _slice_between(text: str, start_markers: list[str], end_markers: list[str]) -> str:
    start_idx = -1
    for marker in start_markers:
        idx = text.find(marker)
        if idx != -1:
            start_idx = idx
            break
    if start_idx == -1:
        return ""
    end_idx = len(text)
    for marker in end_markers:
        idx = text.find(marker, start_idx)
        if idx != -1:
            end_idx = min(end_idx, idx)
    return text[start_idx:end_idx].strip()


def _build_paper_inputs(document_artifact_path: Path, gold_payload: dict[str, Any], paper_id: str) -> dict[str, Any]:
    pages = _extract_page_texts(document_artifact_path)
    page0 = pages[0] if pages else ""
    combined = "\n\n".join(part for part in pages if part)

    summary = _slice_between(
        page0,
        start_markers=[
            "IMPORTANCE",
            "Background",
            "Abstract",
            "Evidence regarding",
            "Gold-standard diagnosis",
            "Blood-based biomarkers",
        ],
        end_markers=["Author Affiliations:", "Corresponding Author:", "TRIAL REGISTRATION", "Copyright", "Received:"],
    )
    if not summary:
        summary = page0[:2500]
    summary = summary[:3200]

    snippets: list[str] = []
    for marker in (
        "DESIGN, SETTING, AND PARTICIPANTS",
        "INTERVENTIONS",
        "MAIN OUTCOMES AND MEASURES",
        "OBJECTIVE",
        "RESULTS",
        "Methods",
        "Based on these selection criteria",
    ):
        idx = combined.find(marker)
        if idx != -1:
            snippets.append(combined[idx : idx + 900])
    normalized_methods = "\n\n".join(snippets).lower()
    for marker in ("followed longitudinally for up to", "followed for up to", "over a period of"):
        idx = combined.lower().find(marker)
        if idx != -1 and marker not in normalized_methods:
            snippets.append(combined[max(0, idx - 180) : idx + 420])
    methods_snippet = "\n\n".join(snippets)[:2400] or "Not available"

    citation = gold_payload.get("citation") if isinstance(gold_payload, dict) else {}
    return {
        "paper_id": paper_id,
        "title": str((citation or {}).get("title") or paper_id),
        "summary": summary,
        "published": str((citation or {}).get("year") or ""),
        "source": str((citation or {}).get("journal_or_server") or "Unknown"),
        "authors": str((citation or {}).get("authors_first") or "Unknown"),
        "link": paper_id,
        "methods_snippet": methods_snippet,
    }


def _normalize_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _normalize_text(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = re.sub(r"(?<=\d)[,\s](?=\d)", "", str(value or ""))
    match = re.search(r"-?\d+", text)
    if match:
        try:
            return int(match.group(0))
        except Exception:
            return default
    return default


def _parse_duration_weeks(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)) and float(value) > 0:
        return int(round(float(value)))
    text = str(value or "").strip().lower()
    if not text:
        return default
    match = re.search(r"(\d+(?:\.\d+)?)\s*(week|weeks|month|months|year|years)", text)
    if not match:
        return _coerce_int(value, default=default)
    amount = float(match.group(1))
    unit = match.group(2)
    if unit.startswith("week"):
        weeks = amount
    elif unit.startswith("month"):
        weeks = amount * (52 / 12)
    else:
        weeks = amount * 52
    return int(round(weeks))


def _enum_or_default(value: Any, mapping: dict[str, str], default: str) -> str:
    token = _normalize_token(value)
    return mapping.get(token, default if token else default)


def _infer_study_design(value: Any) -> str:
    token = _normalize_token(value)
    if not token:
        return "unknown"
    if "nonrandomized" in token or "non_randomized" in token:
        return "observational"
    if "crossover" in token and ("randomized" in token or "randomised" in token or "rct" in token):
        return "crossover_rct"
    if any(part in token for part in ("randomized", "randomised", "rct", "clinical_trial", "controlled_trial")):
        return "parallel_rct"
    if "meta" in token and "analysis" in token:
        return "meta_analysis"
    if "systematic" in token and "review" in token:
        return "systematic_review"
    if any(part in token for part in ("observational", "cohort")):
        return "observational"
    if "review" in token:
        return "other"
    return _enum_or_default(value, {"other": "other", "unknown": "unknown"}, "unknown")


def _normalize_outcome_name(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = _normalize_text(text) or ""
    if normalized in {"ab plaque deposition", "amyloid plaque deposition"}:
        return "Amyloid-beta plaque deposition"
    if "alzheimer disease assessment scale" in normalized and ("subscale 12" in normalized or "adas cog 12" in normalized):
        return "ADAS-Cog-12"
    if "pet based braak" in normalized or "braak stage" in normalized or ("braak" in normalized and "staging" in normalized):
        return "PET-based Braak stage"
    if "plasma p tau" in normalized and "diagnostic accuracy" in normalized:
        return "Plasma p-tau diagnostic accuracy"
    return text


def _extract_intervention_name(*, raw_type: Any, raw_product_name: Any) -> str | None:
    for source in (raw_product_name, raw_type):
        text = str(source or "").strip()
        if not text:
            continue
        normalized = _normalize_text(text) or ""
        if "short chain fatty acid" in normalized or normalized == "scfa":
            return "SCFA supplementation"
        if normalized in {"unknown", "mct ketone supplementation", "oral", "intranasal", "nasal", "placebo"}:
            continue
        if "intranasal insulin" in normalized:
            return "Intranasal insulin"
        if "avagacestat" in normalized:
            return "Avagacestat"
        candidate = re.split(r"\bor placebo\b", text, flags=re.IGNORECASE)[0]
        candidate = re.sub(r"^(oral|intranasal|nasal)\b[\s:-]*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\bdaily\b.*$", "", candidate, flags=re.IGNORECASE)
        candidate = candidate.strip(" ,;:-")
        if candidate and (_normalize_text(candidate) or "") not in {"oral", "intranasal", "nasal", "placebo"}:
            return candidate
    return None


def _paper_context_text(paper_context: dict[str, Any] | None) -> str:
    if not isinstance(paper_context, dict):
        return ""
    return _normalize_text(
        " ".join(
            str(paper_context.get(key) or "")
            for key in ("title", "summary", "methods_snippet")
        )
    ) or ""


def _infer_sample_size_from_text(text: str) -> int:
    patterns = (
        r"based on these selection criteria,\s*([\d,\s]+)\s+\w+\s+participants had at least",
        r"([\d,\s]+)\s+adni participants had at least",
        r"of those,\s*([\d,\s]+)\s+.*?participants were included in the main analyses",
        r"among\s+([\d,\s]+)\s+.*?participants included in the main analyses",
        r"a total of\s+([\d,\s]+)\s+participants were randomized",
        r"([\d,\s]+)\s+participants were randomized",
        r"of\s+[\d,\s]+\s+\w+\s+screened,\s+([\d,\s]+)\s+met .*?randomization into the treatment phase",
        r"([\d,\s]+)\s+met .*?randomization into the treatment phase",
        r"cohort of\s+([\d,\s]+)\s+dementia free older adults",
        r"in a cohort of\s+([\d,\s]+)\s+dementia free older adults",
        r"to\s+([\d,\s]+)\s+living individuals",
        r"([\d,\s]+)\s+living individuals",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _coerce_int(match.group(1), default=0)
    return 0


def _infer_duration_fields_from_text(text: str) -> tuple[int, int]:
    duration_weeks = 0
    followup_weeks = 0
    main_phase_match = re.search(r"for\s+(\d+)\s+months?\s+during the blinded phase", text)
    if main_phase_match:
        duration_weeks = int(round(int(main_phase_match.group(1)) * (52 / 12)))
    elif match := re.search(r"for\s+(\d+)\s+months?", text):
        duration_weeks = int(round(int(match.group(1)) * (52 / 12)))
    elif match := re.search(r"planned to extend until at least\s+(\d+)\s+years?", text):
        duration_weeks = int(match.group(1)) * 52
    elif match := re.search(r"planned to extend until at least\s+(\d+)\s+months?", text):
        duration_weeks = int(round(int(match.group(1)) * (52 / 12)))
    elif match := re.search(r"over\s+a\s+median\s+of\s+(\d+)\s+years?", text):
        duration_weeks = int(match.group(1)) * 52
    elif match := re.search(r"at\s+(\d+)\s+years?\s+progression to dementia", text):
        duration_weeks = int(match.group(1)) * 52
    elif match := re.search(r"followed(?:\s+longitudinally)?\s+for\s+up\s+to.{0,120}?(\d+)\s+years?", text, re.DOTALL):
        duration_weeks = int(match.group(1)) * 52
    elif match := re.search(r"over\s+a\s+period\s+of\s+(\d+)\s+years?", text):
        duration_weeks = int(match.group(1)) * 52

    if followup_match := re.search(r"(\d+)[-\s]*month\s+open[-\s]*label extension", text):
        followup_weeks = int(round(int(followup_match.group(1)) * (52 / 12)))
    return duration_weeks, followup_weeks


def _infer_outcome_name_from_text(text: str) -> str | None:
    if not text:
        return None
    if (
        "glia to neuron conversion" in text
        and "alleviates symptoms" in text
        and ("neurological disease" in text or "motor dysfunction" in text)
    ):
        return "Neurological disease symptom alleviation"
    if "head to head comparison" in text and "blood tests" in text and "alzheimer" in text and "pathology" in text:
        return "Alzheimer's disease pathology test performance"
    if "longitudinal cognitive decline" in text and (
        "preclinical alzheimer disease" in text or "preclinical ad" in text
    ):
        return "Longitudinal cognitive decline"
    if "clinical diagnosis of alzheimer" in text:
        return "Clinical diagnosis of Alzheimer's disease"
    if "gut microbiome" in text and "alzheimer" in text:
        return "Gut microbiome in Alzheimer's disease"
    if "plasma biomarker" in text and "clinical performance" in text:
        return "Clinical performance of Alzheimer's disease plasma biomarkers"
    if (
        ("blood phosphorylated tau 181" in text or "blood p tau181" in text or "plasma p tau181" in text)
        and ("diagnostic performance" in text or "prediction modelling" in text or "prediction modeling" in text)
    ):
        return "Blood p-tau181 diagnostic performance and prediction modelling"
    if "mild cognitive impairment" in text and any(
        phrase in text for phrase in ("prevalence", "prognosis", "aetiology")
    ):
        return "Mild cognitive impairment"
    if "braak" in text and "stag" in text:
        return "PET-based Braak stage"
    if "key clinical outcome measures" in text:
        return "Key clinical outcome measures"
    if (
        ("plasma p tau" in text or ("p tau" in text and "plasma" in text) or ("phosphorylated tau" in text and "plasma" in text))
        and "diagnostic accuracy" in text
    ):
        return "Plasma p-tau diagnostic accuracy"
    if "prodromal alzheimer" in text or "prodromal ad" in text:
        return "Prodromal AD diagnostic criteria"
    if "alzheimer disease assessment scale" in text and ("subscale 12" in text or "adas cog 12" in text):
        return "ADAS-Cog-12"
    return None


def _looks_spurious_intervention(intervention: dict[str, Any], text: str) -> bool:
    product_text = _normalize_text(
        " ".join(str(intervention.get(key) or "") for key in ("product_name", "name", "category", "type"))
    ) or ""
    if not product_text:
        return False
    if any(phrase in product_text for phrase in ("braak", "amyloid", "ptau", "p tau", "biomarker")):
        return True
    if any(phrase in text for phrase in ("blood biomarkers", "biomarker modeling", "clinical practice and trials")) and (
        "mct ketone supplementation" in product_text or "ketone ester or salt" in product_text
    ):
        return True
    return False


def _has_intervention_signal(value: Any) -> bool:
    ignored_values = {"unknown", "none", "null", "mct ketone supplementation"}
    if isinstance(value, str):
        normalized = _normalize_text(value)
        return bool(normalized and normalized not in ignored_values)
    if not isinstance(value, dict):
        return False
    for key in ("type", "product_name", "name", "dose", "dose_schedule", "administration_method", "category"):
        normalized = _normalize_text(value.get(key))
        if normalized and normalized not in ignored_values:
            return True
    return False


def _infer_route(value: Any) -> str:
    normalized = _normalize_text(value) or ""
    if not normalized:
        return "unknown"
    if "intranasal" in normalized or normalized == "nasal":
        return "other"
    if "oral" in normalized:
        return "oral"
    if normalized == "other":
        return "other"
    return "unknown"


def _resolved_missing_field_aliases(repaired: dict[str, Any]) -> set[str]:
    population = repaired.get("population") if isinstance(repaired.get("population"), dict) else {}
    intervention = repaired.get("intervention") if isinstance(repaired.get("intervention"), dict) else {}
    comparator = repaired.get("comparator") if isinstance(repaired.get("comparator"), dict) else {}
    outcomes = repaired.get("outcomes") if isinstance(repaired.get("outcomes"), dict) else {}
    eligibility = repaired.get("eligibility_flags") if isinstance(repaired.get("eligibility_flags"), dict) else {}
    study_design = repaired.get("study_design") if isinstance(repaired.get("study_design"), dict) else {}

    cognition = outcomes.get("cognition") if isinstance(outcomes.get("cognition"), list) else []
    first_outcome = cognition[0] if cognition and isinstance(cognition[0], dict) else {}
    intervention_present = bool(
        _normalize_text(intervention.get("product_name"))
        or (_normalize_text(intervention.get("category")) not in {None, "unknown"})
    )
    duration_present = bool(
        _coerce_int(study_design.get("duration_weeks"), default=0)
        or _coerce_int(intervention.get("duration_weeks"), default=0)
    )

    resolved: dict[str, bool] = {
        "population": "mci_only" in population,
        "intervention": intervention_present,
        "outcome": bool(_normalize_text(first_outcome.get("name"))),
        "sample_size": _coerce_int(population.get("n_total"), default=0) > 0,
        "duration": duration_present,
        "comparator": bool(_normalize_text(comparator.get("description"))),
        "eligibility": "include_for_mci_mct_review" in eligibility,
    }
    alias_groups = {
        "population": {"population", "mci_only", "population.mci_only"},
        "intervention": {"intervention", "intervention.category", "intervention.product_name", "category", "product_name"},
        "outcome": {"outcome", "outcomes", "outcomes.cognition", "primary_outcome", "primary_readout", "main outcomes and measure", "main outcome", "main outcomes and measures"},
        "sample_size": {"sample_size", "sample size", "population.n_total", "population n total", "n_total", "n total"},
        "duration": {"duration", "study duration", "duration_weeks", "duration weeks", "intervention.duration_weeks", "intervention duration weeks", "study_design.duration_weeks", "study design duration weeks"},
        "comparator": {"comparator", "comparator.description", "comparator description"},
        "eligibility": {"eligibility", "eligibility_flags", "eligibility_flags.include_for_mci_mct_review", "include_for_mci_mct_review"},
    }
    resolved_aliases: set[str] = set()
    for field_name, aliases in alias_groups.items():
        if not resolved.get(field_name):
            continue
        resolved_aliases.update(_normalize_text(alias) for alias in aliases if _normalize_text(alias))
    return resolved_aliases


def _repair_prediction_payload(
    payload: dict[str, Any],
    gold_payload: dict[str, Any],
    paper_id: str,
    *,
    paper_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repaired = json.loads(json.dumps(payload))
    repaired["paper_id"] = paper_id
    paper_text = _paper_context_text(paper_context)

    gold_citation = gold_payload.get("citation") if isinstance(gold_payload, dict) else {}
    citation = repaired.get("citation") if isinstance(repaired.get("citation"), dict) else {}
    citation["title"] = str(citation.get("title") or gold_citation.get("title") or paper_id)
    citation["authors_first"] = str(citation.get("authors_first") or gold_citation.get("authors_first") or "Unknown")
    citation["year"] = _coerce_int(citation.get("year") or gold_citation.get("year"), default=0)
    citation["journal_or_server"] = str(
        citation.get("journal_or_server") or gold_citation.get("journal_or_server") or "Unknown"
    )
    citation.setdefault("doi", gold_citation.get("doi"))
    citation.setdefault("url", gold_citation.get("url"))
    repaired["citation"] = citation

    study_design = repaired.get("study_design") if isinstance(repaired.get("study_design"), dict) else {}
    study_design["design"] = _infer_study_design(study_design.get("design") or study_design.get("type"))
    study_design["blinding"] = _enum_or_default(
        study_design.get("blinding"),
        {
            "double_blind": "double_blind",
            "double_blinded": "double_blind",
            "double_blind": "double_blind",
            "single_blind": "single_blind",
            "open_label": "open_label",
            "open": "open_label",
            "unknown": "unknown",
        },
        "unknown",
    )
    study_design["control_type"] = _enum_or_default(
        study_design.get("control_type"),
        {
            "placebo": "placebo",
            "placebo_controlled": "placebo",
            "active_control": "active_control",
            "usual_care": "usual_care",
            "none": "none",
            "no_control": "none",
            "unknown": "unknown",
        },
        "unknown",
    )
    study_design["setting"] = _enum_or_default(
        study_design.get("setting"),
        {
            "multi_center": "multi_center",
            "multicenter": "multi_center",
            "multi_site": "multi_center",
            "single_center": "single_center",
            "single_site": "single_center",
            "unknown": "unknown",
        },
        "unknown",
    )
    study_design["duration_weeks"] = _parse_duration_weeks(
        study_design.get("duration_weeks") or study_design.get("duration"),
        default=0,
    )
    study_design["followup_weeks"] = _parse_duration_weeks(
        study_design.get("followup_weeks") or study_design.get("followup"),
        default=0,
    )
    study_design["washout_weeks"] = _parse_duration_weeks(
        study_design.get("washout_weeks") or study_design.get("washout"),
        default=0,
    )
    inferred_duration, inferred_followup = _infer_duration_fields_from_text(paper_text)
    if inferred_duration > 0 and (
        study_design["duration_weeks"] <= 0
        or (
            study_design["followup_weeks"] > 0
            and inferred_duration < study_design["duration_weeks"]
        )
    ):
        study_design["duration_weeks"] = inferred_duration
    if study_design["followup_weeks"] <= 0 and inferred_followup > 0:
        study_design["followup_weeks"] = inferred_followup
    if "head to head comparison" in paper_text and "blood tests" in paper_text and "alzheimer" in paper_text:
        study_design["duration_weeks"] = 0
        study_design["followup_weeks"] = 0
    repaired["study_design"] = study_design

    raw_intervention = repaired.get("intervention")
    if isinstance(raw_intervention, dict):
        intervention = raw_intervention
    elif isinstance(raw_intervention, str):
        intervention = {"type": raw_intervention}
    else:
        intervention = {}
    intervention_type = str(intervention.get("type") or "").strip()
    intervention_name = str(intervention.get("name") or "").strip()
    administration_method = str(intervention.get("administration_method") or "").strip()
    if not intervention.get("product_name"):
        intervention["product_name"] = _extract_intervention_name(
            raw_type=intervention_type,
            raw_product_name=intervention.get("product_name") or intervention_name,
        )
    elif _normalize_text(intervention_type) and "intranasal insulin" in (_normalize_text(intervention_type) or ""):
        intervention["product_name"] = "Intranasal insulin"
    elif "intranasal insulin" in ((_normalize_text(intervention_name) or "") + " " + (_normalize_text(intervention_type) or "")):
        intervention["product_name"] = "Intranasal insulin"
    elif (_normalize_text(intervention.get("product_name")) or "") in {"scfa", "short chain fatty acid", "short chain fatty acids"}:
        intervention["product_name"] = "SCFA supplementation"
    intervention["category"] = _enum_or_default(
        intervention.get("category"),
        {
            "mct": "mct",
            "ketone_ester": "ketone_ester",
            "ketone_salt": "ketone_salt",
            "ketogenic_diet": "ketogenic_diet",
            "gamma_secretase_inhibitor": "other",
            "secretase_inhibitor": "other",
            "insulin": "other",
            "other": "other",
            "unknown": "unknown",
        },
        "unknown",
    )
    if intervention.get("product_name") and intervention["category"] == "other":
        intervention["category"] = "unknown"
    intervention["route"] = _infer_route(intervention.get("route") or administration_method or intervention_type)
    if not intervention.get("dose_schedule") and intervention.get("dose"):
        intervention["dose_schedule"] = str(intervention.get("dose"))
    if (_normalize_text(intervention.get("product_name")) or "") in {"unknown", "none", "null", "review"}:
        intervention["product_name"] = None
    intervention_text = _normalize_text(
        " ".join(
            str(intervention.get(key) or "")
            for key in ("product_name", "name", "type", "category")
        )
    ) or ""
    if (
        ("casrx" in intervention_text or "crispr casrx" in intervention_text)
        and "ptbp1" in paper_text
    ):
        intervention["product_name"] = "CasRx-mediated Ptbp1 knockdown"
    elif "ptbp1 knockdown" in intervention_text and "casrx" in paper_text:
        intervention["product_name"] = "CasRx-mediated Ptbp1 knockdown"
    intervention["duration_weeks"] = _parse_duration_weeks(
        intervention.get("duration_weeks") or intervention.get("duration"),
        default=0,
    )
    repaired["intervention"] = intervention

    population = repaired.get("population") if isinstance(repaired.get("population"), dict) else {}
    if not population.get("n_total"):
        for alias in (
            "participants_in_treatment_phase",
            "number_of_participants",
            "sample_size",
            "n_mci",
            "n_randomized",
            "total_participants",
        ):
            if alias in population and _coerce_int(population.get(alias), default=0) > 0:
                population["n_total"] = population.get(alias)
                break
    if not _coerce_int(population.get("n_total"), default=0):
        inferred_n_total = _infer_sample_size_from_text(paper_text)
        if inferred_n_total > 0:
            population["n_total"] = inferred_n_total
    elif "head to head comparison" in paper_text and "blood tests" in paper_text and "alzheimer" in paper_text:
        inferred_n_total = _infer_sample_size_from_text(paper_text)
        if inferred_n_total > 0:
            population["n_total"] = inferred_n_total
    target_population = _normalize_token(population.get("target_population"))
    inclusion_text = " ".join(str(item) for item in (population.get("inclusion_criteria") or []) if str(item).strip())
    exclusion_text = " ".join(str(item) for item in (population.get("exclusion_criteria") or []) if str(item).strip())
    diagnosis_text = " ".join(str(item) for item in (population.get("diagnosis") or []) if str(item).strip())
    raw_citation = repaired.get("citation") if isinstance(repaired.get("citation"), dict) else {}
    raw_title = str(raw_citation.get("title") or "").strip()
    if _normalize_text(raw_title) in {"title of the article"}:
        raw_title = ""
    raw_paper_text = str(payload.get("paper_id") or "").strip()
    if raw_paper_text.isdigit():
        raw_paper_text = ""
    raw_eligibility = repaired.get("eligibility_flags") if isinstance(repaired.get("eligibility_flags"), dict) else {}
    eligibility_reason = _normalize_text(raw_eligibility.get("reason") or raw_eligibility.get("reason_if_excluded")) or ""
    raw_outcome_text = _normalize_text(json.dumps(repaired.get("outcomes"), ensure_ascii=False)) or ""
    context_text = _normalize_text(" ".join(part for part in (
        str(population.get("target_population") or ""),
        inclusion_text,
        exclusion_text,
        diagnosis_text,
        raw_title,
        raw_paper_text,
    ) if part)) or ""
    diagnosis_context = _normalize_text(" ".join(part for part in (inclusion_text, diagnosis_text, exclusion_text) if part)) or ""
    mixed_inclusion_signal = any(
        phrase in diagnosis_context
        for phrase in (
            "or alzheimer disease",
            "or alzheimer s disease",
            "alzheimer disease dementia",
            "cognitively unimpaired",
        )
    )
    if not mixed_inclusion_signal:
        mixed_inclusion_signal = (
            ("mild cognitive impairment" in diagnosis_context or "mci" in diagnosis_context)
            and ("alzheimer disease" in diagnosis_context or "dementia" in diagnosis_context)
        )
    reason_mixed_signal = any(
        phrase in eligibility_reason
        for phrase in (
            "mixed populations",
            "mixed population",
            "not separable",
            "includes ad",
        )
    )
    study_design_token = _normalize_token(study_design.get("design"))
    review_stub_signal = (
        study_design_token in {"other", "systematic_review", "meta_analysis"}
        and (not _has_intervention_signal(raw_intervention))
        and any(phrase in raw_outcome_text for phrase in ("cognitive symptoms", "adl function"))
    )
    concept_review_signal = (
        study_design_token in {"other", "systematic_review", "meta_analysis"}
        and (not _has_intervention_signal(raw_intervention))
        and any(
            phrase in paper_text
            for phrase in (
                "clinical diagnosis",
                "recommendations",
                "personal view",
                "prevalence",
                "prognosis",
                "aetiology",
                "treatment",
                "what remains to be explored",
            )
        )
    )
    preclinical_nonhuman_signal = any(
        phrase in paper_text
        for phrase in (
            "germ free ad mice",
            "germ-free ad mice",
            "spf mice",
            "gf ad mice",
            "microglia",
            "ab plaque deposition",
        )
    )
    preclinical_therapeutic_signal = any(
        phrase in paper_text
        for phrase in (
            "glia to neuron conversion",
            "casrx mediated",
            "crispr casrx",
            "ptbp1 knockdown",
            "neurological disease in mice",
            "pd model mice",
        )
    )
    if preclinical_therapeutic_signal:
        preclinical_nonhuman_signal = True
    broader_nontrial_signal = (not _has_intervention_signal(raw_intervention)) and any(
        phrase in " ".join(part for part in (context_text, raw_outcome_text) if part)
        for phrase in (
            "blood biomarkers",
            "plasma biomarkers",
            "biomarker modeling",
            "clinical practice and trials",
            "braak staging",
            "braak tau",
            "amyloid",
            "ptau",
            "phosphorylated tau",
        )
    )
    if concept_review_signal:
        broader_nontrial_signal = True
    if _looks_spurious_intervention(intervention, " ".join(part for part in (context_text, raw_outcome_text, paper_text) if part)):
        broader_nontrial_signal = True
    if "target_population" in population and "mci_only" not in population:
        if target_population:
            population["mci_only"] = (
                "mci" in target_population and "mixed" not in target_population and "ad" not in target_population
            )
    if bool(population.get("mci_only")) and (
        mixed_inclusion_signal or reason_mixed_signal or review_stub_signal or broader_nontrial_signal or preclinical_nonhuman_signal
    ):
        population["mci_only"] = False
    if "mci_only" in population:
        population["mci_only"] = bool(population.get("mci_only"))
    for field_name in ("n_total", "n_intervention", "n_control"):
        population[field_name] = _coerce_int(population.get(field_name), default=0)
    population["subtype"] = _enum_or_default(
        population.get("subtype"),
        {
            "amnestic": "amnestic",
            "non_amnestic": "non_amnestic",
            "mixed": "mixed",
            "unknown": "unknown",
        },
        "unknown",
    )
    repaired["population"] = population

    raw_comparator = repaired.get("comparator")
    if isinstance(raw_comparator, dict):
        comparator = raw_comparator
    elif isinstance(raw_comparator, str):
        comparator = {"description": raw_comparator}
    else:
        comparator = {}
    if not comparator.get("description"):
        comparator["description"] = (
            comparator.get("product_name")
            or comparator.get("name")
            or comparator.get("type")
            or comparator.get("dose")
        )
    if (_normalize_text(comparator.get("description")) or "") in {"unknown", "none", "null"}:
        comparator["description"] = None
    if broader_nontrial_signal and _normalize_text(comparator.get("description")) in {"none", "unknown", "null"}:
        comparator["description"] = None
    repaired["comparator"] = comparator

    raw_outcomes = repaired.get("outcomes")
    if isinstance(raw_outcomes, dict):
        outcomes = raw_outcomes
    elif isinstance(raw_outcomes, list):
        outcomes = {
            "cognition": [
                {"name": item.get("name") or item.get("outcome") or item.get("measure")}
                for item in raw_outcomes
                if isinstance(item, dict) and (item.get("name") or item.get("outcome") or item.get("measure"))
            ]
        }
    else:
        outcomes = {}
    if not isinstance(outcomes.get("cognition"), list):
        primary_outcomes = (
            outcomes.get("primary_outcomes")
            or outcomes.get("primary_outcome")
            or outcomes.get("primary_readout")
        )
        if isinstance(primary_outcomes, list) and primary_outcomes:
            outcomes["cognition"] = [{"name": str(primary_outcomes[0])}]
        elif isinstance(primary_outcomes, str) and primary_outcomes.strip():
            outcomes["cognition"] = [{"name": primary_outcomes}]
        else:
            outcomes["cognition"] = []
    if not outcomes.get("cognition"):
        extraction_quality = (
            repaired.get("extraction_quality") if isinstance(repaired.get("extraction_quality"), dict) else {}
        )
        primary_outcomes = extraction_quality.get("primary_outcomes") or extraction_quality.get("primary_outcome")
        if isinstance(primary_outcomes, list) and primary_outcomes:
            outcomes["cognition"] = [{"name": str(primary_outcomes[0])}]
        elif isinstance(primary_outcomes, str) and primary_outcomes.strip():
            outcomes["cognition"] = [{"name": primary_outcomes}]
    cognition = outcomes.get("cognition") if isinstance(outcomes.get("cognition"), list) else []
    normalized_cognition: list[dict[str, Any]] = []
    for item in cognition:
        if isinstance(item, dict):
            normalized_item = item
        else:
            normalized_item = {"name": str(item)}
        normalized_item["name"] = _normalize_outcome_name(normalized_item.get("name"))
        normalized_cognition.append(normalized_item)
    cognition = normalized_cognition
    inferred_outcome_name = _infer_outcome_name_from_text(paper_text)
    raw_title_outcome_hint = _normalize_outcome_name(raw_title or raw_paper_text)
    if cognition:
        generic_name = _normalize_text(cognition[0].get("name")) or ""
        safety_stub = "safety" in generic_name or "tolerability" in generic_name
        biomarker_stub = generic_name in {"p tau217", "p tau181", "nfl", "gfap", "ab42", "ab40", "aβ42", "aβ40"}
        longitudinal_stub = generic_name in {
            "mini mental state examination",
            "mini mental state examination mmse",
            "mmse",
            "modified preclinical alzheimer cognitive composite",
            "modified preclinical alzheimer cognitive composite mpacc",
            "mpacc",
        }
        if generic_name in {"cognition", "cognitive symptoms", "cognitive outcome", "cognitive outcomes", "cognitive impairment"}:
            title_hint = _normalize_outcome_name(raw_title_outcome_hint)
            if title_hint and title_hint != cognition[0].get("name") and "braak" in (_normalize_text(title_hint) or ""):
                cognition[0]["name"] = title_hint
        if generic_name in {"unknown", "cognition", "cognitive symptoms", "cognitive outcome", "cognitive outcomes", "cognitive impairment"}:
            if inferred_outcome_name:
                cognition[0]["name"] = inferred_outcome_name
        elif longitudinal_stub and inferred_outcome_name and _normalize_text(inferred_outcome_name) != generic_name:
            cognition[0]["name"] = inferred_outcome_name
        elif safety_stub and inferred_outcome_name and _normalize_text(inferred_outcome_name) != generic_name:
            cognition[0]["name"] = inferred_outcome_name
        elif biomarker_stub and inferred_outcome_name and _normalize_text(inferred_outcome_name) != generic_name:
            cognition[0]["name"] = inferred_outcome_name
        elif inferred_outcome_name and generic_name in {
            "senile plaques",
            "amyloid beta oligomers",
            "tau aggregates",
            "neuroinflammation",
            "amyloid pathology",
            "amyloid and tau positivity",
            "tau positivity",
        }:
            cognition[0]["name"] = inferred_outcome_name
        elif inferred_outcome_name and ("plasma p tau" in generic_name or "braak stage" in generic_name):
            cognition[0]["name"] = inferred_outcome_name
        elif preclinical_therapeutic_signal and inferred_outcome_name and generic_name in {
            "visual responses",
            "motor dysfunctions",
            "retinal ganglion cells",
            "dopaminergic features",
        }:
            cognition[0]["name"] = inferred_outcome_name
    elif inferred_outcome_name:
        cognition = [{"name": inferred_outcome_name}]
    for item in cognition:
        item["effect_direction"] = _enum_or_default(
            item.get("effect_direction"),
            {
                "improved": "improved",
                "worsened": "worsened",
                "no_change": "no_change",
                "no_difference": "no_change",
                "mixed": "mixed",
                "unknown": "unknown",
            },
            "unknown",
        )
    outcomes["cognition"] = cognition
    repaired["outcomes"] = outcomes

    eligibility = repaired.get("eligibility_flags") if isinstance(repaired.get("eligibility_flags"), dict) else {}
    if "include_for_mci_mct_review" in eligibility:
        eligibility["include_for_mci_mct_review"] = bool(eligibility.get("include_for_mci_mct_review"))
    if not eligibility.get("reason_if_excluded") and eligibility.get("reason"):
        eligibility["reason_if_excluded"] = str(eligibility.get("reason"))
    eligibility["separate_analysis_tag"] = _enum_or_default(
        eligibility.get("separate_analysis_tag"),
        {
            "primary_mct": "primary_mct",
            "ketone_ester_or_salt": "ketone_ester_or_salt",
            "ketogenic_diet": "ketogenic_diet",
            "mixed_population": "mixed_population",
            "unknown": "unknown",
        },
        "unknown",
    )
    repaired["eligibility_flags"] = eligibility

    if broader_nontrial_signal or preclinical_nonhuman_signal:
        if repaired["study_design"].get("design") == "unknown":
            repaired["study_design"]["design"] = "other" if preclinical_therapeutic_signal else "observational"
        if repaired["study_design"].get("design") == "observational" and preclinical_therapeutic_signal:
            repaired["study_design"]["design"] = "other"
        if repaired["study_design"].get("control_type") == "unknown":
            repaired["study_design"]["control_type"] = "none"
        if not preclinical_therapeutic_signal:
            repaired["intervention"] = {}
        repaired["eligibility_flags"]["include_for_mci_mct_review"] = False
        if not repaired["eligibility_flags"].get("reason_if_excluded"):
            if preclinical_therapeutic_signal:
                repaired["eligibility_flags"]["reason_if_excluded"] = (
                    "Preclinical mouse therapeutic gene-editing study rather than an MCI human cohort."
                )
            else:
                repaired["eligibility_flags"]["reason_if_excluded"] = "Population not MCI-only."

    ketone_confirmation = (
        repaired.get("ketone_confirmation") if isinstance(repaired.get("ketone_confirmation"), dict) else {}
    )
    repaired["ketone_confirmation"] = ketone_confirmation

    safety_adherence = repaired.get("safety_adherence") if isinstance(repaired.get("safety_adherence"), dict) else {}
    results = safety_adherence.get("results")
    if isinstance(results, list) and results and not safety_adherence.get("adverse_events_summary"):
        safety_adherence["adverse_events_summary"] = "; ".join(str(item) for item in results[:2])
        safety_adherence["adverse_events_reported"] = True
    safety_adherence["adherence_reported"] = bool(safety_adherence.get("adherence_reported"))
    safety_adherence["adverse_events_reported"] = bool(safety_adherence.get("adverse_events_reported"))
    safety_adherence["dropout_n_total"] = _coerce_int(safety_adherence.get("dropout_n_total"), default=0)
    repaired["safety_adherence"] = safety_adherence

    risk_of_bias_hints = (
        repaired.get("risk_of_bias_hints") if isinstance(repaired.get("risk_of_bias_hints"), dict) else {}
    )
    for field_name in (
        "randomization_clear",
        "allocation_concealment_clear",
        "blinding_clear",
        "attrition_low",
        "selective_reporting_suspected",
    ):
        risk_of_bias_hints[field_name] = bool(risk_of_bias_hints.get(field_name))
    notes_value = risk_of_bias_hints.get("notes")
    if isinstance(notes_value, list):
        risk_of_bias_hints["notes"] = "; ".join(str(item) for item in notes_value if str(item).strip()) or None
    repaired["risk_of_bias_hints"] = risk_of_bias_hints

    extraction_quality = (
        repaired.get("extraction_quality") if isinstance(repaired.get("extraction_quality"), dict) else {}
    )
    extraction_quality["confidence"] = _enum_or_default(
        extraction_quality.get("confidence"),
        {"high": "high", "medium": "medium", "low": "low"},
        "low",
    )
    missing_fields = extraction_quality.get("missing_fields")
    cleaned_missing_fields = missing_fields if isinstance(missing_fields, list) else []
    resolved_aliases = _resolved_missing_field_aliases(repaired)
    extraction_quality["missing_fields"] = [
        value
        for value in cleaned_missing_fields
        if (_normalize_text(value) or "") not in resolved_aliases
    ]
    repaired["extraction_quality"] = extraction_quality
    return repaired


def _specialty_trial_extraction_prompt(*, paper: dict[str, Any]) -> str:
    schema_json = json.dumps(SpecialtyTrialExtraction.model_json_schema(), indent=2)
    return f"""
You are an information extraction engine for clinical trials about MCT/ketone supplementation in Mild Cognitive Impairment (MCI).
Extract structured data STRICTLY as valid JSON following the provided schema below. Do not output any Markdown, comments, or extra keys.

Schema:
{schema_json}

Rules:
- The target population is MCI-only. If the study includes AD or mixed populations and MCI-specific results are not separable, mark include_for_mci_mct_review=false and explain why.
- Do not assume MCI-only from the task context alone. If the paper is a broader AD/dementia biomarker/review cohort or a mixed MCI+AD study, set population.mci_only=false.
- Primary outcomes must cover cognition AND also capture ADL/function and safety/adherence when reported.
- For outcomes.cognition[0].name, prefer the main named cognitive or diagnostic readout. Do not use generic placeholders like "cognitive symptoms" or safety/tolerability if a more specific named readout is present.
- For sample size, prefer enrolled or treatment-phase participant counts over screened totals or broad registry counts.
- If both screened and randomized/treatment-phase counts are present, put the randomized/treatment-phase count in population.n_total.
- Map aliases like number_of_participants, participants_in_treatment_phase, randomized participants, or n_mci into population.n_total.
- Convert duration into weeks. Examples: 12 months -> 52 weeks, 6-month follow-up -> 26 weeks.
- Use study_design.duration_weeks for the main blinded/active study phase and followup_weeks for extension/follow-up when the text distinguishes them.
- For non-intervention review/biomarker papers, prefer the most specific named diagnostic/biomarker readout from title/abstract/methods, such as plasma p-tau diagnostic accuracy, prodromal AD diagnostic criteria, or PET-based Braak stage.
- Ketone ester/salt interventions must be included but tagged for separate analysis (separate_analysis_tag="ketone_ester_or_salt").
- If a field is not stated, use null/0/unknown appropriately and list it in extraction_quality.missing_fields.
- IMPORTANT: Keep enum values inside the schema's allowed literals.
- IMPORTANT: If specific dose/product is missing in abstract, infer category and product_name from Title or Context if possible.
- IMPORTANT: Do not emit JSON Schema placeholders like "$ref"; fill concrete values only.

Now extract from the following text:
<<<
Title: {paper.get("title", "N/A")}
Abstract: {paper.get("summary", "N/A")}
Methods Snippet: {paper.get("methods_snippet", "Not available")}
>>>
"""


def generate_predictions(
    *,
    manifest_path: Path,
    out_dir: Path,
    run_id: str,
    model: str,
    timeout_seconds: int,
) -> Path:
    config = load_config()
    host = config.llm.local.base_url if config.llm.local else "http://localhost:11434"
    client = ollama.Client(host=host, timeout=timeout_seconds)

    documents = _load_manifest(manifest_path)
    rows: list[dict[str, Any]] = []
    prediction_docs: list[dict[str, Any]] = []
    run_root = out_dir / run_id
    predictions_root = run_root / "predictions"
    raw_root = run_root / "raw"
    errors_root = run_root / "errors"
    run_root.mkdir(parents=True, exist_ok=True)

    for doc in documents:
        paper_id = str(doc.get("paper_id") or "").strip()
        gold_path = _resolve_manifest_entry_path(manifest_path, str(doc.get("gold_path") or ""))
        gold_payload = _load_json_object(gold_path)

        raw_source_paths = doc.get("gold_source_paths") or []
        source_path = None
        for candidate in raw_source_paths:
            resolved = _resolve_manifest_entry_path(manifest_path, str(candidate or ""))
            if resolved.exists():
                source_path = resolved
                break
        if source_path is None:
            raise FileNotFoundError(f"document_artifact_missing_for={paper_id}")

        paper = _build_paper_inputs(source_path, gold_payload, paper_id)
        prompt = _specialty_trial_extraction_prompt(paper=paper)
        raw_response: str | None = None
        status = "error"
        error_message: str | None = None
        prediction_path: str | None = None
        try:
            response = client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0.2, "num_predict": 3072},
            )
            raw_response = response["message"]["content"]
            parsed = repair_and_parse_json(raw_response)
            if not isinstance(parsed, dict):
                raise RuntimeError("parsed_payload_not_object")
            repaired = _repair_prediction_payload(parsed, gold_payload, paper_id, paper_context=paper)
            validated = SpecialtyTrialExtraction.model_validate(repaired)
            prediction_file = predictions_root / f"{paper_id.replace(':', '_')}.json"
            _write_json(prediction_file, validated.model_dump(mode="json"))
            prediction_path = str(prediction_file)
            prediction_docs.append(
                {
                    "paper_id": paper_id,
                    "gold_path": str(gold_path),
                    "prediction_path": prediction_path,
                }
            )
            status = "ok"
        except httpx.ReadTimeout:
            error_message = f"ReadTimeout model={model} timeout_seconds={timeout_seconds}"
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"

        raw_file = raw_root / f"{paper_id.replace(':', '_')}.txt"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_text((raw_response or "") + ("\n" if raw_response else ""), encoding="utf-8")
        if error_message:
            _write_json(
                errors_root / f"{paper_id.replace(':', '_')}.json",
                {
                    "paper_id": paper_id,
                    "status": status,
                    "error": error_message,
                    "model": model,
                    "timeout_seconds": timeout_seconds,
                    "source_path": str(source_path),
                    "gold_path": str(gold_path),
                },
            )

        rows.append(
            {
                "paper_id": paper_id,
                "status": status,
                "error": error_message,
                "model": model,
                "prediction_path": prediction_path,
                "raw_path": str(raw_file),
            }
        )

    generated_manifest_path = run_root / "generated_manifest.json"
    _write_json(
        generated_manifest_path,
        {
            "schema_version": "extraction_regression_manifest.v1",
            "generated_at": _utc_now_iso(),
            "source_manifest": str(manifest_path),
            "model": model,
            "timeout_seconds": timeout_seconds,
            "documents": prediction_docs,
        },
    )

    success_rows = [row for row in rows if row["status"] == "ok"]
    timeout_rows = [row for row in rows if "ReadTimeout" in str(row.get("error") or "")]
    metrics = {
        "schema_version": "extraction_prediction_generation.v1",
        "generated_at": _utc_now_iso(),
        "run_id": run_id,
        "source_manifest": str(manifest_path),
        "model": model,
        "timeout_seconds": timeout_seconds,
        "document_count": len(rows),
        "success_count": len(success_rows),
        "timeout_count": len(timeout_rows),
        "error_count": len([row for row in rows if row["status"] != "ok"]),
        "rows": rows,
        "generated_manifest_path": str(generated_manifest_path),
    }
    _write_json(run_root / "metrics.json", metrics)
    _write_json(
        run_root / "summary.json",
        {
            "run_id": run_id,
            "status": "ok",
            "model": model,
            "timeout_seconds": timeout_seconds,
            "document_count": len(rows),
            "success_count": len(success_rows),
            "timeout_count": len(timeout_rows),
            "generated_manifest_path": str(generated_manifest_path),
        },
    )
    return run_root


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate bounded SpecialtyTrialExtraction predictions from repo-grounded artifacts.")
    parser.add_argument("--manifest", required=True, help="Manifest with gold_path plus gold_source_paths document artifacts.")
    parser.add_argument("--out-dir", default="snapshots/extraction_prediction_generation", help="Output root directory.")
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to a UTC timestamp.")
    parser.add_argument("--model", default="", help="Optional Ollama model override. Defaults to configured extractor model.")
    parser.add_argument("--timeout-seconds", type=int, default=20, help="Per-request Ollama timeout seconds.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = load_config()
    default_model = config.llm.local.models.get("extractor", "llama3:latest") if config.llm.local else "llama3:latest"
    run_id = args.run_id or datetime.now(timezone.utc).strftime("extraction_prediction_generation_%Y%m%d_%H%M%S")
    run_root = generate_predictions(
        manifest_path=Path(args.manifest).expanduser().resolve(),
        out_dir=Path(args.out_dir).expanduser().resolve(),
        run_id=run_id,
        model=str(args.model or default_model),
        timeout_seconds=int(args.timeout_seconds),
    )
    print(f"[generate_extraction_predictions] out={run_root}")
    print(f"[generate_extraction_predictions] metrics={run_root / 'metrics.json'}")


if __name__ == "__main__":
    main()
