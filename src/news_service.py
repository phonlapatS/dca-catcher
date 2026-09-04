import logging
import json
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta

from src.database import Database
from src.catalyst.evaluator import CatalystEvaluator
from src.catalyst.models import CatalystVerdict, CatalystArticle

logger = logging.getLogger(__name__)

class JunkFilter:
    """Dynamic heuristic filter to weed out clickbait and noise."""
    
    # In a fully dynamic system, this could be loaded from a DB or YAML config.
    DEFAULT_JUNK_TERMS = {
        "zacks", "motley fool", "top 10", "stocks to buy", 
        "buy or sell", "market update", "daily summary", "investopedia"
    }

    def __init__(self, additional_terms: Optional[set] = None):
        self.junk_terms = self.DEFAULT_JUNK_TERMS.copy()
        if additional_terms:
            self.junk_terms.update(additional_terms)

    def is_junk(self, headline: str) -> bool:
        hl_lower = headline.lower()
        return any(term in hl_lower for term in self.junk_terms)


class NewsService:
    """
    Centralized OOP Service for handling news caching, live fallback, 
    and context-aware formatting for different bot commands.
    """

    def __init__(self, db: Database, evaluator: CatalystEvaluator, providers: list):
        self.db = db
        self.evaluator = evaluator
        self.providers = providers
        self.junk_filter = JunkFilter()

    async def _get_cached_news(self, symbol: str, hours: int = 48) -> List[CatalystVerdict]:
        """Fetches and deserializes AI-evaluated news from the database cache."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        verdicts = []
        
        async with self.db.session() as session:
            from sqlalchemy import select
            from src.database import SeenCatalyst
            
            stmt = select(SeenCatalyst).where(
                SeenCatalyst.symbol == symbol.upper(),
                SeenCatalyst.seen_at >= cutoff,
                SeenCatalyst.metadata_json.is_not(None)
            ).order_by(SeenCatalyst.seen_at.desc())
            
            result = await session.execute(stmt)
            for row in result.scalars():
                try:
                    data = json.loads(row.metadata_json)
                    verdicts.append(CatalystVerdict(**data))
                except Exception as e:
                    logger.debug(f"Failed to parse metadata_json for {symbol}: {e}")
                    
        return verdicts

    async def _fetch_and_evaluate_live(self, symbol: str, limit: int = 3) -> List[CatalystVerdict]:
        """Live fallback: Fetches fresh news, applies heuristics, and evaluates via AI."""
        live_verdicts = []
        for provider in self.providers:
            try:
                articles = await provider.fetch_articles_for_symbol(symbol)
                for article in articles:
                    if len(live_verdicts) >= limit:
                        break
                        
                    if await self.db.is_catalyst_seen(article.headline_hash):
                        continue
                        
                    if self.junk_filter.is_junk(article.headline):
                        await self.db.record_seen_catalyst(
                            article.headline_hash, article.symbol, article.headline, article.publisher
                        )
                        continue

                    # Evaluate using Gemini Flash
                    verdict = await self.evaluator.evaluate_catalyst(article)
                    
                    # Cache the result
                    await self.db.record_seen_catalyst(
                        article.headline_hash, article.symbol, article.headline, 
                        article.publisher, metadata_json=verdict.model_dump_json()
                    )
                    
                    live_verdicts.append(verdict)
            except Exception as e:
                logger.error(f"Error fetching live news from {provider.__class__.__name__}: {e}")
                
        return live_verdicts

    async def get_scan_teaser(self, symbol: str) -> str:
        """
        Builds the 1-3 line news teaser for the /scan command.
        Uses Cascade pattern: Cache (S-Tier) -> Live Fetch -> Fallback.
        """
        # 1. Check Cache for S-Tier (Score >= 8.0)
        cached = await self._get_cached_news(symbol, hours=48)
        s_tier = [v for v in cached if v.is_material and v.materiality_score >= 8.0]
        
        # 2. Live Fallback if no S-Tier
        if not s_tier:
            live_news = await self._fetch_and_evaluate_live(symbol, limit=2)
            s_tier = [v for v in live_news if v.is_material and v.materiality_score >= 8.0]
            if not s_tier:
                # Still no S-Tier? Fallback to A/B Tier from cache/live
                fallback_tier = [v for v in (cached + live_news) if v.materiality_score >= 5.0]
                # Sort by score
                fallback_tier.sort(key=lambda x: x.materiality_score, reverse=True)
                if fallback_tier:
                    v = fallback_tier[0]
                    icon = "🟡" # A/B Tier warning
                    return f"📰 **News Update (ทั่วไป):**\n{icon} *{v.impact_summary}* (ความน่าเชื่อถือ {v.confidence_score}%)"
                return "" # Pure Empty State (Very rare)

        # 3. Format S-Tier result
        lines = ["📰 **Breaking News:**"]
        # Sort S-tier by score descending
        s_tier.sort(key=lambda x: x.materiality_score, reverse=True)
        for v in s_tier[:2]:
            icon = "🔴" if "NEGATIVE" in v.bear_risks.upper() and v.materiality_score >= 9.0 else "🔸"
            lines.append(f"{icon} *{v.impact_summary}* (ความน่าเชื่อถือ {v.confidence_score}%)")
            
        return "\n".join(lines)

    async def get_news_radar(self, symbol: str) -> str:
        """
        Builds a comprehensive news radar report for the /news command.
        Groups news by tier (S, A, B, C) and context (Macro, Sector, Micro).
        """
        # Get cached + fetch a few live to enrich
        cached = await self._get_cached_news(symbol, hours=72)
        live_news = await self._fetch_and_evaluate_live(symbol, limit=4)
        
        all_news = cached + live_news
        if not all_news:
            return f"📰 **News Radar: ${symbol}**\n\nไม่มีความเคลื่อนไหวใดๆ ในช่วง 3 วันที่ผ่านมา"
            
        # Grouping
        s_tier, a_tier, b_tier, c_tier = [], [], [], []
        
        # Use headline hash to deduplicate in memory just in case
        seen_summaries = set()
        
        for v in all_news:
            if v.thai_summary in seen_summaries:
                continue
            seen_summaries.add(v.thai_summary)
            
            if v.materiality_score >= 9.0:
                s_tier.append(v)
            elif v.materiality_score >= 7.5:
                a_tier.append(v)
            elif v.materiality_score >= 5.0:
                b_tier.append(v)
            else:
                c_tier.append(v)
                
        def format_group(title, items, icon):
            if not items: return ""
            lines = [f"\n{icon} **{title}**"]
            items.sort(key=lambda x: x.materiality_score, reverse=True)
            for item in items[:4]: # Limit to top 4 per tier
                sentiment = getattr(item, 'sentiment', 'NEUTRAL').upper()
                if sentiment == "POSITIVE":
                    sent_tag = "🟢[บวก]"
                elif sentiment == "NEGATIVE":
                    sent_tag = "🔴[ลบ]"
                else:
                    sent_tag = "⚪[กลาง]"
                    
                scope_tag = f"[{getattr(item, 'scope', 'MICRO')}]"
                lines.append(
                    f"• {scope_tag} {sent_tag} *{item.thai_summary}* "
                    f"\n   ↳ 💡 Impact: {item.impact_summary} (Conf: {item.confidence_score}%)"
                )
            return "\n".join(lines)
            
        report = [f"📰 **News Radar 360°: ${symbol}**\n*(คัดกรองและประเมินผลโดย AI)*"]
        
        report.append(format_group("Major Catalysts (S-Tier)", s_tier, "🔴"))
        report.append(format_group("Significant Movers (A-Tier)", a_tier, "🟡"))
        report.append(format_group("General Updates (B-Tier)", b_tier, "🔵"))
        report.append(format_group("Market Noise / PR (C-Tier)", c_tier, "⚪️"))
        
        return "\n".join([r for r in report if r])

