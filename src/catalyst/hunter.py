import logging
from datetime import datetime, timezone
from typing import List, Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.database import Database

from src.catalyst.models import CatalystArticle, CatalystVerdict
from src.catalyst.providers.google_news import GoogleNewsProvider
from src.catalyst.providers.yahoo_finance import YahooFinanceProvider
from src.catalyst.verifiers.density_filter import DensityFilter
from src.catalyst.verifiers.market_check import MarketMicrostructureChecker
from src.catalyst.evaluator import CatalystEvaluator

logger = logging.getLogger(__name__)


class CatalystHunter:
    """Proactive Market Catalyst & Supply Chain Hunter Orchestrator."""

    def __init__(
        self,
        db: Database,
        bot=None,
        channel_id: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        providers=None,
    ):
        self.db = db
        self.bot = bot
        self.channel_id = channel_id
        self.providers = providers or [GoogleNewsProvider(), YahooFinanceProvider()]
        self.density_filter = DensityFilter()
        self.microstructure_checker = MarketMicrostructureChecker()
        self.evaluator = CatalystEvaluator(api_key=gemini_api_key)

    async def run_scan_cycle(self, symbols: Optional[List[str]] = None) -> int:
        """Runs a complete scan cycle across specified symbols or master watchlist."""
        if symbols is None:
            symbols = await self.db.get_unique_watchlist_symbols(market="US")
            if not symbols:
                symbols = ["NVDA", "MRNA", "TSLA", "AAPL", "AMD", "PLTR", "CRWD"]

        processed_count = 0

        for symbol in symbols:
            for provider in self.providers:
                try:
                    articles = await provider.fetch_articles_for_symbol(symbol)
                except Exception as e:
                    logger.error(f"Provider error for {symbol}: {e}")
                    continue

                for article in articles:
                    # 1. Deduplication Gate (0-Token DB lookup)
                    if await self.db.is_catalyst_seen(article.headline_hash):
                        continue

                    # 2. Fact Density Gate (0-Token Filter)
                    if not self.density_filter.is_high_density(article.headline, article.raw_snippet):
                        # Still record as seen to prevent re-processing
                        await self.db.record_seen_catalyst(
                            headline_hash=article.headline_hash,
                            symbol=article.symbol,
                            headline=article.headline,
                            publisher=article.publisher,
                        )
                        continue

                    # 3. Dual-Perspective AI Evaluation (Gemini)
                    verdict = await self.evaluator.evaluate_catalyst(article)

                    # 4. Dispatch Alert if Material Catalyst (Score >= 8.0)
                    if verdict.is_material and verdict.materiality_score >= 8.0:
                        await self._dispatch_catalyst_alert(article, verdict)
                        processed_count += 1

                    # 5. Record Hash in Database
                    await self.db.record_seen_catalyst(
                        headline_hash=article.headline_hash,
                        symbol=article.symbol,
                        headline=article.headline,
                        publisher=article.publisher,
                    )

        return processed_count

    async def _dispatch_catalyst_alert(self, article: CatalystArticle, verdict: CatalystVerdict):
        """Formats and dispatches the catalyst alert with interactive action hub buttons."""
        if not self.bot or not self.channel_id:
            logger.warning("Telegram Bot or Channel ID not configured for Catalyst alert")
            return

        date_str = article.published_at.strftime("%d/%m/%Y เวลา %H:%M น.")
        
        # Build Connected Stocks String
        connected_section = ""
        if verdict.connected_stocks:
            connected_lines = []
            for item in verdict.connected_stocks:
                icon = "🟢" if item.impact_direction == "POSITIVE" else "🔴"
                connected_lines.append(f"• {icon} ${item.symbol}: {item.rationale_thai}")
            connected_section = "\n\n🔗 หุ้นที่เชื่อมโยงในห่วงโซ่อุปทาน (Supply Chain Spillovers):\n" + "\n".join(connected_lines)

        text = (
            f"🚨 BREAKING CATALYST: #{article.symbol}\n"
            f"⏰ อัปเดตล่าสุด: {date_str} (เวลาไทย)\n\n"
            f"📰 แหล่งที่มา: {article.publisher}\n"
            f"📌 สรุปข่าว: {verdict.thai_summary}\n\n"
            f"📊 การประเมินพื้นฐาน 2 ด้าน (Dual-Perspective Analysis):\n"
            f"• 🟢 ปัจจัยบวก: {verdict.bull_catalysts}\n"
            f"• 🔴 ความเสี่ยง: {verdict.bear_risks}"
            f"{connected_section}\n\n"
            f"🛒 แผนกลยุทธ์ DCA Catcher:\n"
            f"{verdict.dca_guidance}"
        )

        # Build Interactive Keyboards
        buttons = [
            [
                InlineKeyboardButton(text="➕ เพิ่มเข้า Watchlist", callback_data=f"cat_watch_{article.symbol}"),
                InlineKeyboardButton(text="🎯 ตั้งเป้า Sniper", callback_data=f"cat_sniper_{article.symbol}"),
            ]
        ]

        # Add buttons for connected stocks
        connected_row = []
        for item in verdict.connected_stocks[:2]:  # Limit to top 2 for clean UI
            connected_row.append(
                InlineKeyboardButton(text=f"🔍 สแกน ${item.symbol}", callback_data=f"cat_scan_{item.symbol}")
            )
        if connected_row:
            buttons.append(connected_row)

        reply_markup = InlineKeyboardMarkup(inline_keyboard=buttons)


        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=text,
                reply_markup=reply_markup,
            )
            logger.info(f"Dispatched Catalyst Alert for {article.symbol} to {self.channel_id}")
        except Exception as e:
            logger.error(f"Failed to dispatch Telegram Catalyst alert: {e}")
