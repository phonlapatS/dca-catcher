import logging
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List
import aiohttp
import feedparser

from src.catalyst.models import CatalystArticle
from src.catalyst.providers.base import BaseNewsProvider

logger = logging.getLogger(__name__)


class GoogleNewsProvider(BaseNewsProvider):
    """Fetches real-time RSS news feeds from Google News."""

    BASE_URL = "https://news.google.com/rss/search"

    async def fetch_articles_for_symbol(self, symbol: str) -> List[CatalystArticle]:
        encoded_query = urllib.parse.quote(f"{symbol} stock news")
        url = f"{self.BASE_URL}?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        articles: List[CatalystArticle] = []
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Google News RSS returned status {response.status} for {symbol}")
                        return []
                    xml_content = await response.text()
                    
            feed = feedparser.parse(xml_content)
            for entry in feed.entries:
                headline = getattr(entry, "title", "").strip()
                if not headline:
                    continue
                
                # Extract publisher
                publisher = "Google News"
                if hasattr(entry, "source") and hasattr(entry.source, "title"):
                    publisher = entry.source.title
                elif "-" in headline:
                    # Often "Headline - Publisher"
                    parts = headline.rsplit("-", 1)
                    if len(parts) == 2 and len(parts[1].strip()) < 40:
                        publisher = parts[1].strip()

                # Parse publication date
                published_at = datetime.now(timezone.utc)
                if hasattr(entry, "published"):
                    try:
                        published_at = parsedate_to_datetime(entry.published)
                    except Exception:
                        pass

                raw_snippet = getattr(entry, "summary", "") or getattr(entry, "description", "")
                headline_hash = self.compute_hash(headline)

                articles.append(
                    CatalystArticle(
                        headline=headline,
                        headline_hash=headline_hash,
                        symbol=symbol.upper(),
                        publisher=publisher,
                        published_at=published_at,
                        raw_snippet=raw_snippet
                    )
                )
        except Exception as e:
            logger.error(f"Error fetching Google News for {symbol}: {e}")
            return []

        return articles
