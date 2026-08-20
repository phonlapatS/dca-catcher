import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List
import aiohttp
import feedparser

from src.catalyst.models import CatalystArticle
from src.catalyst.providers.base import BaseNewsProvider

logger = logging.getLogger(__name__)


class YahooFinanceProvider(BaseNewsProvider):
    """Fetches ticker news RSS feeds from Yahoo Finance."""

    BASE_URL = "https://finance.yahoo.com/rss/headline"

    async def fetch_articles_for_symbol(self, symbol: str) -> List[CatalystArticle]:
        url = f"{self.BASE_URL}?s={symbol}"

        articles: List[CatalystArticle] = []
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Yahoo Finance RSS returned status {response.status} for {symbol}")
                        return []
                    xml_content = await response.text()

            feed = feedparser.parse(xml_content)
            for entry in feed.entries:
                headline = getattr(entry, "title", "").strip()
                if not headline:
                    continue

                publisher = "Yahoo Finance"
                if hasattr(entry, "source"):
                    if hasattr(entry.source, "title"):
                        publisher = entry.source.title
                    elif isinstance(entry.source, dict) and "title" in entry.source:
                        publisher = entry.source["title"]
                    else:
                        publisher = str(entry.source)
                elif hasattr(entry, "publisher"):
                    publisher = str(entry.publisher)


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
            logger.error(f"Error fetching Yahoo Finance news for {symbol}: {e}")
            return []

        return articles
