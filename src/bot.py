import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.token import TokenValidationError, validate_token
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
        self.dp.message.register(self.cmd_remove, Command("remove"))
        self.dp.message.register(self.cmd_list, Command("list"))
        self.dp.message.register(self.cmd_scan, Command("scan"))
        self.dp.message.register(self.cmd_help, Command("help"))

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
            "พิมพ์ /help เพื่อดูคำสั่งทั้งหมดที่ใช้งานได้ครับ"
        )
        await message.answer(welcome_text)

    async def cmd_help(self, message: types.Message):
        """Handle /help — display all available commands and their usage."""
        help_text = (
            "📌 **Available Commands (คำสั่งทั้งหมดที่ใช้งานได้):**\n\n"
            "🔹 `/start` - เริ่มต้นใช้งานบอท และดูคำทักทาย\n"
            "🔹 `/help` - แสดงหน้านี้ (รายการคำสั่งทั้งหมด)\n"
            "🔹 `/add <ชื่อหุ้น> [ตลาด]` - เพิ่มหุ้นเข้า Watchlist ส่วนตัวของคุณ\n"
            "   *(ตัวอย่าง: /add NVDA US หรือ /add PTT.BK TH)*\n"
            "🔹 `/remove <ชื่อหุ้น>` - ลบหุ้นออกจาก Watchlist\n"
            "   *(ตัวอย่าง: /remove NVDA)*\n"
            "🔹 `/list` - ดูรายชื่อหุ้นทั้งหมดใน Watchlist ของคุณ\n"
            "🔹 `/scan` - สั่ง AI ให้วิเคราะห์หุ้น **ทุกตัว** ใน Watchlist\n"
            "🔹 `/scan <ชื่อหุ้น>` - สั่ง AI ให้วิเคราะห์หุ้น **เฉพาะตัวที่ระบุ**\n"
            "   *(ตัวอย่าง: /scan TSLA)*"
        )
        await message.answer(help_text, parse_mode="Markdown")

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

    async def cmd_remove(self, message: types.Message):
        """Handle /remove <symbol> — remove stock from user's watchlist."""
        if not message.text or not message.from_user:
            return

        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.reply("❌ Usage: /remove <symbol>\nExample: /remove NVDA")
            return

        symbol = parts[1].upper()
        telegram_id = message.from_user.id

        async with self.db.session() as session:
            stmt = select(Watchlist).join(User, Watchlist.user_id == User.id).where(User.telegram_id == telegram_id, Watchlist.symbol == symbol)
            res = await session.execute(stmt)
            item = res.scalar_one_or_none()

            if item:
                await session.delete(item)
                await session.commit()
                await message.reply(f"🗑️ Removed {symbol} from your watchlist.")
            else:
                await message.reply(f"ℹ️ {symbol} is not in your watchlist.")

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

                targets_str = (
                    "\n".join(f"  • {t}" for t in grade_result.buy_targets)
                    if getattr(grade_result, "buy_targets", None)
                    else "  • N/A"
                )

                # Create a visual progress bar for confidence
                conf = grade_result.confidence
                filled = int(conf / 10)
                empty = 10 - filled
                bar = "█" * filled + "░" * empty

                report_text = (
                    f"{emoji} DCA Analysis: {grade_result.symbol}\n"
                    f"Grade: {grade_result.grade}/4 — {label}\n"
                    f"Confidence: {conf}% [{bar}]\n\n"
                    f"📊 Market Snapshot:\n"
                    f"• Current Price: ${snapshot.current_price:,.2f}\n"
                    f"• Drawdown from ATH: {snapshot.drawdown_pct}%\n"
                    f"• ATH Price: ${snapshot.ath_price:,.2f}\n\n"
                    f"💡 AI Advice (คำแนะนำ):\n"
                    f"{grade_result.advice}\n\n"
                    f"🎯 Buy Targets (ราคาเป้าหมาย):\n"
                    f"{targets_str}\n\n"
                    f"📝 Reasons:\n"
                    f"{reasons_str}"
                )
                await message.reply(report_text)

            await session.commit()

    async def broadcast_scan(self, market: str = None):
        """Run broadcast scan and send to configured channel."""
        if not self.config.broadcast_channel_id:
            logger.info("BROADCAST_CHANNEL_ID not set. Skipping broadcast.")
            return

        symbols = await self.db.get_unique_watchlist_symbols(market)
        if not symbols:
            logger.info(f"No symbols found for market {market}. Skipping broadcast.")
            return

        snapshots = self.fetcher.fetch(symbols)
        if not snapshots:
            return

        enriched = self.transformer.enrich(snapshots)
        bot_user = await self.bot.get_me()

        for symbol, signal in enriched.items():
            result = self.grader.grade(signal)
            
            targets_str = (
                "\n".join(f"  • {t}" for t in result.buy_targets)
                if getattr(result, "buy_targets", None)
                else "  • N/A"
            )
            
            conf = result.confidence
            filled = int(conf / 10)
            empty = 10 - filled
            bar = "█" * filled + "░" * empty
            
            msg = f"#{symbol} Analysis:\nGrade: {result.grade}/4\nConfidence: {conf}% [{bar}]\n\n💡 Advice:\n{result.advice}\n\n🎯 Buy Targets:\n{targets_str}"
            kb = create_add_watchlist_keyboard(symbol, bot_user.username)
            try:
                await self.bot.send_message(self.config.broadcast_channel_id, msg, reply_markup=kb)
            except Exception as e:
                logger.error(f"Failed to send broadcast for {symbol}: {e}")

    async def start(self):
        """Initialize database, scheduler, and start polling."""
        logger.info("Initializing database tables...")
        await self.db.create_tables()

        logger.info("Starting scheduler...")
        self.scheduler = AsyncIOScheduler(timezone="Asia/Bangkok")
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=7, minute=0)
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=9, minute=30, args=['TH'])
        self.scheduler.add_job(self.broadcast_scan, 'cron', hour=20, minute=0, args=['US'])
        self.scheduler.start()

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
