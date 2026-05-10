from typing import List
from src.config import AppConfig
from src.fetch.base import BaseFetcher
from src.fetch.pubmed import PubMedFetcher
from src.fetch.arxiv import ArXivFetcher

def get_fetchers(config: AppConfig) -> List[BaseFetcher]:
    """
    Returns a list of initialized Fetcher instances based on configuration.
    Example config:
      sources:
        pubmed: {enabled: true, priority: 1}
        arxiv: {enabled: true, priority: 2}
    """
    fetchers = []
    
    # 1. Check sources in config (if exists)
    # If not in config (MVP legacy), enable both by default
    sources = getattr(config, 'sources', None)
    
    if not sources:
        # Default Fallback
        fetchers.append(PubMedFetcher(config))
        fetchers.append(ArXivFetcher(config))
        return fetchers

    # 2. Add based on config
    # We sort by priority if available
    source_list = []
    
    if sources.get('pubmed', {}).get('enabled', True):
        prio = sources['pubmed'].get('priority', 1)
        source_list.append((prio, PubMedFetcher(config)))
        
    if sources.get('arxiv', {}).get('enabled', True):
        prio = sources['arxiv'].get('priority', 2)
        source_list.append((prio, ArXivFetcher(config)))
        
    # Sort by priority (asc)
    source_list.sort(key=lambda x: x[0])
    
    return [f[1] for f in source_list]
