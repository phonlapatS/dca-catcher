import abc
import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from src.catalyst.models import CatalystArticle


class BaseNewsProvider(abc.ABC):
    """Abstract base class for asynchronous financial news providers."""

    @abc.abstractmethod
    async def fetch_articles_for_symbol(self, symbol: str) -> List[CatalystArticle]:
        """Fetches recent news articles for a given ticker symbol."""
        pass

    @staticmethod
    def compute_hash(headline: str) -> str:
        """Generates a canonical SHA-256 hash for a news headline (case-insensitive & trimmed)."""
        normalized = headline.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
