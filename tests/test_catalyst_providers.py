import hashlib
import pytest
from unittest.mock import AsyncMock, patch
from src.catalyst.providers.google_news import GoogleNewsProvider
from src.catalyst.providers.yahoo_finance import YahooFinanceProvider
from src.catalyst.models import CatalystArticle

SAMPLE_GOOGLE_NEWS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Google News - MRNA</title>
    <item>
      <title>Moderna Reports Positive Phase 3 Trial Results - Business Wire</title>
      <link>https://news.google.com/rss/articles/12345</link>
      <pubDate>Thu, 20 Aug 2026 10:45:00 GMT</pubDate>
      <description>Merck and Moderna announce positive results for melanoma vaccine.</description>
      <source url="https://www.businesswire.com">Business Wire</source>
    </item>
    <item>
      <title>Why Moderna Stock Is Surging Today - Motley Fool</title>
      <link>https://news.google.com/rss/articles/67890</link>
      <pubDate>Thu, 20 Aug 2026 11:00:00 GMT</pubDate>
      <description>Shares of biotech giant jump after big announcement.</description>
      <source url="https://www.fool.com">Motley Fool</source>
    </item>
  </channel>
</rss>
"""

SAMPLE_YAHOO_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Yahoo Finance - NVDA</title>
    <item>
      <title>Nvidia expands datacenter architecture with new partners</title>
      <link>https://finance.yahoo.com/news/11111</link>
      <pubDate>Thu, 20 Aug 2026 09:30:00 GMT</pubDate>
      <description>Nvidia announced new server partnerships with liquid cooling providers.</description>
      <source>Reuters</source>
    </item>
  </channel>
</rss>
"""

@pytest.mark.asyncio
async def test_google_news_provider_parse():
    provider = GoogleNewsProvider()
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=SAMPLE_GOOGLE_NEWS_RSS)
        mock_get.return_value.__aenter__.return_value = mock_response

        articles = await provider.fetch_articles_for_symbol("MRNA")
        assert len(articles) == 2
        
        art1 = articles[0]
        assert art1.symbol == "MRNA"
        assert "Phase 3 Trial Results" in art1.headline
        assert art1.publisher == "Business Wire"
        assert len(art1.headline_hash) == 64
        # Verify SHA-256 calculation
        expected_hash = hashlib.sha256(art1.headline.strip().lower().encode("utf-8")).hexdigest()
        assert art1.headline_hash == expected_hash

@pytest.mark.asyncio
async def test_yahoo_finance_provider_parse():
    provider = YahooFinanceProvider()
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=SAMPLE_YAHOO_RSS)
        mock_get.return_value.__aenter__.return_value = mock_response

        articles = await provider.fetch_articles_for_symbol("NVDA")
        assert len(articles) == 1
        
        art = articles[0]
        assert art.symbol == "NVDA"
        assert "Nvidia expands datacenter" in art.headline
        assert art.publisher == "Reuters"
        assert len(art.headline_hash) == 64

@pytest.mark.asyncio
async def test_provider_network_error_graceful_handling():
    provider = GoogleNewsProvider()
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.side_effect = Exception("Connection Timeout")
        articles = await provider.fetch_articles_for_symbol("AAPL")
        assert articles == []
