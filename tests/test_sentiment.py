import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from src.scrapers.sentiment import get_fear_greed_index, get_recent_news

class TestSentimentScraper(unittest.TestCase):
    def test_get_fear_greed_index_mock(self):
        # We will test the module function exists and returns a string
        result = get_fear_greed_index()
        self.assertIsInstance(result, str)

    def test_get_recent_news(self):
        result = get_recent_news('AAPL')
        self.assertIsInstance(result, list)

if __name__ == '__main__':
    unittest.main()
