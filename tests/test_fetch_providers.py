import unittest
from unittest.mock import MagicMock, patch
from src.config import AppConfig
from src.fetch import get_fetchers
from src.fetch.pubmed import PubMedFetcher
from src.fetch.arxiv import ArXivFetcher

class TestFetchProviders(unittest.TestCase):
    def test_get_fetchers_default(self):
        """Test default behavior when sources not in config"""
        config = MagicMock(spec=AppConfig)
        # remove 'sources' attribute to simulate missing config
        del config.sources 
        
        # This part is tricky with MagicMock because getattr(mock, 'sources', None) returns the mock itself usually.
        # So we need to ensure the mock behaves like an object without that attribute or returns None.
        # Let's mock the config object differently or patch getattr logic.
        # Simpler: Create a dummy object.
        class DummyConfig:
            pass
        
        fetchers = get_fetchers(DummyConfig())
        self.assertEqual(len(fetchers), 2)
        self.assertIsInstance(fetchers[0], PubMedFetcher)
        self.assertIsInstance(fetchers[1], ArXivFetcher)

    def test_get_fetchers_config_enable_disable(self):
        """Test enabling/disabling sources via config"""
        class DummyConfig:
            pass
        
        config = DummyConfig()
        config.sources = {
            'pubmed': {'enabled': True, 'priority': 2},
            'arxiv': {'enabled': False, 'priority': 1}
        }
        
        fetchers = get_fetchers(config)
        self.assertEqual(len(fetchers), 1)
        self.assertIsInstance(fetchers[0], PubMedFetcher)

    def test_get_fetchers_priority(self):
        """Test priority sorting"""
        class DummyConfig:
            pass
        
        config = DummyConfig()
        # ArXiv priority 1 (first), PubMed priority 2 (second)
        config.sources = {
            'pubmed': {'enabled': True, 'priority': 2},
            'arxiv': {'enabled': True, 'priority': 1}
        }
        
        fetchers = get_fetchers(config)
        self.assertEqual(len(fetchers), 2)
        self.assertIsInstance(fetchers[0], ArXivFetcher)
        self.assertIsInstance(fetchers[1], PubMedFetcher)

if __name__ == '__main__':
    unittest.main()
