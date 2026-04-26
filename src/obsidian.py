import csv
from io import StringIO
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import logging

from src.schemas import BiomedicalClinicalExtraction, SpecialtyTrialExtraction, PaperStatus
from src.skills.storage import atomic_write_text

logger = logging.getLogger(__name__)


def _atomic_write_csv_rows(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_text(path, buffer.getvalue())

def _get_escalation_metadata_lines(paper: Dict[str, Any]) -> str:
    lines = []
    final_route = str(paper.get("escalation_final_route") or "").strip()
    if final_route:
        lines.append(f"> **Final Route**: {final_route}")

    in_scope = paper.get("escalation_in_biomedical_scope")
    if isinstance(in_scope, bool):
        scope_label = "In biomedical scope" if in_scope else "Out of biomedical scope"
        lines.append(f"> **Biomedical Scope**: {scope_label}")

    raw_codes = paper.get("escalation_reason_codes")
    if isinstance(raw_codes, list):
        codes = [str(code).strip() for code in raw_codes if str(code).strip()]
        if codes:
            lines.append(f"> **Reason Codes**: {', '.join(codes)}")

    return "\n".join(lines)

def _get_status_callout(paper: Dict[str, Any]) -> str:
    """Action Gates 상태에 따른 Callout 생성"""
    # [NEW] Retraction Checks First
    if paper.get('is_retracted'):
        return f"\n> [!danger] ☠️ RETRACTED PAPER\n> **Details**: {paper.get('retraction_details', 'No details provided.')}\n"
    
    status_str = paper.get('processing_status')
    escalation_meta = _get_escalation_metadata_lines(paper)
    
    if status_str == PaperStatus.QUARANTINED:
        return "\n> [!danger] Low Confidence - Quarantined\n> This paper has been flagged for low confidence and isolated.\n"
    elif status_str == PaperStatus.PENDING_REVIEW:
        body = "\n> [!warning] Requires Human Review\n> Confidence score is in the intermediate range."
        if escalation_meta:
            body += "\n" + escalation_meta
        return body + "\n"
    elif status_str == PaperStatus.APPROVED:
        # [NEW] Escalation indicator
        if paper.get('is_escalated'):
            reason = paper.get('escalation_reason', 'Escalation Judge Approved')
            body = f"\n> [!success] Fast-Lane Approved (Escalation Judge)\n> **Judge Decision**: {reason}"
            if escalation_meta:
                body += "\n" + escalation_meta
            return body + "\n"
        return ""
    return ""

def get_template_study(paper: Dict[str, Any]) -> str:
    """기전/방법론 연구용 노트 템플릿"""
    status_callout = _get_status_callout(paper)
    one_liner_section = ""
    if paper.get('ai_one_liner'):
        one_liner_section = f"## 🧠 One-Liner\n> {paper['ai_one_liner']}\n"

    # [Fix] ai_mode가 'one-liner'이면 ai_summary가 one_liner와 동일하므로 중복 출력 방지
    ai_summary_section = ""
    if paper.get('ai_mode') != 'one-liner':
        ai_summary_section = f"## 🧠 AI Summary ({paper.get('ai_mode', 'simple')})\n{paper.get('ai_summary', 'Not available.')}\n"

    # [NEW] Evidence & Confidence Section
    hybrid_tags = paper.get('hybrid_tags', {})
    evidence_block = ""
    # hybrid_tags가 dict일 때만 접근
    if isinstance(hybrid_tags, dict) and (hybrid_tags.get('evidence_span') or hybrid_tags.get('confidence')):
        conf_score = hybrid_tags.get('confidence', 0.0)
        callout_type = "info" 
        
        evidence_block = f'''
> [!{callout_type}] Evidence & Confidence
> **Confidence**: {conf_score:.2f}
> **Evidence**: "{hybrid_tags.get('evidence_span', "N/A")}"
'''

    # [NEW] Context-Aware Analysis
    relevance_block = ""
    relevance = paper.get('relevance_analysis')
    if relevance:
        relevance_block = f'''
## 🧠 Context-Aware Analysis
> **Gap**: {relevance.get('gap', 'N/A')}
> **Insight**: {relevance.get('insight', 'N/A')}
> **Limitation**: {relevance.get('limitation', 'N/A')}
'''
    # Tags as YAML list
    tags_list = str(paper.get('tags', [])).replace("'", '"') # Simple list conversion
    
    return f"""---
type: paper
aliases: ["{paper['title']}"]
tags: {tags_list}
cssclasses: ["paper-note"]
status: {paper.get('reading_status', 'Inbox')}
created: {datetime.now().strftime('%Y-%m-%d')}
source: {paper['source']}
url: {paper['link']}
slot: {paper['slot']}
---

# {paper['title']}

{status_callout}
{one_liner_section}
{evidence_block}
{relevance_block}
{ai_summary_section}

## 📝 Notes
- 
"""

def _biomedical_clinical_summary_block(extraction: BiomedicalClinicalExtraction) -> str:
    population_parts = []
    if extraction.population.condition:
        population_parts.append(extraction.population.condition)
    if extraction.population.cohort_description:
        population_parts.append(extraction.population.cohort_description)
    if extraction.population.n_total > 0:
        population_parts.append(f"n={extraction.population.n_total}")
    population_str = ", ".join(population_parts) or "Not detailed"

    intervention_parts = []
    if extraction.intervention.name:
        intervention_parts.append(extraction.intervention.name)
    if extraction.intervention.category != "unknown":
        intervention_parts.append(extraction.intervention.category.replace("_", " ").title())
    if extraction.intervention.dose:
        intervention_parts.append(extraction.intervention.dose)
    intervention_str = ", ".join(intervention_parts) or "Not detailed"

    primary_outcomes = ", ".join(endpoint.name for endpoint in extraction.outcomes.primary[:3]) or "Not detailed"
    safety_str = "Reported" if extraction.safety_adherence.adverse_events_reported or extraction.outcomes.safety else "Not detailed"
    followup_tag = extraction.eligibility_flags.followup_tag.replace("_", " ").title()

    return f"""
> [!summary] Clinical Snapshot
> **Condition / Population**: {population_str}
> **Intervention**: {intervention_str}
> **Primary Outcomes**: {primary_outcomes}
> **Safety**: {safety_str}
> **Follow-Up Tag**: {followup_tag}
"""


def get_template_trial(
    paper: Dict[str, Any],
    extraction: Optional[SpecialtyTrialExtraction | BiomedicalClinicalExtraction] = None,
) -> str:
    """Clinical note template with default biomedical wording and optional specialty extraction overlays."""
    status_callout = _get_status_callout(paper)
    # Tags as YAML list
    tags_list = str(paper.get('tags', [])).replace("'", '"')
    
    # status = "Extracted" if extraction else "Extraction Needed" 
    # [UPDATED] Use ReadingStatus (Ticket 8)
    status = paper.get('reading_status', 'Inbox')
    
    # One-Liner 섹션 생성
    one_liner_section = ""
    if paper.get('ai_one_liner'):
        one_liner_section = f"## 🧠 One-Liner\n> {paper['ai_one_liner']}\n"

    # [NEW] Evidence & Confidence Section
    hybrid_tags = paper.get('hybrid_tags', {})
    evidence_block = ""
    # hybrid_tags가 dict일 때만 접근
    if isinstance(hybrid_tags, dict) and (hybrid_tags.get('evidence_span') or hybrid_tags.get('confidence')):
        conf_score = hybrid_tags.get('confidence', 0.0)
        # 0.8 이상이면 높은 신뢰도, 아니면 경고
        callout_type = "success" if conf_score >= 0.8 else "warning"
        
        evidence_block = f'''
> [!{callout_type}] Evidence & Confidence
> **Confidence**: {conf_score:.2f}
> **Evidence**: "{hybrid_tags.get('evidence_span', "N/A")}"
'''

    # 추출 데이터가 있으면 요약 블록을, 없으면 기본 메시지를 사용
    if isinstance(extraction, SpecialtyTrialExtraction):
        scope_block = f"""
> [!info] Specialty Extraction Lane
> {SpecialtyTrialExtraction.specialty_scope_note()}
"""
        summary_block = extraction.to_summary_block()
        data_block = "## 📊 Extracted Data (JSON)\n```json\n" + extraction.model_dump_json(indent=2) + "\n```\n"
    elif isinstance(extraction, BiomedicalClinicalExtraction):
        scope_block = f"""
> [!info] Clinical Workspace Lane
> {BiomedicalClinicalExtraction.default_scope_note()}
"""
        summary_block = _biomedical_clinical_summary_block(extraction)
        data_block = "## 📊 Extracted Data (JSON)\n```json\n" + extraction.model_dump_json(indent=2) + "\n```\n"
    else:
        scope_block = f"""
> [!info] Clinical Workspace Lane
> {BiomedicalClinicalExtraction.default_scope_note()}
"""
        # [Fix] ai_mode가 one-liner인 경우 중복 방지
        fail_content = paper.get('ai_summary', 'No data available.')
        if paper.get('ai_mode') == 'one-liner':
            fail_content = "See One-Liner above."
        summary_block = f"> [!info] Clinical Extraction Pending\n> {fail_content}"
        data_block = """## 📊 Data Extraction
| Field | Result |
|-------|--------|
| Condition / Population |  |
| Intervention |  |
| Primary Outcome |  |
"""

    # [NEW] Context-Aware Analysis
    relevance_block = ""
    relevance = paper.get('relevance_analysis')
    if relevance:
        relevance_block = f'''
## 🧠 Context-Aware Analysis
> **Gap**: {relevance.get('gap', 'N/A')}
> **Insight**: {relevance.get('insight', 'N/A')}
> **Limitation**: {relevance.get('limitation', 'N/A')}
'''

    # [NEW] Optional Institutional Proxy Link
    pdf_access_block = ""
    if not paper.get('local_pdf_path'):
        from src.institutional_access import extract_institutional_proxy_link
        proxy_url = extract_institutional_proxy_link(paper.get('feedback_json'))
        if proxy_url:
            pdf_access_block = f"""
> [!info] 🪪 Institutional Access Available
> PDF was not auto-downloaded. [Download via KNU Libproxy]({proxy_url})
"""
        elif str(paper.get("pdf_status") or "").strip().lower() == "missing":
            pdf_access_block = """
> [!warning] PDF Unavailable
> PDF is currently unavailable and no institutional access link is stored for this paper yet.
"""

    return f"""---
type: clinical_paper
aliases: ["{paper['title']}"]
tags: {tags_list}
cssclasses: ["clinical-note"]
status: {status}
created: {datetime.now().strftime('%Y-%m-%d')}
url: {paper['link']}
slot: {paper['slot']}
doi: {paper['doi']}
---

# {paper['title']}
{pdf_access_block}
{status_callout}
{one_liner_section}
## 🏥 Clinical Quick Look
{scope_block}
{summary_block}

{evidence_block}
{relevance_block}

{data_block}

## Abstract
{paper.get('summary', 'No abstract available.')}
"""

def _extract_intervention_string(td: Dict[str, Any]) -> str:
    """Trial data 딕셔너리에서 상세 Intervention 문자열 생성"""
    inter = td.get('intervention', {})
    flags = td.get('eligibility_flags', {})
    
    int_parts = []
    category = inter.get('category', 'unknown')
    product_name = inter.get('product_name')
    
    if category != "unknown":
        cat_display = category.replace("_", " ").title()
        if product_name:
            cat_display += f" ({product_name})"
        int_parts.append(cat_display)
    elif product_name:
        int_parts.append(product_name)

    dose_value = inter.get('dose_value', 0.0)
    dose_unit = inter.get('dose_unit', 'unknown')
    dose_schedule = inter.get('dose_schedule')

    if dose_value > 0:
        unit = dose_unit.replace("_per_day", "/d") if dose_unit != "unknown" else ""
        int_parts.append(f"{dose_value:.1f}{unit}")
    elif dose_schedule:
        int_parts.append(dose_schedule)

    duration_weeks = inter.get('duration_weeks', 0)
    if duration_weeks > 0:
        int_parts.append(f"{duration_weeks} weeks")
    
    intervention_str = ", ".join(int_parts)
    
    if not intervention_str:
        tag = flags.get('separate_analysis_tag', 'unknown')
        if tag != "unknown":
            tag_clean = tag.replace("_", " ").title()
            intervention_str = f"{tag_clean} (Unspecified details)"
        else:
            intervention_str = "Not detailed"
    return intervention_str


def _extract_biomedical_population_string(extraction: BiomedicalClinicalExtraction) -> str:
    population = extraction.population
    parts = []
    if population.condition:
        parts.append(population.condition)
    if population.cohort_description:
        parts.append(population.cohort_description)
    if population.n_total > 0:
        parts.append(f"n={population.n_total}")
    return ", ".join(parts) or "Not detailed"


def _extract_biomedical_intervention_string(extraction: BiomedicalClinicalExtraction) -> str:
    intervention = extraction.intervention
    parts = []
    if intervention.name:
        parts.append(intervention.name)
    if intervention.category != "unknown":
        parts.append(intervention.category.replace("_", " ").title())
    if intervention.dose:
        parts.append(intervention.dose)
    elif intervention.schedule:
        parts.append(intervention.schedule)
    if intervention.duration_weeks > 0:
        parts.append(f"{intervention.duration_weeks} weeks")
    return ", ".join(parts) or "Not detailed"


def _coerce_biomedical_clinical_extraction(
    paper: Dict[str, Any],
    extraction: Optional[SpecialtyTrialExtraction | BiomedicalClinicalExtraction] = None,
) -> Optional[BiomedicalClinicalExtraction]:
    if isinstance(extraction, BiomedicalClinicalExtraction):
        return extraction

    payload = paper.get("clinical_data")
    if isinstance(payload, BiomedicalClinicalExtraction):
        return payload
    if isinstance(payload, dict):
        try:
            return BiomedicalClinicalExtraction.model_validate(payload)
        except Exception as exc:
            logger.warning("Failed to parse clinical_data for CSV export: %s", exc)
    return None


def _build_clinical_index_fields(
    paper: Dict[str, Any],
    extraction: Optional[SpecialtyTrialExtraction | BiomedicalClinicalExtraction] = None,
) -> Dict[str, str]:
    fields = {
        "Population": "",
        "Intervention": "",
        "Outcome_Cognition": "",
        "Outcome_ADL": "",
        "Condition": "",
        "Primary_Outcome": "",
        "Safety": "",
        "Followup_Tag": "",
    }

    specialty_payload = None
    if isinstance(extraction, SpecialtyTrialExtraction):
        specialty_payload = extraction.model_dump(mode="json")
    elif paper.get("trial_data"):
        specialty_payload = paper["trial_data"]

    if isinstance(specialty_payload, dict):
        population = specialty_payload.get("population", {})
        population_label = "MCI-only" if population.get("mci_only") else "Mixed"
        if not population.get("mci_only"):
            notes = population.get("comorbidity_notes")
            if notes:
                population_label += f" ({notes})"

        fields["Population"] = population_label
        fields["Intervention"] = _extract_intervention_string(specialty_payload)
        fields["Outcome_Cognition"] = "Reported" if specialty_payload.get("outcomes", {}).get("cognition") else ""
        fields["Outcome_ADL"] = "Yes" if specialty_payload.get("outcomes", {}).get("adl_function") else "No"
        return fields

    generic_payload = _coerce_biomedical_clinical_extraction(paper, extraction)
    if generic_payload is None:
        return fields

    primary_outcomes = [endpoint.name for endpoint in generic_payload.outcomes.primary if endpoint.name]
    safety_outcomes = [endpoint.name for endpoint in generic_payload.outcomes.safety if endpoint.name]
    safety_summary = ""
    if generic_payload.safety_adherence.adverse_events_reported:
        safety_summary = generic_payload.safety_adherence.adverse_events_summary or "Adverse events reported"
    elif safety_outcomes:
        safety_summary = "; ".join(safety_outcomes[:3])

    fields["Population"] = _extract_biomedical_population_string(generic_payload)
    fields["Intervention"] = _extract_biomedical_intervention_string(generic_payload)
    fields["Condition"] = generic_payload.population.condition or ""
    fields["Primary_Outcome"] = "; ".join(primary_outcomes[:3])
    fields["Safety"] = safety_summary
    followup_tag = generic_payload.eligibility_flags.followup_tag
    if followup_tag != "unknown":
        fields["Followup_Tag"] = followup_tag.replace("_", " ").title()
    return fields

def find_related_papers(current_paper: Dict[str, Any], config) -> str:
    """
    [NEW] Smart Linking: Find related papers from the CSV index based on shared tags.
    Returns a markdown list of links.
    """
    index_path = config.paths.obsidian_vault / config.paths.index_all
    if not index_path.exists():
        return ""
        
    related_links = []
    current_tags = set(current_paper.get('tags', []))
    current_id = current_paper.get('doi') or current_paper.get('link')
    
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip self
                if row.get('Paper_ID') == current_id:
                    continue
                
                # Check Overlap
                row_tags = set(row.get('Tags', '').split(';'))
                overlap = current_tags.intersection(row_tags)
                
                # Similarity Logic: At least 2 shared tags or Same Slot + 1 Tag
                if len(overlap) >= 2 or (row.get('Slot') == current_paper.get('slot') and len(overlap) >= 1):
                    # Link Format: [[Filename]]
                    # We need the filename. CSV has Note_Path (Inbox/Date/Filename)
                    note_path = row.get('Note_Path', '')
                    if note_path:
                        filename = Path(note_path).name.replace('.md', '')
                        link = f"- [[{filename}]] (Shared: {', '.join(list(overlap)[:3])})"
                        related_links.append(link)
                        
        if related_links:
            # Limit to top 5
            return "\n## 🔗 Related Papers\n" + "\n".join(related_links[:5]) + "\n"
            
    except Exception as e:
        logger.warning(f"Failed to find related papers: {e}")
        
    return ""

def update_csv_index(
    paper: Dict[str, Any],
    file_path: Path,
    is_clinical: bool = False,
    relative_note_path: str = None,
    extraction: Optional[SpecialtyTrialExtraction | BiomedicalClinicalExtraction] = None,
):
    """
    [Fix] DOI 기준이 아니라 'Date + Slot' 기준으로 중복 방지 (Upsert)
    -> 같은 날짜, 같은 슬롯에는 무조건 1개의 행만 유지됩니다.
    """
    # 1. 원하는 컬럼 정의 (사용자 요청 반영)
    headers = [
        'Date', 'Slot', 'Paper_ID', 'Title', 'DOI', 
        'Source', 'URL', 'Score', 'Status', 'Note_Path',
        'Tags', 'Authors' # [NEW] Added for Smart Linking
    ]
    
    # [추가] 임상시험 전용 컬럼
    if is_clinical:
        headers.extend(
            [
                'Population',
                'Intervention',
                'Outcome_Cognition',
                'Outcome_ADL',
                'Condition',
                'Primary_Outcome',
                'Safety',
                'Followup_Tag',
            ]
        )
    
    rows = []
    updated = False
    today = datetime.now().strftime('%Y-%m-%d')
    paper_id = paper.get('doi') or paper.get('link') or "unknown_id"
    
    # [NEW] Note Path Logic
    if relative_note_path:
        note_path = relative_note_path
    else:
        # Fallback (Legacy)
        safe_title = "".join(c for c in paper.get('title', '')[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
        note_path = f"Inbox/{today}/{paper.get('slot', 'Paper')}_{safe_title}.md"
    
    # Prepare common fields
    tags_val = ";".join(paper.get('tags', []))
    authors_val = ";".join(paper.get('authors', []))
    
    # 2. 기존 파일 읽기 (있다면)
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # [Modified] 헤더가 달라도 읽어들여서 데이터 보존 (Schema Migration 지원)
            for row in reader:
                # [핵심 변경] 오늘 날짜이고 + 슬롯이 같으면 -> 덮어쓴다!
                is_same_slot = (row.get('Date') == today) and (row.get('Slot', '').lower() == paper.get('slot', '').lower())
                
                # 임상 전용 파일인 경우 슬롯 체크 없이 날짜만 보면 됨 (하루 1개 제한 시)
                if is_clinical and row.get('Date') == today:
                        is_same_slot = True

                if is_same_slot:
                    row['Paper_ID'] = paper_id
                    row['Date'] = today
                    row['Title'] = paper.get('title', '')
                    row['DOI'] = paper.get('doi', '')
                    row['Source'] = paper.get('source', '')
                    row['URL'] = paper.get('link', '')
                    row['Note_Path'] = note_path
                    row['Score'] = "Top1" # 현재 로직상 Top1임
                    row['Tags'] = tags_val     # [NEW]
                    row['Authors'] = authors_val # [NEW]
                    
                    # 임상 데이터 업데이트
                    if is_clinical:
                        row.update(_build_clinical_index_fields(paper, extraction))
                    
                    # [UPDATED] Use ReadingStatus (Ticket 8)
                    row['Status'] = paper.get('reading_status', 'Inbox')

                    updated = True
                
                # [Safety] DictWriter는 헤더에 있는 키가 딕셔너리에 없으면 에러를 냄.
                # 따라서 모든 헤더 키에 대해 기본값을 채워줌.
                for h in headers:
                    row.setdefault(h, "")
                rows.append(row)
    
    # 3. 새 데이터 추가 (Update 안 된 경우)
    if not updated:
        # 임상 데이터 추출 (있을 경우)
        clinical_fields = _build_clinical_index_fields(paper, extraction) if is_clinical else {}

        new_row = {
            'Date': today,
            'Slot': paper.get('slot', 'N/A'),
            'Paper_ID': paper_id,
            'Title': paper.get('title', ''),
            'DOI': paper.get('doi', ''),
            'Source': paper.get('source', ''),
            'URL': paper.get('link', ''),
            'Score': "Top1",
            'Status': paper.get('reading_status', 'Inbox'),
            'Note_Path': note_path,
            'Tags': tags_val,      # [NEW]
            'Authors': authors_val # [NEW]
        }
        
        if is_clinical:
            new_row.update(clinical_fields)
            
        # [Safety] 새 행도 마찬가지로 누락된 키 보정
        for h in headers:
            new_row.setdefault(h, "")
            
        rows.append(new_row)
    
    # 4. 파일 덮어쓰기
    # extrasaction='ignore': 기존 데이터에만 있고 새 헤더에는 없는 컬럼이 있어도 에러 없이 저장(해당 컬럼은 삭제됨)
    _atomic_write_csv_rows(file_path, headers, rows)

def save_paper_to_obsidian(
    paper: Dict[str, Any], 
    config, 
    extraction: Optional[SpecialtyTrialExtraction | BiomedicalClinicalExtraction] = None,
    subfolder_override: str = None,
    index_file_override: str = None
):
    """Main note writer with a domain-neutral clinical default and optional specialty extraction overlays."""
    vault_path = config.paths.obsidian_vault
    
    # [NEW] Determine Folder
    if subfolder_override:
         today_folder = vault_path / subfolder_override
    elif paper.get('processing_status') == PaperStatus.QUARANTINED:
        # 격리 폴더: Inbox/Quarantine (날짜별 구분 없이 큐로 관리하거나, 필요시 날짜 추가)
        today_folder = vault_path / "Inbox" / "Quarantine"
    else:
        # 일반 폴더: Inbox/YYYY-MM-DD
        today_folder = vault_path / "Inbox" / datetime.now().strftime('%Y-%m-%d')
        
    today_folder.mkdir(parents=True, exist_ok=True)
    
    safe_title = "".join(c for c in paper.get('title', '')[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
    filename = f"{paper.get('slot', 'Paper')}_{safe_title}.md"
    file_path = today_folder / filename
    
    # Find Related Papers
    related_block = find_related_papers(paper, config)
    
    # [템플릿 분기] Clinical 슬롯 -> Clinical note, 그 외 -> Study Note
    if paper.get('slot', '').lower() == 'clinical':
        content = get_template_trial(paper, extraction)
    else:
        content = get_template_study(paper)
        
    # Append Related Papers
    if related_block:
        content += related_block
        
    atomic_write_text(file_path, content)
    
    # [NEW] Calculate Relative Note Path for CSV
    try:
        relative_path = file_path.relative_to(vault_path)
    except ValueError:
        relative_path = file_path.name

    # [인덱스 1] 전체 논문 누적 (paper_collection.csv OR Override)
    if index_file_override:
         path_all = config.paths.obsidian_vault / index_file_override
    else:
         path_all = config.paths.obsidian_vault / config.paths.index_all
         
    path_all.parent.mkdir(parents=True, exist_ok=True)
    update_csv_index(
        paper,
        path_all,
        is_clinical=False,
        relative_note_path=str(relative_path),
        extraction=extraction,
    )
    
    # [인덱스 2] 임상 추출 논문만 누적 (clinical_trials.csv) -> OnDemand는 임상 인덱스 안 건드림 (규칙상)
    # 하지만 일단 유지하되, override가 없을 때만
    if not index_file_override and paper.get('slot', '').lower() == 'clinical':
        path_clinical = config.paths.obsidian_vault / config.paths.index_clinical
        path_clinical.parent.mkdir(parents=True, exist_ok=True)
        update_csv_index(
            paper,
            path_clinical,
            is_clinical=True,
            relative_note_path=str(relative_path),
            extraction=extraction,
        )
    
    return file_path

def set_reading_status(paper_id_or_doi: str, new_status: str, config) -> str:
    """
    Updates the reading status in CSV Index and Obsidian Note.
    Checks multiple index files (Main, OnDemand, Manual).
    Returns the DOI if found, else None.
    """
    import re
    
    vault_path = config.paths.obsidian_vault
    
    # Define potential indexes
    potential_indexes = [
        config.paths.index_all, # 00_Index/paper_collection.csv
        "00_Index/on_demand.csv",
        "00_Index/manual_collection.csv"
    ]
    
    target_doi = None
    target_note_path = None
    
    for relative_idx_path in potential_indexes:
        index_path = vault_path / relative_idx_path
        if not index_path.exists():
            continue
            
        updated_rows = []
        found_in_this_file = False
        headers = []
        
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                for row in reader:
                    pid = row.get('Paper_ID', '')
                    doi = row.get('DOI', '')
                    title = row.get('Title', '')
                    
                    # Match Logic
                    if paper_id_or_doi == pid or paper_id_or_doi == doi or paper_id_or_doi == title:
                        row['Status'] = new_status
                        target_doi = doi
                        note_rel = row.get('Note_Path')
                        if note_rel:
                            target_note_path = vault_path / note_rel
                        found_in_this_file = True
                        
                    updated_rows.append(row)
            
            if found_in_this_file:
                _atomic_write_csv_rows(index_path, headers, updated_rows)
                logger.info(f"Updated status in index: {relative_idx_path}")
                break # Stop searching other indexes if found
                
        except Exception as e:
            logger.error(f"Failed to read/update index {relative_idx_path}: {e}")
            
    # 2. Update Obsidian Note Frontmatter (Only if note found)
    if target_note_path and target_note_path.exists():
        try:
            content = target_note_path.read_text(encoding='utf-8')
            new_content = re.sub(r'^status:.*$', f'status: {new_status}', content, count=1, flags=re.MULTILINE)
            atomic_write_text(target_note_path, new_content)
            logger.info(f"Updated status in note: {target_note_path}")
        except Exception as e:
            logger.error(f"Failed to update markdown note: {e}")
            
    return target_doi
