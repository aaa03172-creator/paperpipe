import feedparser
import requests
import urllib.parse
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.schemas import Paper

# Logger Setup
logger = logging.getLogger(__name__)

# Retry Configuration
RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=10),
    "retry": retry_if_exception_type((requests.RequestException, ConnectionError, TimeoutError))
}

@retry(**RETRY_CONFIG)
def fetch_arxiv(keywords: List[str], max_results: int = 5) -> List[Paper]:
    """ArXiv에서 키워드로 논문 검색 (Retry 적용)"""
    papers = []
    # 검색어 조합 (OR 로직)
    query = " OR ".join([f'all:"{k}"' for k in keywords])
    encoded_query = urllib.parse.quote(query)
    
    url = f"http://export.arxiv.org/api/query?search_query={encoded_query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    
    logger.debug(f"Fetching ArXiv: {url}")
    feed = feedparser.parse(url)
    
    if hasattr(feed, 'bozo') and feed.bozo:
        logger.warning(f"ArXiv feed parse error: {feed.bozo_exception}")

    for entry in feed.entries:
        try:
            # 날짜 필터링 (최근 7일 이내만)
            published = datetime(*entry.published_parsed[:6])
            if datetime.now() - published > timedelta(days=7):
                continue
            
            arxiv_id = entry.link.split("/abs/")[-1]
            pdf_link = entry.link.replace("/abs/", "/pdf/")

            papers.append(Paper(
                id=arxiv_id,
                title=entry.title.replace("\n", " "),
                authors=[a.name for a in entry.authors],
                link=entry.link,
                published=published.strftime("%Y-%m-%d"),
                source="ArXiv",
                summary=entry.summary,
                pdf_link=pdf_link
            ))
        except Exception as e:
            logger.error(f"Error parsing ArXiv entry: {e}")
            continue
    
    return papers

def _parse_pubmed_article_date(article_data) -> str:
    """PubMed 날짜 파싱 헬퍼"""
    pubdate = article_data.find("Journal/JournalIssue/PubDate")
    if pubdate is None:
        return "1900-01-01"

    year_tag = pubdate.find("Year")
    month_tag = pubdate.find("Month")
    day_tag = pubdate.find("Day")
    
    year = int(year_tag.text) if year_tag is not None and year_tag.text else 1900
    month_str = month_tag.text if month_tag is not None else "Jan"
    day_str = day_tag.text if day_tag is not None else "01"

    try:
        month = datetime.strptime(month_str, "%b").month
    except ValueError:
        try:
            month = int(month_str)
        except ValueError:
            month = 1
    
    day = int(day_str) if day_str.isdigit() else 1

    return datetime(year, month, day).strftime("%Y-%m-%d")

@retry(**RETRY_CONFIG)
def _esearch_pubmed(term: str, max_results: int) -> List[str]:
    """PubMed ID 검색 (ESearch)"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search_url = f"{base_url}/esearch.fcgi?db=pubmed&term={term}&retmode=json&retmax={max_results}&sort=date"
    
    resp = requests.get(search_url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    
    return data.get("esearchresult", {}).get("idlist", [])

@retry(**RETRY_CONFIG)
def _efetch_pubmed(ids: List[str]) -> str:
    """PubMed 상세 정보 가져오기 (EFetch)"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    id_str = ",".join(ids)
    fetch_url = f"{base_url}/efetch.fcgi?db=pubmed&id={id_str}&retmode=xml"
    
    resp = requests.get(fetch_url, timeout=15)
    resp.raise_for_status()
    return resp.content

def fetch_pubmed(keywords: List[str], max_results: int = 5) -> List[Paper]:
    """PubMed에서 키워드로 논문 검색 (Robust)"""
    papers = []
    term = " OR ".join(keywords)
    
    try:
        # 1. ID Search
        logger.info(f"Connecting to PubMed (ESearch)... Term length: {len(term)}")
        id_list = _esearch_pubmed(term, max_results)
        
        if not id_list:
            logger.info("No papers found on PubMed.")
            return []

        # 2. Detail Fetch
        logger.info(f"Fetching details for {len(id_list)} papers...")
        xml_content = _efetch_pubmed(id_list)
        
        # 3. Parsing
        root = ET.fromstring(xml_content)
        
        for article in root.findall(".//PubmedArticle"):
            try:
                medline = article.find("MedlineCitation")
                article_data = medline.find("Article")
                
                # Title
                title = article_data.find("ArticleTitle").text or "No Title"
                
                # Abstract
                abstract_text = ""
                abstract = article_data.find("Abstract")
                if abstract is not None:
                    texts = ["".join(elem.itertext()) for elem in abstract.findall("AbstractText")]
                    abstract_text = " ".join(t for t in texts if t)
                
                # Authors
                authors_list = []
                author_list_tag = article_data.find("AuthorList")
                if author_list_tag is not None:
                    for author in author_list_tag.findall("Author"):
                        last = author.find("LastName")
                        initial = author.find("Initials")
                        if last is not None and initial is not None:
                            authors_list.append(f"{last.text} {initial.text}")
                
                # IDs (PMID / DOI)
                pmid = medline.find("PMID").text
                doi = ""
                
                # DOI logic 1
                elocation = article_data.find("ELocationID[@EIdType='doi']")
                if elocation is not None:
                    doi = elocation.text
                else:
                    # DOI logic 2
                    id_list_tag = article.find("PubmedData/ArticleIdList")
                    if id_list_tag is not None:
                        doi_tag = id_list_tag.find("ArticleId[@IdType='doi']")
                        if doi_tag is not None:
                            doi = doi_tag.text
                
                paper_id = doi if doi else f"PMID:{pmid}"
                published_date = _parse_pubmed_article_date(article_data)
                
                papers.append(Paper(
                    id=paper_id,
                    title=title,
                    authors=authors_list,
                    link=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    published=published_date,
                    source="PubMed",
                    summary=abstract_text,
                    pdf_link=None 
                ))
            except Exception as e:
                logger.error(f"Error parsing single PubMed article: {e}")
                continue
            
    except Exception as e:
        logger.error(f"Critical Error in fetch_pubmed: {e}", exc_info=True)
        
    return papers
