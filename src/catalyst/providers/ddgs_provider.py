import logging
from typing import List
import asyncio
from datetime import datetime, timezone
import hashlib

from src.catalyst.models import CatalystArticle

logger = logging.getLogger(__name__)

class DDGSNewsProvider:
    """Fetches news via DuckDuckGo Search API (ddgs)."""
    
    async def fetch_articles_for_symbol(self, symbol: str) -> List[CatalystArticle]:
        try:
            # ddgs is synchronous, so wrap in asyncio.to_thread to not block Event Loop
            def _fetch():
                from ddgs import DDGS
                with DDGS() as ddgs:
                    # Query strictly for stock news to avoid random irrelevant articles
                    return list(ddgs.news(f"{symbol} stock market news", max_results=10))
            
            results = await asyncio.to_thread(_fetch)
            
            articles = []
            for item in results:
                # item format: {'date': '...', 'title': '...', 'body': '...', 'url': '...', 'source': '...'}
                date_str = item.get("date", "")
                try:
                    pub_date = datetime.fromisoformat(date_str)
                except Exception:
                    pub_date = datetime.now(timezone.utc)
                    
                title = item.get("title", "")
                body = item.get("body", "")
                source = item.get("source", "DuckDuckGo")
                
                if not title:
                    continue
                    
                hl_hash = hashlib.md5(title.encode("utf-8")).hexdigest()
                
                articles.append(CatalystArticle(
                    headline=title,
                    headline_hash=hl_hash,
                    symbol=symbol.upper(),
                    publisher=source,
                    published_at=pub_date,
                    raw_snippet=body
                ))
                
            return articles
        except Exception as e:
            logger.error(f"DDGS fetch error for {symbol}: {e}")
            return []
