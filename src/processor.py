import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path # [Fix]


from src.db import is_paper_processed, save_paper_state, log_run_stat
from src.config import load_config, AppConfig
# [Refactor] Use Fetch Provider
from src.fetch import get_fetchers 
from src.llm_provider import get_llm_provider, LLMProvider
from src.obsidian import save_paper_to_obsidian
from src.schemas import Paper, TrialExtraction, PaperStatus
from src.downloader import download_paper
from src.zotero import export_to_ris
from src.retraction import check_retraction # [NEW] Import

# 로거 설정
logger = logging.getLogger(__name__)

# ... (rest of imports/helpers)

def _get_fallback_summary(paper: Paper) -> str:
    """LLM 실패 시 사용할 Fallback 요약 (초록 원문)"""
    if not paper.summary:
        return "No abstract available."
    return (paper.summary[:300] + '...') if len(paper.summary) > 300 else paper.summary

def process_paper(
    paper_data: Dict[str, Any], 
    config: AppConfig, 
    llm_provider: LLMProvider,
    is_deep_target: bool,
    subfolder_override: str = None, # [NEW]
    index_file_override: str = None # [NEW]
) -> Dict[str, Any]:
    """선정된 논문 하나를 처리하는 로직 (LLM, 다운로드, Obsidian 저장)"""
    paper = paper_data['paper']
    slot = paper_data['slot']
    
    logger.info(f"Processing paper: {paper.title}")
    
    # 최종 결과로 사용할 딕셔너리 (paper 모델을 기반으로 생성)
    result_dict = paper.model_dump()
    result_dict['doi'] = paper.id # 하위 호환성을 위해 doi 키 추가
    result_dict['slot'] = slot
    result_dict.setdefault('ai_mode', 'fallback')
    result_dict['ai_summary'] = _get_fallback_summary(paper)
    result_dict['trial_data'] = None
    # [Fix] Initialize tags from paper_data (config/search logic)
    result_dict['tags'] = list(paper_data.get('tags', []))

    # [NEW] Integrity Check (Retraction Watch)
    if paper.id and "/" in paper.id: # Simple check if it might be a DOI
        logger.info("   🛡️  Checking integrity (Retraction Watch)...")
        # Use Unpaywall email as polite pool email if available
        integrity_data = check_retraction(paper.id, config.unpaywall.email)
        
        if integrity_data['is_retracted']:
            logger.warning(f"   ☠️  PAPER RETRACTED: {integrity_data['retraction_details']}")
            result_dict['is_retracted'] = True
            result_dict['retraction_details'] = integrity_data['retraction_details']
            result_dict['processing_status'] = PaperStatus.QUARANTINED
            # Add explicit tag
            result_dict['tags'].append("#RETRACTED")

    if llm_provider and llm_provider.is_available():
        # [Step 1] Slot Verification (Enabled)
        if config.llm.features.slot_classification.enabled:
            logger.info("   🔍 Verifying slot classification...")
            # Pydantic Paper object -> dict
            new_slot_name = llm_provider.classify_slot(paper.model_dump(), slot)
            if new_slot_name.lower() != slot.lower():
                 logger.info(f"   🔄 Slot Re-assigned: {slot} -> {new_slot_name}")
                 result_dict['slot'] = new_slot_name.lower()
                 slot = new_slot_name.lower() # Update local var for subsequent logic

        # [NEW] Hybrid Tagging
        try:
             logger.info("   🏷️  Running Hybrid Tagging...")
             tags_data = llm_provider.tag_paper(paper.model_dump())
             
             if tags_data:
                 result_dict['hybrid_tags'] = tags_data
                 # Merge soft tags
                 if tags_data.get('soft_tags'):
                     current_tags = set(result_dict.get('tags', []))
                     current_tags.update(tags_data['soft_tags'])
                     result_dict['tags'] = list(current_tags)

                 # [NEW] Action Gate Logic
                 if 'confidence' in tags_data:
                     conf = tags_data['confidence']
                     if conf >= config.confidence_thresholds.high:
                         result_dict['processing_status'] = PaperStatus.AUTO_APPROVED
                         logger.info(f"      - Gate: Auto-Approved (Conf: {conf:.2f})")
                     elif conf < config.confidence_thresholds.low:
                          result_dict['processing_status'] = PaperStatus.QUARANTINED
                          logger.info(f"      - Gate: Quarantined (Conf: {conf:.2f})")
                     else:
                          result_dict['processing_status'] = PaperStatus.PENDING_REVIEW
                          result_dict['tags'].append("#Review_Needed") # [NEW] Explicit tag
                          logger.info(f"      - Gate: Pending Review (Conf: {conf:.2f})")
                          
                          # [NEW] Escalation Gate (Conditional Re-ranking)
                          # Only escalate if NOT retracted and NOT already quarantined
                          if not result_dict.get('is_retracted'):
                              logger.info("      ⚖️  Triggering Escalation Gate (Judge)...")
                              escalation = llm_provider.evaluate_escalation(result_dict)
                              
                              if escalation.get('approved'):
                                  new_conf = escalation.get('new_confidence', 0.95)
                                  updated_reason = escalation.get('reason', 'Judge Approved')
                                  
                                  result_dict['processing_status'] = PaperStatus.AUTO_APPROVED
                                  result_dict['is_escalated'] = True
                                  result_dict['escalation_reason'] = updated_reason
                                  
                                  # Update confidence score in hybrid_tags for consistency
                                  if 'hybrid_tags' in result_dict:
                                      result_dict['hybrid_tags']['confidence'] = new_conf
                                      
                                  logger.info(f"      🚀 Escalation APPROVED: {updated_reason} (New Conf: {new_conf:.2f})")
                              else:
                                  logger.info(f"      ✋ Escalation Denied: {escalation.get('reason')}")
             else:
                 # Tagging returned None -> Use Fallback
                 logger.warning("   ⚠️ Tagging returned no data. Using fallback.")
                 result_dict['tags'].append("#check_tags")
                 result_dict['processing_status'] = PaperStatus.PENDING_REVIEW # Default fallback

        except Exception as e:
             logger.warning(f"   ⚠️ Tagging failed: {e}")
             result_dict['tags'].append("#check_tags")
             result_dict['processing_status'] = PaperStatus.PENDING_REVIEW # Default fallback

        # [Step 1.5] Context-Aware Analysis (Ticket 7)
        try:
            current_slot_config = config.search.slots.get(slot)
            if current_slot_config and current_slot_config.research_question:
                rq = current_slot_config.research_question
                logger.info(f"   🧠 Running Context Analysis for RQ: {rq[:50]}...")
                
                analysis = llm_provider.analyze_relevance(paper.model_dump(), rq)
                if analysis:
                    result_dict['relevance_analysis'] = analysis
                    logger.info("      - Analysis complete (Gap/Insight/Limitation)")
        except Exception as e:
            logger.warning(f"   ⚠️ Context Analysis failed: {e}")

        # [NEW] Smart Linking (Vectors)
        try:
            logger.info("   🔗 Running Smart Linking (Vector Embeddings)...")
            text_to_embed = f"{paper.title}\n{paper.summary}"
            embedding = llm_provider.get_embedding(text_to_embed)
            
            if embedding:
                # 1. Save to DB
                from src.db import save_embedding, get_all_embeddings
                save_embedding(paper.id, embedding)
                
                # 2. Find Related
                all_vectors = get_all_embeddings()
                related = llm_provider.find_related_papers(paper.id, all_vectors, top_k=3)
                
                if related:
                    result_dict['related_papers'] = []
                    for pid, score in related:
                        # Find title from DB or just store PID/Score
                        # For simple display, PID + Score is enough, or we iterate all papers to find title (expensive)
                        # Let's just store PID and score for now. Obsidian renderer can link to PID note.
                        result_dict['related_papers'].append({"id": pid, "score": float(score)})
                    logger.info(f"      - Found {len(related)} related papers.")
            else:
                logger.warning("      - Failed to generate embedding.")
        except Exception as e:
            logger.warning(f"   ⚠️ Smart Linking failed: {e}")

        # [Step 2] Generate One-Liner
        if config.llm.features.one_liner.enabled:
            logger.info("   -> Generating one-liner summary...")
            one_liner = llm_provider.generate_one_liner(paper.model_dump())
            if one_liner and "AI Error" not in one_liner:
                result_dict['ai_one_liner'] = one_liner

        # [Step 3] Main Content Generation
        if slot.lower() == 'clinical' and config.llm.features.trial_extraction.enabled:
            logger.info("   -> Running clinical trial extraction...")
            extraction_result = llm_provider.extract_trial_data(paper.model_dump())
            if extraction_result:
                result_dict['trial_data'] = extraction_result.model_dump()
                result_dict['ai_summary'] = extraction_result.to_summary_block()
                result_dict['ai_mode'] = 'extraction'
            elif result_dict.get('ai_one_liner'):
                result_dict['ai_summary'] = result_dict['ai_one_liner']
                result_dict['ai_mode'] = 'one-liner'

        elif is_deep_target:
            logger.info("   -> Running Deep Read analysis...")
            deep_summary = llm_provider.generate_deep_read(paper)
            if deep_summary:
                result_dict['ai_summary'] = deep_summary
                result_dict['ai_mode'] = 'deep'
        
        else: # Not a deep read target, use one-liner if available
            if result_dict.get('ai_one_liner'):
                result_dict['ai_summary'] = result_dict['ai_one_liner']
                result_dict['ai_mode'] = 'one-liner'
    else:
        logger.warning("LLM provider not available. Skipping all AI features.")

    # [NEW] PDF 다운로드 시도
    logger.info("   -> Attempting PDF download...")
    paper = download_paper(paper, config)
    # local_pdf_path는 문자열이어야 할 수 있으므로 변환
    result_dict['local_pdf_path'] = str(paper.local_pdf_path) if paper.local_pdf_path else None

    # [NEW] NotebookLM Copier Loop
    if paper.local_pdf_path and config.paths.upload_dir:
        try:
            import shutil
            from pathlib import Path
            upload_dir = Path(config.paths.upload_dir)
            
            # [NEW] Subfolder override logic (e.g. Upload/OnDemand)
            if subfolder_override:
                upload_dir = upload_dir / subfolder_override
                
            if not upload_dir.exists():
                upload_dir.mkdir(parents=True, exist_ok=True)
            
            dest_path = upload_dir / paper.local_pdf_path.name
            shutil.copy2(paper.local_pdf_path, dest_path)
            logger.info(f"      - Copied to NotebookLM Upload: {dest_path}")
        except Exception as e:
            logger.error(f"      - Failed to copy to NotebookLM Upload: {e}")


    # Obsidian 노트 생성
    logger.info("   -> Saving note to Obsidian...")
    obsidian_path = None
    try:
        extraction_obj = TrialExtraction(**result_dict['trial_data']) if result_dict.get('trial_data') else None
        obsidian_path = save_paper_to_obsidian(
            result_dict, 
            config, 
            extraction=extraction_obj,
            subfolder_override=subfolder_override, # [NEW]
            index_file_override=index_file_override # [NEW]
        )
        logger.info(f"      - Successfully saved to {obsidian_path}")
    except Exception as e:
        logger.error(f"      - Failed to save to Obsidian: {e}", exc_info=True)

    # [Ticket v3.0] Agentic Post-Processing
    if config.agents and config.agents.enabled and obsidian_path and obsidian_path.exists():
        try:
            # 1. Populate RAG Index (Copy Note)
            import shutil
            rag_path = Path(config.agents.rag_index_path)
            if not rag_path.exists():
                rag_path.mkdir(parents=True, exist_ok=True)
            
            rag_dest = rag_path / obsidian_path.name
            shutil.copy2(obsidian_path, rag_dest)
            logger.info(f"      - [Agent] Copied to RAG Index: {rag_dest}")
            
            # 2. Trigger Deep Read Agent (Auto-Gate > High Confidence)
            # Only if status is AUTO_APPROVED (High Confidence)
            if result_dict.get('processing_status') == PaperStatus.AUTO_APPROVED:
                logger.info("      🤖 Triggering Agentic Deep Read (Auto-Approved)...")
                from src.agents.deep_reader import DeepReadAgent
                agent = DeepReadAgent()
                
                content = obsidian_path.read_text(encoding='utf-8')
                report = agent.run(content, {
                    'title': paper.title, 
                    'authors': paper.authors, 
                    'published': paper.published
                })
                
                if report and "❌" not in report:
                    # Append to Obsidian Note
                    new_content = content + f"\n\n## 🤖 Agent Deep Read\n{report}\n"
                    obsidian_path.write_text(new_content, encoding='utf-8')
                    logger.info("      - [Agent] Deep Read appended to note.")
                    
                    # Update RAG copy too
                    rag_dest.write_text(new_content, encoding='utf-8')
                else:
                    logger.warning(f"      - [Agent] Deep Read failed: {report}")
                    
        except Exception as e:
             logger.error(f"      ❌ Agentic processing error: {e}")

    # [NEW] Zotero Export
    if config.paths.export_dir:
        export_to_ris(result_dict, config.paths.export_dir)

    # 처리된 논문 DB에 저장
    save_paper_state(paper.id, paper.title, paper.source, datetime.now().isoformat())
    
    return result_dict

def process_daily_slots(ignore_db: bool = False) -> List[Dict[str, Any]]:
    """매일 정해진 슬롯에 따라 논문을 수집, 처리, 요약, 다운로드하는 메인 파이프라인"""
    config = load_config()
    llm_provider = get_llm_provider(config.llm, config.entity_aliases) # [Updated] Pass aliases
    final_selection_data = []
    
    # [Refactor] Initialize Fetchers
    fetchers = get_fetchers(config)
    
    logger.info("🚀 Starting daily paper processing pipeline...")

    # 1. 각 슬롯별 후보 논문 수집 (Provider Pattern 적용)
    candidate_papers = {}
    for slot_name, slot_config in config.search.slots.items():
        query = slot_config.query
        source_filter = slot_config.source # e.g. "pubmed", "arxiv", "all"
        
        logger.info(f"🔍 Searching slot '{slot_name}' (Filter: {source_filter}) with query: \"{query}\"\n")
        
        candidates: List[Paper] = []
        
        for fetcher in fetchers:
            # Source Filtering Logic
            if source_filter.lower() == 'all' or fetcher.source_name.lower() == source_filter.lower():
                try:
                    # Default limits (Configurable per slot could be an upgrade)
                    limit = 30 if fetcher.source_name == 'PubMed' else 10 
                    
                    fetched = fetcher.fetch(query, max_results=limit)
                    candidates.extend(fetched)
                    
                    # [Milestone 4.5] Log Stats
                    limit_hit = len(fetched) >= limit
                    log_run_stat(slot_name, len(fetched), limit_hit)

                    logger.info(f"   - Fetched {len(fetched)} from {fetcher.source_name}")
                except Exception as e:
                    logger.error(f"   ❌ Error fetching from {fetcher.source_name}: {e}")

        candidate_papers[slot_name] = candidates

    # [NEW] 1.5 Bibliometric Ranking (Ticket 3)
    if config.ranking.bibliometrics.enabled:
        try:
            from src.ranking import BibliometricScorer
            scorer = BibliometricScorer(config)
            logger.info("📊 Applied Bibliometric Ranking to candidates...")
            
            for slot_name, candidates in candidate_papers.items():
                if not candidates: continue
                # Rank in-place (updates manual_rank_score)
                ranked = scorer.calculate_scores(candidates)
                candidate_papers[slot_name] = ranked
                if ranked:
                    top = ranked[0]
                    logger.info(f"   - Top ranked for {slot_name}: {top.title[:40]}... (Score: {top.manual_rank_score})")
        except Exception as e:
            logger.error(f"❌ Ranking failed: {e}")

    # 2. 슬롯별 최종 논문 선정
    processed_ids = set()
    for slot_name, candidates in candidate_papers.items():
        for paper in candidates:
            if not paper.id: continue
            if paper.id in processed_ids: continue
            if not ignore_db and is_paper_processed(paper.id):
                logger.debug(f"   ⏭️  Skipping duplicate (DB): {paper.title}")
                continue

            title_clean = paper.title.strip()
            word_count = len(title_clean.split())
            if (word_count <= 4 and title_clean.endswith('.')) or \
               (word_count <= 5 and any(k in title_clean for k in ["Chapter", "Section", "Part", "Index", "Preface"])):
                logger.info(f"   🗑️ Skipping Junk Title: {title_clean}")
                continue

            paper_data = {'paper': paper, 'slot': slot_name, 'tags': []}
            if slot_name == 'clinical':
                title_lower = paper.title.lower()
                if "ester" in title_lower or "salt" in title_lower:
                    paper_data['tags'].extend(["#MCT", "#KetoneEster"])
                else:
                    paper_data['tags'].append("#MCT")
            
            final_selection_data.append(paper_data)
            processed_ids.add(paper.id)
            logger.info(f"✅ Selected paper '{paper.title}' for slot '{slot_name}'.")
            break
        
        if not any(p['slot'] == slot_name for p in final_selection_data):
            logger.warning(f"⚠️ No valid paper selected for slot '{slot_name}'.")

    # 3. 선정된 논문들 정보 처리
    logger.info(f"⚙️ Processing {len(final_selection_data)} selected papers...")
    results = []

    # Deep Read 대상 선정 로직
    deep_read_id = None
    slot_priority = ['clinical', 'mechanism', 'methods']
    for slot in slot_priority:
        for p_data in final_selection_data:
            if p_data['slot'] == slot:
                deep_read_id = p_data['paper'].id
                break
        if deep_read_id: break
    
    if not deep_read_id and final_selection_data:
        deep_read_id = final_selection_data[0]['paper'].id

    for paper_data in final_selection_data:
        is_deep_target = paper_data['paper'].id == deep_read_id
        processed_result = process_paper(paper_data, config, llm_provider, is_deep_target)
        results.append(processed_result)

    logger.info("✅ Daily paper processing finished.")
    return results

def process_local_pdf(pdf_path: Path):
    """
    [NEW] Process a manually downloaded PDF file (Watch Folder).
    1. Extract Title/DOI from metadata or filename.
    2. Create Paper object.
    3. Run process_paper.
    """
    import shutil
    from pypdf import PdfReader
    
    config = load_config()
    llm_provider = get_llm_provider(config.llm, config.entity_aliases)
    
    logger.info(f"📂 Processing Local PDF: {pdf_path.name}")
    
    # 1. Metadata Extraction
    try:
        from src.utils import create_paper_from_pdf
        paper = create_paper_from_pdf(pdf_path)
    except Exception as e:
        logger.error(f"❌ Failed to create paper object: {e}")
        return
    
    # Check DB
    if is_paper_processed(paper.id):
        logger.info(f"   ⏭️  Skipping duplicate (DB): {paper.title}")
        return

    # 2. Rename & Move to Library
    from src.utils import generate_filename
    
    new_filename = generate_filename(paper)
    year = paper.published[:4] if paper.published and len(paper.published) >= 4 else "Unknown"
    
    library_dir = config.paths.library_dir / year
    library_dir.mkdir(parents=True, exist_ok=True)
    
    final_path = library_dir / new_filename
    
    # Handle duplicates in library (e.g. versioning)
    if final_path.exists():
        timestamp = datetime.now().strftime("%H%M%S")
        final_path = library_dir / f"{final_path.stem}_{timestamp}{final_path.suffix}"

    try:
        shutil.move(pdf_path, final_path)
        logger.info(f"   📂 Organized PDF: {final_path}")
        
        # Update Paper object to point to new location
        paper.local_pdf_path = final_path
        paper.link = f"file://{final_path.absolute()}"

        # 3. Process
        paper_data = {'paper': paper, 'slot': 'Manual_PDF', 'tags': ['#Manual_PDF']}
    
        process_paper(
            paper_data, 
            config, 
            llm_provider, 
            is_deep_target=False,
            subfolder_override="Manual_PDFs", # Note: process_paper checks paper.local_pdf_path
            index_file_override="00_Index/manual_collection.csv"
        )
        logger.info(f"✅ Successfully processed local PDF: {title}")
        
    except Exception as e:
        logger.error(f"❌ Failed to process local PDF: {e}")
        # Move to Error folder (from final_path if it was moved, or pdf_path if move failed)
        error_dir = config.paths.watch_folder / "Error" # Relative to watch folder root
        error_dir.mkdir(exist_ok=True)
        
        source = final_path if final_path.exists() else pdf_path
        target = error_dir / source.name
        
        if source.exists():
            shutil.move(source, target)
            logger.info(f"   -> Moved to Error: {target}")

def process_on_demand_search(query: str, limit: int, dry_run: bool = False) -> List[Any]:
    """[NEW] On-Demand Search Function"""
    config = load_config()
    fetchers = get_fetchers(config)
    llm_provider = get_llm_provider(config.llm, config.entity_aliases)
    
    logger.info(f"🚀 Starting On-Demand Search: '{query}' (Limit: {limit})")
    
    # 1. Fetch
    candidates = []
    for fetcher in fetchers:
        try:
            logger.info(f"   - Fetching from {fetcher.source_name}...")
            # Divide limit among fetchers or use limit for each? Use limit for each is simpler for now.
            fetched = fetcher.fetch(query, max_results=limit)
            candidates.extend(fetched)
        except Exception as e:
            logger.error(f"     ❌ Error fetching from {fetcher.source_name}: {e}")
            
    # Deduplicate by ID
    unique_candidates = []
    seen_ids = set()
    for p in candidates:
        if p.id and p.id not in seen_ids:
            unique_candidates.append(p)
            seen_ids.add(p.id)
            
    logger.info(f"✅ Found {len(unique_candidates)} unique candidates.")

    # [NEW] Bibliometric Ranking (Ticket 3)
    if config.ranking.bibliometrics.enabled and unique_candidates:
        try:
            from src.ranking import BibliometricScorer
            scorer = BibliometricScorer(config)
            logger.info("📊 Applied Bibliometric Ranking to search results...")
            unique_candidates = scorer.calculate_scores(unique_candidates)
            if unique_candidates:
                top = unique_candidates[0]
                logger.info(f"   - Top ranked: {top.title[:40]}... (Score: {top.manual_rank_score})")
        except Exception as e:
            logger.error(f"❌ Ranking failed: {e}")
    
    if dry_run:
        return unique_candidates
        
    # 2. Process
    results = []
    for paper in unique_candidates:
        # Check DB to avoid re-processing same paper (unless we want to force?)
        if is_paper_processed(paper.id):
             logger.info(f"   ⏭️  Skipping duplicate (DB): {paper.title}")
             continue
             
        paper_data = {'paper': paper, 'slot': 'OnDemand', 'tags': ['#OnDemand']}
        try:
            # On-Demand papers are generally not targets for deep read unless specified.
            # We treat them as normal papers.
            # Override namespace
            res = process_paper(
                paper_data, 
                config, 
                llm_provider, 
                is_deep_target=False,
                subfolder_override="OnDemand",
                index_file_override="00_Index/on_demand.csv"
            )
            results.append(res)
        except Exception as e:
            logger.error(f"   ❌ Error processing {paper.title}: {e}")
            
    return results