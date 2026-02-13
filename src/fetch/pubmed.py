import requests
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.fetch.base import BaseFetcher
from src.schemas import Paper
from src.config import AppConfig

# Logger Setup
logger = logging.getLogger(__name__)

# Retry Configuration
RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=10),
    "retry": retry_if_exception_type((requests.RequestException, ConnectionError, TimeoutError))
}

class PubMedFetcher(BaseFetcher):
    @property
    def source_name(self) -> str:
        return "PubMed"

    def fetch(self, query: str, max_results: int) -> List[Paper]:
        """PubMed에서 키워드로 논문 검색"""
        papers: List[Paper] = []
        
        try:
            # 1. ESearh (Get IDs)
            logger.info(f"Connecting to PubMed (ESearch)... Query: {query}")
            id_list = self._esearch(query, max_results)
            
            if not id_list:
                logger.info("No papers found on PubMed.")
                return []

            # 2. EFetch (Get Details)
            logger.info(f"Fetching details for {len(id_list)} ids...")
            xml_content = self._efetch(id_list)
            
            # 3. Parsing
            root = ET.fromstring(xml_content)
            
            for article in root.findall(".//PubmedArticle"):
                try:
                    p = self._parse_article(article)
                    if p:
                        papers.append(p)
                except Exception as e:
                    logger.error(f"Error parsing single PubMed article: {e}")
                    continue
                
        except Exception as e:
            logger.error(f"Critical Error in PubMedFetcher: {e}", exc_info=True)
            
        return papers

    @retry(**RETRY_CONFIG)
    def _esearch(self, term: str, max_results: int) -> List[str]:
        """PubMed ID 검색"""
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        search_url = f"{base_url}/esearch.fcgi?db=pubmed&term={term}&retmode=json&retmax={max_results}&sort=date"
        
        resp = requests.get(search_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        return data.get("esearchresult", {}).get("idlist", [])

    @retry(**RETRY_CONFIG)
    def _efetch(self, ids: List[str]) -> str:
        """PubMed 상세 정보 가져오기"""
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        id_str = ",".join(ids)
        fetch_url = f"{base_url}/efetch.fcgi?db=pubmed&id={id_str}&retmode=xml"
        
        resp = requests.get(fetch_url, timeout=15)
        resp.raise_for_status()
        return resp.content

    def _parse_article(self, article: ET.Element) -> Optional[Paper]:
        medline = article.find("MedlineCitation")
        if medline is None:
            return None
            
        article_data = medline.find("Article")
        if article_data is None:
            return None
            
        # Title
        title_tag = article_data.find("ArticleTitle")
        title = title_tag.text if title_tag is not None else "No Title"
        
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
                    txt = last.text if last.text else ""
                    init = initial.text if initial.text else ""
                    authors_list.append(f"{txt} {init}")
        
        # IDs (PMID / DOI)
        pmid_tag = medline.find("PMID")
        pmid = pmid_tag.text if pmid_tag is not None else "00000"
        doi = ""
        
        # DOI logic
        elocation = article_data.find("ELocationID[@EIdType='doi']")
        if elocation is not None:
            doi = elocation.text
        else:
            id_list_tag = article.find("PubmedData/ArticleIdList")
            if id_list_tag is not None:
                doi_tag = id_list_tag.find("ArticleId[@IdType='doi']")
                if doi_tag is not None:
                    doi = doi_tag.text
        
        paper_id = doi if doi else f"PMID:{pmid}"
        published_date = self._parse_date(article_data)
        
        return Paper(
            id=paper_id,
            doi=doi if doi else None,
            title=title,
            authors=authors_list,
            link=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            published=published_date,
            source="PubMed",
            summary=abstract_text,
            pdf_link=None 
        )

    def _parse_date(self, article_data: ET.Element) -> str:
        pubdate = article_data.find("Journal/JournalIssue/PubDate")
        if pubdate is None:
            return "1900-01-01"

        year_tag = pubdate.find("Year")
        if year_tag is None:
            # MedlineDate fallback (e.g. "2000 Oct-Dec")
            medline_date = pubdate.find("MedlineDate")
            if medline_date is not None:
                return medline_date.text[:4] + "-01-01"
            return "1900-01-01"

        year = int(year_tag.text)
        month_tag = pubdate.find("Month")
        day_tag = pubdate.find("Day")
        
        month_str = month_tag.text if month_tag is not None else "Jan"
        day_str = day_tag.text if day_tag is not None else "01"

        try:
            month = datetime.strptime(month_str, "%b").month
        except ValueError:
            try:
                # Some XML has numerical month
                month = int(month_str)
            except ValueError:
                month = 1
        
        day = int(day_str) if day_str.isdigit() else 1

        return datetime(year, month, day).strftime("%Y-%m-%d")
