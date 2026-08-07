import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.token import TokenValidationError, validate_token
from sqlalchemy import select

from src.config import Config
from src.database import Database, Signal, User, Watchlist
from src.fetcher import MarketDataFetcher
from src.grader import SignalGrader
from src.transform import DataTransformer

logger = logging.getLogger(__name__)

GRADE_EMOJIS = {
    1: "🔴",
    2: "🟡",
    3: "🟢",
    4: "🌟",
}

GRADE_LABELS = {
    1: "Risky (มีความเสี่ยงสูง)",
    2: "Moderate (ถือ/รอดู)",
    3: "Low Risk (เหมาะแก่การ DCA)",
    4: "Strong Buy (สัญญาณซื้อแข็งแกร่ง)",
}


def create_add_watchlist_keyboard(symbol: str, bot_username: str) -> InlineKeyboardMarkup:
    """Create an inline keyboard button with deep link to add a symbol to user's watchlist.

    Deep link format: t.me/bot_username?start=add_SYMBOL
    """
    url = f"https://t.me/{bot_username}?start=add_{symbol}"
    button = InlineKeyboardButton(text=f"➕ Add {symbol} to Watchlist", url=url)
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


class DCABot:
    """Main application class — wires all components and handles Telegram commands."""

    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config.database_url)
        self.fetcher = MarketDataFetcher()
        self.transformer = DataTransformer()
        self.grader = SignalGrader(config.gemini_api_key)

        token = config.telegram_token
        try:
            validate_token(token)
        except TokenValidationError:
            token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self._register_handlers()

    def _register_handlers(self):
        """Register all Telegram command handlers."""
        self.dp.message.register(self.cmd_start, Command("start"))
        self.dp.message.register(self.cmd_add, Command("add"))
        self.dp.message.register(self.cmd_list, Command("list"))
        self.dp.message.register(self.cmd_scan, Command("scan"))

    async def _add_to_watchlist(
        self, telegram_id: int, username: str | None, symbol: str, market: str
    ) -> str:
        """Helper method to upsert user and add symbol to watchlist."""
        async with self.db.session() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                user = User(telegram_id=telegram_id, username=username)
                session.add(user)
                await session.commit()
                await session.refresh(user)

            stmt_w = select(Watchlist).where(
                Watchlist.user_id == user.id, Watchlist.symbol == symbol
            )
            res_w = await session.execute(stmt_w)
            existing = res_w.scalar_one_or_none()

            if existing:
                return f"ℹ️ Symbol {symbol} ({market}) is already in your watchlist."
            else:
                item = Watchlist(user_id=user.id, symbol=symbol, market=market)
                session.add(item)
                await session.commit()
                return f"✅ Added {symbol} ({market}) to your watchlist."

    async def cmd_start(self, message: types.Message, command: CommandObject | None = None):
        """Handle /start — welcome message and deep links (e.g. /start add_NVDA)."""
        if command and command.args and command.args.startswith("add_"):
            if not message.from_user:
                return
            symbol = command.args.split("_", 1)[1].upper()
            market = "TH" if symbol.endswith(".BK") else "US"
            await message.answer(f"⏳ Adding {symbol} to your watchlist...")
            res_text = await self._add_to_watchlist(
                message.from_user.id, message.from_user.username, symbol, market
            )
            await message.answer(res_text)
            return

        welcome_text = (
            "👋 Welcome to DCA Catcher Bot!\n"
            "ยินดีต้อนรับสู่ระบบวิเคราะห์หุ้นสำหรับ DCA ด้วย AI\n\n"
            "📌 Available Commands (คำสั่งที่ใช้งานได้):\n"
            "/add <symbol> [market] - Add stock to watchlist (e.g. /add NVDA US, /add PTT.BK TH)\n"
            "/list - View your watchlist (ดูรายการหุ้นใน watchlist)\n"
            "/scan [symbol] - Run AI DCA analysis (วิเคราะห์หุ้นด้วย AI)"
        )
        await message.answer(welcome_text)

    async def cmd_add(self, message: types.Message):
        """Handle /add <symbol> <market> — add stock to user's watchlist.

        Usage: /add NVDA US  or  /add PTT TH
        - Creates user if not exists (upsert by telegram_id)
        - Adds symbol+market to their watchlist
        - Responds with confirmation
        """
        if not message.text or not message.from_user:
            return

        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.reply(
                "❌ Usage: /add <symbol> [market]\n"
                "Example: /add NVDA US or /add PTT.BK TH"
            )
            return

        symbol = parts[1].upper()
        market = parts[2].upper() if len(parts) >= 3 else ("TH" if symbol.endswith(".BK") else "US")

        telegram_id = message.from_user.id
        username = message.from_user.username

        res_text = await self._add_to_watchlist(telegram_id, username, symbol, market)
        await message.reply(res_text)

    async def cmd_list(self, message: types.Message):
        """Handle /list — show user's watchlist."""
        if not message.from_user:
            return

        telegram_id = message.from_user.id

        async with self.db.session() as session:
            stmt = select(Watchlist).join(User, Watchlist.user_id == User.id).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            items = res.scalars().all()

            if not items:
                await message.reply(
                    "📋 Your watchlist is empty.\n"
                    "Add stocks using: /add <symbol> [market]"
                )
                return

            lines = ["📋 Your Watchlist (รายการหุ้นของคุณ):"]
            for item in items:
                lines.append(f"• {item.symbol} ({item.market})")

            await message.reply("\n".join(lines))

    async def cmd_scan(self, message: types.Message):
        """Handle /scan [symbol] — run analysis pipeline.

        If symbol provided: scan that specific symbol.
        If no symbol: scan all symbols in user's watchlist.

        Pipeline: fetch → transform → grade → format → reply
        """
        if not message.text or not message.from_user:
            return

        parts = message.text.strip().split()
        symbols: list[str] = []

        if len(parts) >= 2:
            symbols = [parts[1].upper()]
        else:
            # Query user's watchlist
            telegram_id = message.from_user.id
            async with self.db.session() as session:
                stmt = select(Watchlist.symbol).join(User, Watchlist.user_id == User.id).where(User.telegram_id == telegram_id)
                res = await session.execute(stmt)
                symbols = list(res.scalars().all())

        if not symbols:
            await message.reply(
                "⚠️ Watchlist is empty and no symbol provided.\n"
                "Specify a symbol to scan (e.g. /scan NVDA) or add stocks to your watchlist with /add <symbol> <market>."
            )
            return

        await message.reply(f"🔍 Scanning {len(symbols)} symbol(s): {', '.join(symbols)}...")

        snapshots = self.fetcher.fetch(symbols)
        if not snapshots:
            await message.reply(f"❌ Failed to fetch market data for: {', '.join(symbols)}")
            return

        enriched_signals = self.transformer.enrich(snapshots)

        async with self.db.session() as session:
            for symbol, enriched in enriched_signals.items():
                grade_result = self.grader.grade(enriched)

                # Save signal to database
                signal_entry = Signal(
                    symbol=grade_result.symbol,
                    grade=grade_result.grade,
                    confidence=grade_result.confidence,
                    advice=grade_result.advice,
                )
                session.add(signal_entry)

                emoji = GRADE_EMOJIS.get(grade_result.grade, "❓")
                label = GRADE_LABELS.get(grade_result.grade, "Unknown")
                snapshot = enriched.snapshot

                reasons_str = (
                    "\n".join(f"  • {r}" for r in grade_result.reasons)
                    if grade_result.reasons
                    else "  • N/A"
                )

                report_text = (
                    f"{emoji} DCA Analysis: {grade_result.symbol}\n"
                    f"Grade: {grade_result.grade}/4 — {label}\n"
                    f"Confidence: {grade_result.confidence}%\n\n"
                    f"📊 Market Snapshot:\n"
                    f"• Current Price: ${snapshot.current_price:,.2f}\n"
                    f"• Drawdown from ATH: {snapshot.drawdown_pct}%\n"
                    f"• ATH Price: ${snapshot.ath_price:,.2f}\n\n"
                    f"💡 AI Advice (คำแนะนำ):\n"
                    f"{grade_result.advice}\n\n"
                    f"📝 Reasons:\n"
                    f"{reasons_str}"
                )
                await message.reply(report_text)

            await session.commit()

    async def start(self):
        """Initialize database and start polling."""
        logger.info("Initializing database tables...")
        await self.db.create_tables()
        logger.info("Starting Telegram bot polling...")
        await self.dp.start_polling(self.bot)

    async def stop(self):
        """Cleanup: close database connections."""
        logger.info("Closing database connections...")
        await self.db.close()
        await self.bot.session.close()


async def main():
    config = Config.from_env()
    bot = DCABot(config)
    try:
        await bot.start()
    finally:
        await bot.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
