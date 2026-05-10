from abc import ABC, abstractmethod
from typing import List
from src.schemas import Paper
from src.config import AppConfig

class BaseFetcher(ABC):
    """
    Abstract Base Class for all paper fetchers.
    New sources (e.g., IEEE, Springer) must inherit from this class.
    """
    
    def __init__(self, config: AppConfig):
        self.config = config

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the source (e.g., 'PubMed', 'ArXiv')"""
        pass

    @abstractmethod
    def fetch(self, query: str, max_results: int) -> List[Paper]:
        """
        Fetch papers based on a query.
        
        Args:
            query (str): The search query string.
            max_results (int): Maximum number of papers to return.
            
        Returns:
            List[Paper]: A list of Paper objects.
        """
        pass
